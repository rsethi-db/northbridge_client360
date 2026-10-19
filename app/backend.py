"""Data access for the Client 360 app.

Two paths, chosen per client by entitlement rather than convenience:

* Lakebase (app service principal) - low-latency reads of the synced serving tables (`nb_serving.*`, unrestricted
  segment only) and steward write-back into `steward.steward_decisions`.
* SQL warehouse + Genie on behalf of the signed-in user - Restricted-segment clients are never copied to Lakebase.
  They are read from certified gold with the user's own token, so the Unity Catalog ABAC row filter decides whether
  the user sees them at all.
"""
import os
import time
import uuid
from functools import lru_cache

import pandas as pd
import psycopg
from databricks import sql as dbsql
from databricks.sdk import WorkspaceClient
from flask import request
from psycopg_pool import ConnectionPool

CATALOG = os.getenv("CATALOG", "richasethi_febar_catalog")
P = os.getenv("SCHEMA_PREFIX", "nb_")
GOLD = f"{CATALOG}.{P}gold"
SERVING = f"{P}serving"          # Postgres schema holding the synced tables
ENDPOINT = os.getenv("LAKEBASE_ENDPOINT", "projects/northbridge-client360/branches/production/endpoints/primary")
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "")
GENIE_TITLE = os.getenv("GENIE_SPACE_TITLE", "Northbridge Client 360")
ROUNDTRIP_JOB_ID = os.getenv("ROUNDTRIP_JOB_ID")
RESTRICTED_GROUP = os.getenv("RESTRICTED_GROUP", "northbridge_restricted_clients")
PII_GROUP = os.getenv("PII_GROUP", "northbridge_pii_readers")
STEWARD_GROUP = os.getenv("STEWARD_GROUP", "northbridge_data_stewards")
BUILD_JOB_NAME = os.getenv("BUILD_JOB_NAME", "Northbridge Client 360 - Build end to end")

sp = WorkspaceClient()   # app service principal (DATABRICKS_CLIENT_ID / _SECRET injected by Databricks Apps)
HOST = sp.config.host


# ------------------------------------------------------------------------------------------------
# Lakebase: pooled connections with short-lived OAuth credentials
# ------------------------------------------------------------------------------------------------
_token = {"value": None, "expires": 0.0}


def _pg_password():
    if time.time() > _token["expires"]:
        _token["value"] = sp.api_client.do("POST", "/api/2.0/postgres/credentials", body={"endpoint": ENDPOINT})["token"]
        _token["expires"] = time.time() + 45 * 60   # credentials last 60 minutes
    return _token["value"]


class _TokenConnection(psycopg.Connection):
    @classmethod
    def connect(cls, conninfo="", **kwargs):
        kwargs["password"] = _pg_password()
        return super().connect(conninfo, **kwargs)


@lru_cache(maxsize=1)
def _pool():
    host = os.getenv("PGHOST") or sp.api_client.do("GET", f"/api/2.0/postgres/{ENDPOINT}")["status"]["hosts"]["host"]
    user = os.getenv("PGUSER") or sp.config.client_id
    conninfo = f"host={host} port={os.getenv('PGPORT', '5432')} dbname={os.getenv('PGDATABASE', 'databricks_postgres')} user={user} sslmode=require"
    return ConnectionPool(conninfo, connection_class=_TokenConnection, min_size=1, max_size=6, max_lifetime=40 * 60,
                          kwargs={"autocommit": True}, open=True)


def pg(query, params=None) -> pd.DataFrame:
    with _pool().connection() as conn:
        cur = conn.execute(query, params or ())
        cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(cur.fetchall(), columns=cols)


def pg_exec(query, params=None):
    with _pool().connection() as conn:
        conn.execute(query, params or ())


# ------------------------------------------------------------------------------------------------
# On-behalf-of-user: SQL warehouse and Genie with the signed-in user's token
# ------------------------------------------------------------------------------------------------
def user_token():
    try:
        return request.headers.get("x-forwarded-access-token")
    except RuntimeError:
        return None


def user_email():
    try:
        return request.headers.get("x-forwarded-email") or request.headers.get("x-forwarded-preferred-username") or "local-user"
    except RuntimeError:
        return "local-user"


def uc(query, params=None) -> pd.DataFrame:
    """Query Unity Catalog as the signed-in user (ABAC row filters and masks apply to *them*)."""
    token = user_token()
    if not token:
        raise PermissionError("no user token - run inside Databricks Apps with user authorization (scope: sql)")
    with dbsql.connect(server_hostname=HOST.replace("https://", ""), http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
                       access_token=token) as conn, conn.cursor() as cur:
        cur.execute(query, params or {})
        return pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])


def user_entitlements():
    try:
        r = uc(f"SELECT current_user() AS user, is_member('{RESTRICTED_GROUP}') AS restricted_access, "
               f"is_member('{PII_GROUP}') AS pii_access, is_member('{STEWARD_GROUP}') AS steward").iloc[0]
        return {"user": r.user, "restricted": bool(r.restricted_access), "pii": bool(r.pii_access), "steward": bool(r.steward)}
    except Exception as e:
        return {"user": user_email(), "restricted": False, "pii": False, "steward": False, "error": str(e)[:200]}


# ------------------------------------------------------------------------------------------------
# Account executive view
# ------------------------------------------------------------------------------------------------
SEARCH_COLS = "party_id, party_name, country_iso, ultimate_parent_party_id, ultimate_parent_name, hierarchy_level, client_origin"


def search_clients(text: str) -> pd.DataFrame:
    like = f"%{text.strip().lower()}%"
    standard = pg(f"""SELECT {SEARCH_COLS}, false AS is_restricted FROM {SERVING}.party
                      WHERE search_text LIKE %s ORDER BY hierarchy_level, party_name LIMIT 25""", (like,))
    try:   # Restricted segment: only exists for users the ABAC policy lets through
        restricted = uc(f"""SELECT {SEARCH_COLS}, is_restricted FROM {GOLD}.dim_party
                            WHERE is_restricted AND lower(concat_ws(' ', party_name, ultimate_parent_name, registration_number, party_id)) LIKE :q
                            ORDER BY hierarchy_level, party_name LIMIT 10""", {"q": like})
    except Exception:
        restricted = pd.DataFrame(columns=standard.columns)
    return pd.concat([standard, restricted], ignore_index=True)


def client_family(ultimate_parent_id: str, restricted: bool) -> dict:
    """Golden records, revenue, placements and source lineage for a whole corporate family."""
    if restricted:
        q = {"parties": (f"SELECT *, to_json(source_systems) AS source_systems_json FROM {GOLD}.dim_party WHERE ultimate_parent_party_id = :id", {"id": ultimate_parent_id}),
             "revenue": (f"SELECT * FROM {GOLD}.client_revenue_summary WHERE ultimate_parent_party_id = :id", {"id": ultimate_parent_id}),
             "placements": (f"SELECT * FROM {GOLD}.fact_placements WHERE ultimate_parent_party_id = :id", {"id": ultimate_parent_id}),
             "xref": (f"SELECT * FROM {GOLD}.party_source_xref WHERE ultimate_parent_party_id = :id", {"id": ultimate_parent_id})}
        out = {k: uc(sql_, p) for k, (sql_, p) in q.items()}
        out["parties"]["source_systems"] = out["parties"]["source_systems_json"]
    else:
        out = {"parties": pg(f"SELECT * FROM {SERVING}.party WHERE ultimate_parent_party_id = %s", (ultimate_parent_id,)),
               "revenue": pg(f"SELECT * FROM {SERVING}.client_revenue_summary WHERE ultimate_parent_party_id = %s", (ultimate_parent_id,)),
               "placements": pg(f"SELECT * FROM {SERVING}.placements WHERE ultimate_parent_party_id = %s", (ultimate_parent_id,)),
               "xref": pg(f"SELECT * FROM {SERVING}.party_source_xref WHERE ultimate_parent_party_id = %s", (ultimate_parent_id,))}
    for df in out.values():
        for c in df.columns:
            if c.endswith("_usd") or c in ("commission_rate",):
                df[c] = pd.to_numeric(df[c], errors="coerce")
    return out


def metric_view_total(ultimate_parent_id: str, fiscal_year: int):
    """Total Client Revenue from the certified metric view, as the user - proves the app ties to the dollar."""
    r = uc(f"""SELECT MEASURE(`Total Client Revenue`) AS v FROM {GOLD}.client_revenue_metrics
               WHERE `Ultimate Parent Party ID` = :id AND `Fiscal Year` = :fy""", {"id": ultimate_parent_id, "fy": fiscal_year})
    return float(r.v.iloc[0]) if len(r) and r.v.iloc[0] is not None else 0.0


# ------------------------------------------------------------------------------------------------
# Genie (on behalf of the user)
# ------------------------------------------------------------------------------------------------
def _user_ws():
    token = user_token()
    if not token:
        raise PermissionError("Genie needs the signed-in user's token (scope: dashboards.genie)")
    return WorkspaceClient(host=HOST, token=token, auth_type="pat")


@lru_cache(maxsize=1)
def _genie_space_id(_token_marker: str) -> str:
    w, token = _user_ws(), None
    while True:
        resp = w.genie.list_spaces(page_token=token)
        for s in resp.spaces or []:
            if s.title == GENIE_TITLE:
                return s.space_id
        token = resp.next_page_token
        if not token:
            break
    raise LookupError(f"Genie space '{GENIE_TITLE}' not found or not shared with you")


def genie_space_url():
    try:
        return f"{HOST}/genie/rooms/{_genie_space_id('x')}"
    except Exception:
        return None


def ask_genie(question: str, conversation_id: str | None = None) -> dict:
    """Ask Genie as the signed-in user. Pass conversation_id to ask a follow-up in the same conversation."""
    w = _user_ws()
    space = _genie_space_id("x")
    if conversation_id:
        msg = w.genie.create_message_and_wait(space, conversation_id, question)
    else:
        msg = w.genie.start_conversation_and_wait(space, question)
    out = {"text": None, "sql": None, "columns": None, "rows": None, "conversation_id": msg.conversation_id,
           "conversation_url": f"{HOST}/genie/rooms/{space}/chats/{msg.conversation_id}"}
    for att in msg.attachments or []:
        if att.text and att.text.content:
            out["text"] = att.text.content
        if att.query:
            out["sql"] = att.query.query
            out["text"] = out["text"] or att.query.description
            res = w.genie.get_message_attachment_query_result(space, msg.conversation_id, msg.message_id, att.attachment_id)
            sr = res.statement_response
            if sr and sr.result and sr.manifest:
                out["columns"] = [c.name for c in sr.manifest.schema.columns]
                out["rows"] = sr.result.data_array or []
    return out


# ------------------------------------------------------------------------------------------------
# Data steward view
# ------------------------------------------------------------------------------------------------
def review_queue() -> pd.DataFrame:
    return pg(f"""SELECT q.* FROM {SERVING}.match_review_queue q
                  WHERE NOT EXISTS (SELECT 1 FROM steward.steward_decisions d WHERE d.pair_id = q.pair_id)
                  ORDER BY CASE q.llm_recommendation WHEN 'MERGE' THEN 0 WHEN 'NEEDS_MORE_INFO' THEN 1 ELSE 2 END, q.match_score DESC""")


def record_decision(pair: dict, decision: str, rationale: str) -> str:
    """approve_merge / reject act on the pair; split detaches the right-hand record from its golden party."""
    left, right = pair["left_record_key"], pair["right_record_key"]
    if decision == "split":
        left, right = right, left
    decision_id = str(uuid.uuid4())
    pg_exec("""INSERT INTO steward.steward_decisions (decision_id, pair_id, left_record_key, right_record_key, decision, steward, rationale)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""", (decision_id, pair["pair_id"], left, right, decision, user_email(), rationale or None))
    return decision_id


def recent_decisions(limit=15) -> pd.DataFrame:
    return pg("""SELECT decided_at, steward, decision, left_record_key, right_record_key, rationale
                 FROM steward.steward_decisions ORDER BY decided_at DESC LIMIT %s""", (limit,))


def _active(job_id):
    return any(True for _ in sp.jobs.list_runs(job_id=job_id, active_only=True, limit=1))


def run_roundtrip():
    """Start the steward round-trip job unless it, or the full build, is already running (they rewrite the same tables)."""
    if _active(int(ROUNDTRIP_JOB_ID)):
        return False, "Entity resolution is already running; your decisions will be included if they were saved before it started, otherwise run it again afterwards."
    build = next(iter(sp.jobs.list(name=BUILD_JOB_NAME)), None)
    if build and _active(build.job_id):
        return False, "The full build is running right now. Try again when it finishes."
    sp.jobs.run_now(job_id=int(ROUNDTRIP_JOB_ID))
    return True, None


def last_roundtrip():
    runs = list(sp.jobs.list_runs(job_id=int(ROUNDTRIP_JOB_ID), limit=1))
    if not runs:
        return None
    r = runs[0]
    return {"run_id": r.run_id, "state": (r.state.result_state or r.state.life_cycle_state).value if r.state else "?",
            "url": r.run_page_url, "start": pd.to_datetime(r.start_time, unit="ms", utc=True)}
