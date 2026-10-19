# Notebook run: d9e8ad27-e10b-441b-ab11-ca3df4487192

```markdown
%md
# 30 · Lakebase operational serving and steward write-back

**Lakehouse → Lakebase (synced tables).** The unrestricted `app.app_*` serving projections are synced into the
Lakebase project as Postgres tables in schema `nb_serving` (UC side: `serving.*`). Snapshot mode: every run
refreshes them right after the gold pipeline, so the app always reads the latest golden records with
millisecond latency.

**Lakebase → Lakehouse (Lakehouse Sync).** The app writes steward decisions to `steward.steward_decisions` in
Postgres. A CDF config streams every change into `app.lb_steward_decisions_history` (SCD2 Delta), which entity
resolution applies on its next run. No custom sync code.

Idempotent: creates what is missing, refreshes what exists, (re)grants the app service principal.
```

```python
%pip install -q pg8000==1.31.2
%restart_python
```
**Output:**
```
Note: you may need to restart the kernel using %restart_python or dbutils.library.restartPython() to use updated packages.
```

```python
dbutils.widgets.text("catalog", "richasethi_febar_catalog")
dbutils.widgets.text("schema_prefix", "nb_")
dbutils.widgets.text("lakebase_project", "northbridge-client360")
dbutils.widgets.text("app_name", "northbridge-client360")
CATALOG, P = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema_prefix")
PROJECT, APP_NAME = dbutils.widgets.get("lakebase_project"), dbutils.widgets.get("app_name")
BRANCH = f"projects/{PROJECT}/branches/production"
ENDPOINT = f"{BRANCH}/endpoints/primary"
DATABASE = f"{BRANCH}/databases/databricks-postgres"
PG_DB, PG_SERVING = "databricks_postgres", f"{P}serving"

# synced table (UC serving schema) -> (source serving projection, primary key)
SYNCS = {
    "party": ("app_party", ["party_id"]),
    "party_source_xref": ("app_party_source_xref", ["record_key"]),
    "client_revenue_summary": ("app_client_revenue_summary", ["summary_id"]),
    "placements": ("app_placements", ["placement_id"]),
    "match_review_queue": ("app_match_review_queue", ["pair_id"]),
}
```

```python
import ssl
import time

import pg8000.dbapi   # pure-Python Postgres driver (psycopg's binary wheel aborts the serverless Python process)
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound

w = WorkspaceClient()
api = w.api_client.do

def get_or_none(path):
    try:
        return api("GET", path)
    except NotFound:
        return None
    except Exception as e:
        if "does not exist" in str(e) or "NOT_FOUND" in str(e):
            return None
        raise
```

```markdown
%md ## 1 · Synced tables (create or refresh)
```

```python
pipelines = {}
for name, (source, pk) in SYNCS.items():
    full = f"{CATALOG}.{PG_SERVING}.{name}"
    st = get_or_none(f"/api/2.0/postgres/synced_tables/{full}")
    if st is None:
        api("POST", "/api/2.0/postgres/synced_tables", query={"synced_table_id": full}, body={"spec": {
            "source_table_full_name": f"{CATALOG}.{P}app.{source}", "primary_key_columns": pk, "scheduling_policy": "SNAPSHOT",
            "branch": BRANCH, "postgres_database": PG_DB, "create_database_objects_if_missing": True,
            "new_pipeline_spec": {"storage_catalog": CATALOG, "storage_schema": PG_SERVING}}})
        print("created", full)
    else:
        pid = st["status"].get("pipeline_id")
        try:
            w.pipelines.start_update(pid, full_refresh=False)
            print("refreshing", full)
        except Exception as e:   # an update already in progress will pick up the latest source anyway
            print(f"{full}: refresh not started ({str(e)[:120]}); waiting for the running update")

deadline = time.time() + 1800
pending = set(SYNCS)
while pending and time.time() < deadline:
    time.sleep(20)
    for name in list(pending):
        s = get_or_none(f"/api/2.0/postgres/synced_tables/{CATALOG}.{PG_SERVING}.{name}")["status"]
        state = s.get("detailed_state", "")
        if state.startswith("SYNCED_TABLE_ONLINE") and "PENDING" not in state.replace("NO_PENDING", ""):
            # snapshot refresh is done once the pipeline's latest update is complete
            pid = s.get("pipeline_id")
            latest = w.pipelines.get(pid).latest_updates
            upd = latest[0].state.value if latest else "COMPLETED"
            if upd == "COMPLETED":
                pending.discard(name); print(f"{name}: {state}")
            elif upd in ("FAILED", "CANCELED"):
                raise RuntimeError(f"synced table {name}: latest refresh {upd} (pipeline {pid}) - serving copy is stale")
        elif "FAILED" in state:
            raise RuntimeError(f"synced table {name} failed: {s.get('message')}")
if pending:
    raise TimeoutError(f"synced tables still syncing: {pending}")
```
**Output:**
```
created richasethi_febar_catalog.nb_serving.party
created richasethi_febar_catalog.nb_serving.party_source_xref
created richasethi_febar_catalog.nb_serving.client_revenue_summary
created richasethi_febar_catalog.nb_serving.placements
created richasethi_febar_catalog.nb_serving.match_review_queue
client_revenue_summary: SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE
placements: SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE
party_source_xref: SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE
party: SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE
match_review_queue: SYNCED_TABLE_ONLINE_TRIGGERED_UPDATE
```

```markdown
%md ## 2 · Postgres: steward write-back table and app grants
```

```python
host = api("GET", f"/api/2.0/postgres/{ENDPOINT}")["status"]["hosts"]["host"]
token = api("POST", "/api/2.0/postgres/credentials", body={"endpoint": ENDPOINT})["token"]
me = w.current_user.me().user_name

try:
    sp = w.apps.get(APP_NAME).service_principal_client_id
except Exception:
    sp = None
    print(f"app {APP_NAME} not deployed yet - skipping app grants")

if sp:   # the app's Postgres role is normally created when its Lakebase resource is attached; create it if not
    try:
        api("POST", f"/api/2.0/postgres/{BRANCH}/roles", query={"role_id": sp},
            body={"spec": {"identity_type": "SERVICE_PRINCIPAL", "postgres_role": sp, "auth_method": "LAKEBASE_OAUTH_V1"}})
        print("created Postgres role for app SP", sp)
    except Exception as e:
        print("app SP role already present" if "exist" in str(e).lower() else f"role create skipped: {str(e)[:200]}")

conn = pg8000.dbapi.connect(host=host, database=PG_DB, user=me, password=token, ssl_context=ssl.create_default_context())
conn.autocommit = True
c = conn.cursor()
c.execute("CREATE SCHEMA IF NOT EXISTS steward")
c.execute("""CREATE TABLE IF NOT EXISTS steward.steward_decisions (
    decision_id TEXT PRIMARY KEY, pair_id TEXT, left_record_key TEXT NOT NULL, right_record_key TEXT,
    decision TEXT NOT NULL CHECK (decision IN ('approve_merge', 'reject', 'split')),
    steward TEXT NOT NULL, rationale TEXT, decided_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
c.execute("ALTER TABLE steward.steward_decisions REPLICA IDENTITY FULL")   # required by Lakehouse Sync
c.execute("COMMENT ON TABLE steward.steward_decisions IS 'Steward match-review decisions from the Client 360 app. Streamed to UC by Lakehouse Sync.'")
if sp:
    for stmt in [f'GRANT USAGE ON SCHEMA {PG_SERVING} TO "{sp}"', f'GRANT SELECT ON ALL TABLES IN SCHEMA {PG_SERVING} TO "{sp}"',
                 f'ALTER DEFAULT PRIVILEGES IN SCHEMA {PG_SERVING} GRANT SELECT ON TABLES TO "{sp}"',
                 f'GRANT USAGE ON SCHEMA steward TO "{sp}"', f'GRANT SELECT, INSERT ON steward.steward_decisions TO "{sp}"']:
        c.execute(stmt)
    print("granted app SP read on serving + insert on steward decisions")
c.execute(f"SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN ('{PG_SERVING}', 'steward') ORDER BY 1, 2")
for schema, table in c.fetchall():
    c.execute(f'SELECT count(*) FROM "{schema}"."{table}"')
    print(f"{schema}.{table}: {c.fetchone()[0]:,} rows")
conn.close()
```
**Output:**
```
app SP role already present
granted app SP read on serving + insert on steward decisions
nb_serving.client_revenue_summary: 6,558 rows
nb_serving.match_review_queue: 50 rows
nb_serving.party: 1,811 rows
nb_serving.party_source_xref: 4,139 rows
nb_serving.placements: 19,933 rows
steward.steward_decisions: 0 rows
```

```markdown
%md ## 3 · Lakehouse Sync: steward decisions back into Unity Catalog
```

```python
configs = (get_or_none(f"/api/2.0/postgres/{DATABASE}/cdf-configs") or {}).get("cdf_configs", [])
if not any(cfg.get("postgres_schema") == "steward" or cfg.get("name", "").endswith("nb_steward_decisions") for cfg in configs):
    api("POST", f"/api/2.0/postgres/{DATABASE}/cdf-configs", query={"cdf_config_id": "nb_steward_decisions"},
        body={"catalog": CATALOG, "schema": f"{P}app", "postgres_schema": "steward"})
    print("created Lakehouse Sync config steward -> app.lb_steward_decisions_history")
else:
    print("Lakehouse Sync config already present")
print("history table exists:", spark.catalog.tableExists(f"{CATALOG}.{P}app.lb_steward_decisions_history"))
```
**Output:**
```
created Lakehouse Sync config steward -> app.lb_steward_decisions_history
history table exists: True
```
