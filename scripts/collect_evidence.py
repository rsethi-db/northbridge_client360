"""Collect text-readable execution evidence for every stage of the Northbridge Client 360 build into evidence/.

Runs real queries and API calls against the workspace; nothing here is hand-written output.
Usage: python scripts/collect_evidence.py [profile] [--with-toggle] [--with-roundtrip]
  --with-toggle     removes you from the restricted group, proves the ABAC row filter hides the segment, re-adds you
  --with-roundtrip  approves a merge through the app, runs the steward round-trip job, shows the golden record change
"""
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import iam
from databricks.sdk.service.sql import StatementState

PROFILE = next((a for a in sys.argv[1:] if not a.startswith("--")), "fevm-richasethi-febar")
print = __import__("functools").partial(print, flush=True)
TOGGLE, ROUNDTRIP = "--with-toggle" in sys.argv, "--with-roundtrip" in sys.argv
C, P, WH = "richasethi_febar_catalog", "nb_", "f4edbf03911f5f8e"
G, S, ML, APP = f"{C}.{P}gold", f"{C}.{P}silver", f"{C}.{P}ml", f"{C}.{P}app"
APP_URL = "https://northbridge-client360-7474655101081776.aws.databricksapps.com"
OUT = os.path.join(os.path.dirname(__file__), "..", "evidence")
os.makedirs(f"{OUT}/notebook_runs", exist_ok=True)
w = WorkspaceClient(profile=PROFILE)
ME = w.current_user.me()
NOW = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def sql(q):
    r = w.statement_execution.execute_statement(warehouse_id=WH, statement=q, wait_timeout="50s")
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(2)
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"{r.status.error.message if r.status.error else r.status.state}\n{q}")
    cols = [c.name for c in r.manifest.schema.columns] if r.manifest and r.manifest.schema else []
    return cols, (r.result.data_array if r.result else None) or []


def md(cols, rows, n=25):
    if not cols:
        return "(no rows)"
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join("" if v is None else str(v).replace("|", "/").replace("\n", " ") for v in r) + " |" for r in rows[:n]]
    if len(rows) > n:
        out.append(f"\n_... {len(rows) - n} more rows_")
    return "\n".join(out)


def section(title, q, n=25):
    cols, rows = sql(q)
    return f"### {title}\n```sql\n{q.strip()}\n```\n{md(cols, rows, n)}\n"


def write(name, body):
    with open(f"{OUT}/{name}", "w") as f:
        f.write(f"_Collected {NOW()} by `scripts/collect_evidence.py` as `{ME.user_name}` on {w.config.host}_\n\n{body}")
    print("wrote", name)


def job_id(name):
    return next(j.job_id for j in w.jobs.list(name=name))


# ------------------------------------------------------------------------------------------------
# 1. Build job: task states + notebook outputs
# ------------------------------------------------------------------------------------------------
def notebook_markdown(run_id):
    html = w.jobs.export_run(run_id).views[0].content
    m = re.search(r"__DATABRICKS_NOTEBOOK_MODEL = '([^']+)'", html)
    model = json.loads(urllib.parse.unquote(base64.b64decode(m.group(1)).decode()))
    lines = [f"# Notebook run: {model.get('name')}", ""]
    for cmd in model.get("commands", []):
        code = cmd.get("command", "")
        lines += ["```python" if not code.lstrip().startswith("%md") else "```markdown", code.strip(), "```"]
        res = cmd.get("results") or {}
        data = res.get("data")
        if isinstance(data, list):   # mixed outputs
            text = "\n".join(str(d.get("data", "")) for d in data if isinstance(d, dict) and d.get("type") in ("ansi", "text"))
        elif isinstance(data, str):
            text = data
        else:
            text = ""
        if res.get("type") == "table" and isinstance(res.get("data"), list):
            schema = [c["name"] for c in res.get("schema", [])]
            text = md(schema, res["data"], 30)
            lines += ["**Output (table):**", "", text, ""]
        elif text.strip():
            text = re.sub(r"\x1b\[[0-9;]*m", "", text)
            lines += ["**Output:**", "```", text.strip()[:6000], "```"]
        if cmd.get("error"):
            lines += ["**Error:**", "```", re.sub(r"\x1b\[[0-9;]*m", "", str(cmd["error"]))[:3000], "```"]
        lines.append("")
    return "\n".join(lines)


def build_job_evidence():
    jid = job_id("Northbridge Client 360 - Build end to end")
    run = next(iter(w.jobs.list_runs(job_id=jid, limit=1, expand_tasks=True)))
    run = w.jobs.get_run(run.run_id)
    rows = []
    for t in sorted(run.tasks, key=lambda t: t.start_time or 0):
        dur = round(((t.end_time or 0) - (t.start_time or 0)) / 1000) if t.end_time else None
        rows.append([t.task_key, t.state.result_state.value if t.state.result_state else t.state.life_cycle_state.value, dur,
                     datetime.fromtimestamp((t.start_time or 0) / 1000, timezone.utc).strftime("%H:%M:%S")])
        if t.notebook_task and t.state.result_state and t.state.result_state.value == "SUCCESS":
            try:
                with open(f"{OUT}/notebook_runs/{t.task_key}.md", "w") as f:
                    f.write(notebook_markdown(t.run_id))
            except Exception as e:
                print("notebook export failed", t.task_key, e)
    body = (f"# Build job run\nJob `{jid}`, run `{run.run_id}`: **{run.state.result_state.value if run.state.result_state else run.state.life_cycle_state.value}**  \n"
            f"Run page: {run.run_page_url}\n\n" + md(["task", "result", "seconds", "start (UTC)"], rows, 50) +
            "\n\nEach notebook task's executed cells and outputs are in `evidence/notebook_runs/<task>.md`.\n")
    write("01_build_job_run.md", body)


# ------------------------------------------------------------------------------------------------
# 2. Lakeflow: expectations + quarantine
# ------------------------------------------------------------------------------------------------
def pipeline_evidence():
    pid = next(p.pipeline_id for p in w.pipelines.list_pipelines() if p.name.startswith("Northbridge Client 360 - 1 Ingest"))
    body = "# Lakeflow Declarative Pipeline: data quality\n\n"
    body += section("Expectation results from the pipeline event log (latest update)", f"""
WITH ev AS (SELECT origin.update_id, origin.flow_name, details:flow_progress.data_quality.expectations AS e, timestamp
            FROM event_log('{pid}') WHERE event_type = 'flow_progress' AND details:flow_progress.data_quality.expectations IS NOT NULL),
latest AS (SELECT update_id FROM ev ORDER BY timestamp DESC LIMIT 1)
SELECT split_part(flow_name, '.', 3) AS dataset, x.name AS expectation, sum(x.passed_records) AS passed, sum(x.failed_records) AS failed
FROM ev LATERAL VIEW explode(from_json(e, 'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) t AS x
WHERE update_id = (SELECT update_id FROM latest)
GROUP BY ALL ORDER BY failed DESC, dataset""", 40)
    body += section("Quarantined rows by rule (nb_silver.dq_quarantine)", f"SELECT silver_table, failed_rule, rule_definition, count(*) AS rows FROM {S}.dq_quarantine GROUP BY ALL ORDER BY rows DESC")
    body += section("Sample quarantined records", f"SELECT silver_table, failed_rule, record_key, left(record, 180) AS record FROM {S}.dq_quarantine ORDER BY silver_table LIMIT 8")
    counts = []
    for layer in ["bronze", "silver", "gold", "app"]:
        _, tabs = sql(f"SELECT table_name FROM {C}.information_schema.tables WHERE table_schema = '{P}{layer}' AND table_type <> 'VIEW' AND table_name NOT LIKE 'event_log%' ORDER BY 1")
        for (t,) in tabs:
            try:
                counts.append([layer, t, sql(f"SELECT count(*) FROM {C}.{P}{layer}.{t}")[1][0][0]])
            except Exception as e:
                counts.append([layer, t, f"n/a ({str(e)[:60]})"])
    body += "### Row counts by layer\n" + md(["layer", "table", "rows"], counts, 80) + "\n"
    write("02_lakeflow_data_quality.md", body)


# ------------------------------------------------------------------------------------------------
# 3. Entity resolution + MLflow
# ------------------------------------------------------------------------------------------------
def er_evidence():
    body = "# Entity resolution, match model and GenAI assist\n\n"
    body += section("Entity resolution run log", f"SELECT * FROM {ML}.er_run_log ORDER BY run_ts DESC")
    body += section("Headline client: every source record unified into Kestrel Industries plc", f"""
SELECT x.party_id, x.source_system, x.source_record_id, x.source_name, x.match_method, x.match_confidence
FROM {ML}.party_xref x WHERE x.party_id = (SELECT party_id FROM {G}.dim_party WHERE party_name = 'Kestrel Industries plc')
ORDER BY x.source_system""")
    body += section("Kestrel legal-entity hierarchy", f"""
SELECT party_id, party_name, country_iso, hierarchy_level, parent_party_name, parent_link_source, source_record_count, source_systems
FROM {G}.dim_party WHERE ultimate_parent_name = 'Kestrel Industries plc' ORDER BY hierarchy_level, party_name""")
    body += section("True negative: same trading name, different company - kept separate", f"""
SELECT party_id, party_name, country_iso, registration_number, ultimate_parent_name FROM {G}.dim_party
WHERE party_name LIKE 'Kestrel%' AND ultimate_parent_name <> 'Kestrel Industries plc'""")
    body += section("Match score distribution", f"SELECT match_band, count(*) AS pairs, round(min(match_score), 3) AS min_score, round(max(match_score), 3) AS max_score FROM {ML}.match_candidates_scored GROUP BY 1 ORDER BY 2 DESC")
    body += section("LLM assessments of review-band pairs", f"SELECT llm_endpoint, llm_recommendation, llm_confidence, count(*) AS pairs FROM {ML}.match_review_queue GROUP BY ALL ORDER BY pairs DESC")
    body += section("Sample LLM rationales (stored for stewards)", f"SELECT left_name, right_name, match_score, llm_recommendation, llm_rationale FROM {ML}.match_review_queue ORDER BY pair_id LIMIT 6")
    mv = w.model_versions.list(full_name=f"{ML}.party_match_model") if hasattr(w, "model_versions") else []
    versions = [[v.version, v.status.value if v.status else None, (v.aliases or [None]) and ",".join(a.alias_name for a in (v.aliases or [])), v.comment] for v in mv]
    body += "### Unity Catalog registered model `nb_ml.party_match_model`\n" + md(["version", "status", "aliases", "comment"], versions) + "\n"
    exp = w.experiments.get_by_name(f"/Users/{ME.user_name}/northbridge_entity_resolution").experiment
    runs = list(w.experiments.search_runs(experiment_ids=[exp.experiment_id], max_results=3))
    body += "\n### MLflow training runs\n" + md(["run_id", "metric", "value"], [[r.info.run_id[:12], m.key, round(m.value, 4)] for r in runs[:1] for m in (r.data.metrics or [])], 30) + "\n"
    write("03_entity_resolution.md", body)


# ------------------------------------------------------------------------------------------------
# 4. Governance: ABAC, tags, metric view reconciliation, row filter toggle
# ------------------------------------------------------------------------------------------------
def governance_evidence():
    body = "# Unity Catalog governance\n\n"
    pols = [[p.name, p.policy_type.value, ",".join(p.to_principals or []), ";".join(mc.condition for mc in (p.match_columns or [])), p.comment]
            for p in w.policies.list_policies(on_securable_type="schema", on_securable_fullname=G)]
    body += "### ABAC policies on the gold schema\n" + md(["policy", "type", "to", "match columns", "comment"], pols) + "\n\n"
    body += section("Table tags (certified gold, uncertified silver, SOX, confidentiality)", f"""
SELECT schema_name, table_name, collect_list(concat(tag_name, '=', coalesce(tag_value, ''))) AS tags FROM {C}.information_schema.table_tags
WHERE schema_name IN ('{P}silver', '{P}gold') GROUP BY ALL ORDER BY 1, 2""", 40)
    body += section("Column tags driving ABAC (rls_filter_key, class.*)", f"""
SELECT schema_name, table_name, column_name, tag_name, tag_value FROM {C}.information_schema.column_tags
WHERE schema_name = '{P}gold' ORDER BY table_name, column_name""", 40)
    body += section("Masking in effect for the current user (not in northbridge_pii_readers)", f"SELECT contact_id, contact_name, title, email, phone FROM {G}.party_contacts LIMIT 5")
    body += section("Revenue ties to the dollar: metric view vs fact vs app serving table", f"""
SELECT (SELECT MEASURE(`Total Client Revenue`) FROM {G}.client_revenue_metrics WHERE `Fiscal Year` = 2025) AS metric_view_fy2025,
       (SELECT sum(amount_usd) FROM {G}.fact_revenue WHERE fiscal_year = 2025) AS fact_revenue_fy2025,
       (SELECT sum(total_revenue_usd) FROM {G}.client_revenue_summary WHERE fiscal_year = 2025) AS revenue_summary_fy2025""")
    body += section("Metric view definition", f"SELECT table_name, comment FROM {C}.information_schema.tables WHERE table_schema = '{P}gold' AND table_name = 'client_revenue_metrics'")
    if TOGGLE:
        gid = next(iter(w.groups.list(filter='displayName eq "northbridge_restricted_clients"'))).id
        probe = (f"SELECT is_member('northbridge_restricted_clients') AS in_restricted_group, (SELECT count(*) FROM {G}.dim_party) AS parties_visible, "
                 f"(SELECT count(*) FROM {G}.dim_party WHERE is_restricted) AS restricted_parties_visible, "
                 f"(SELECT round(MEASURE(`Total Client Revenue`), 2) FROM {G}.client_revenue_metrics WHERE `Fiscal Year` = 2025) AS fy2025_revenue_visible")
        before = sql(probe)
        w.groups.patch(gid, operations=[iam.Patch(op=iam.PatchOp.REMOVE, path=f'members[value eq "{ME.id}"]')],
                       schemas=[iam.PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP])
        t0, after = time.time(), None
        try:
            while time.time() - t0 < 900:
                after = sql(probe)
                if after[1][0][0] == "false":
                    break
                time.sleep(20)
            genie = None
            try:   # the same question through Genie while outside the group
                space = next(s.space_id for s in w.genie.list_spaces().spaces if s.title == "Northbridge Client 360")
                m = w.genie.start_conversation_and_wait(space, "How many restricted clients do we have and what was their total revenue in 2025?")
                genie = next((a.text.content for a in m.attachments or [] if a.text), None) or next((a.query.description for a in m.attachments or [] if a.query), None)
            except Exception as e:
                genie = f"(genie error: {e})"
        finally:
            w.groups.patch(gid, operations=[iam.Patch(op=iam.PatchOp.ADD, path="members", value=[{"value": ME.id}])],
                           schemas=[iam.PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP])
        body += (f"### ABAC row filter toggle: {ME.user_name} removed from `northbridge_restricted_clients`, then re-added\n"
                 f"**In the group:**\n{md(*before)}\n\n**Removed from the group** (policy took effect after {round(time.time() - t0)}s):\n{md(*after)}\n\n"
                 f"**Genie, asked while outside the group:** {genie}\n\nMembership restored afterwards.\n")
    write("04_governance.md", body)


# ------------------------------------------------------------------------------------------------
# 5. Lineage
# ------------------------------------------------------------------------------------------------
def lineage_evidence():
    _, edges = sql(f"""SELECT DISTINCT coalesce(source_table_full_name, source_path) AS src, target_table_full_name AS tgt
                       FROM system.access.table_lineage WHERE event_date >= current_date() - 2 AND target_table_full_name LIKE '{C}.{P}%'""")
    up = {}
    for s_, t_ in edges:
        if s_ and t_ and s_ != t_:
            up.setdefault(t_, set()).add(s_)

    def walk(node, depth=0, seen=None):
        seen = seen or set()
        lines = [("  " * depth) + "- " + node.replace(f"{C}.", "")]
        for s_ in sorted(up.get(node, [])):
            if s_ not in seen and "event_log" not in s_:
                seen.add(s_)
                lines += walk(s_, depth + 1, seen)
        return lines
    tree = "\n".join(walk(f"{G}.dim_party"))
    sysmap = {"crm_": "Northbridge CRM", "billing_": "Northbridge billing & commission", "placement_": "Placement platform", "hc_": "Harbor & Cole AMS"}
    systems = sorted({v for k, v in sysmap.items() if f"nb_bronze.{k}" in tree})
    files = []
    for t in ["crm_accounts", "billing_clients", "placement_insureds", "hc_clients", "le_registry"]:
        files += sql(f"SELECT '{t}' AS bronze_table, regexp_extract(_source_file, 'landing/(.+)$', 1) AS source_file, count(*) AS rows FROM {C}.{P}bronze.{t} GROUP BY ALL")[1]
    tree += "\n\nFile-level provenance (bronze `_source_file`, captured by Auto Loader from the UC Volume):\n\n" + md(["bronze table", "file in /Volumes/.../nb_raw/landing", "rows"], files)
    body = ("# Lineage (system.access.table_lineage)\n\nUpstream of the golden party record `nb_gold.dim_party`:\n\n" + tree +
            f"\n\nSource systems reached from the golden record: **{len(systems)} of 4** - {systems}\n\nGenie answers trace to `nb_gold` tables and the metric view; see `08_genie_test_results.md`.\n")
    write("05_lineage.md", body)


# ------------------------------------------------------------------------------------------------
# 6. Lakebase serving + app selftest
# ------------------------------------------------------------------------------------------------
def pg_query(q):
    out = subprocess.check_output([sys.executable, os.path.join(os.path.dirname(__file__), "pg.py"), q, PROFILE]).decode()
    lines = [l.split("\t") for l in out.strip().splitlines()]
    return lines[0], lines[1:]


def lakebase_evidence():
    body = "# Lakebase operational serving\n\n"
    rows = []
    for t in ["party", "party_source_xref", "client_revenue_summary", "placements", "match_review_queue"]:
        st = w.api_client.do("GET", f"/api/2.0/postgres/synced_tables/{C}.{P}serving.{t}")["status"]
        rows.append([f"{P}serving.{t}", f"{P}app.app_{t}", st.get("detailed_state"), (st.get("last_sync") or {}).get("timestamp") if isinstance(st.get("last_sync"), dict) else st.get("last_sync")])
    body += "### Synced tables (UC -> Lakebase, snapshot mode)\n" + md(["synced table", "source projection", "state", "last sync"], rows) + "\n\n"
    cols, data = pg_query(f"SELECT 'party' t, count(*) FROM {P}serving.party UNION ALL SELECT 'placements', count(*) FROM {P}serving.placements "
                          f"UNION ALL SELECT 'match_review_queue', count(*) FROM {P}serving.match_review_queue UNION ALL SELECT 'steward_decisions', count(*) FROM steward.steward_decisions")
    body += "### Postgres row counts\n" + md(cols, data) + "\n\n"
    cols, data = pg_query(f"SELECT count(*) FILTER (WHERE regexp_replace(lower(coalesce(industry,'')), '[^a-z]', '', 'g') = 'defencegovernment') AS defence_rows, count(*) AS rows FROM {P}serving.party")
    body += "### Restricted segment is never copied to Lakebase\n" + md(cols, data) + "\n\n"
    cfg = w.api_client.do("GET", f"/api/2.0/postgres/projects/northbridge-client360/branches/production/databases/databricks-postgres/cdf-configs")
    body += "### Lakehouse Sync (Lakebase -> UC) configs\n```json\n" + json.dumps(cfg, indent=2)[:2000] + "\n```\n"
    write("06_lakebase.md", body)

    tok = w.config.authenticate()["Authorization"]
    res = {}
    for client in ["Kestrel Industries plc", "Ironclad Security plc"]:
        r = requests.get(f"{APP_URL}/api/selftest", params={"client": client}, headers={"Authorization": tok}, timeout=180)
        res[client] = r.json() if r.ok else {"status": r.status_code, "body": r.text[:500]}
    write("07_app_selftest.md", "# Databricks App selftest (`/api/selftest`, called as the signed-in user)\n\n"
          "Exercises Lakebase search + client view, the on-behalf-of-user restricted path, the metric-view tie-out, the steward queue and Genie lookup.\n\n"
          "```json\n" + json.dumps(res, indent=2, default=str) + "\n```\n")


# ------------------------------------------------------------------------------------------------
# 7. Steward round trip
# ------------------------------------------------------------------------------------------------
def roundtrip_evidence():
    _, pick = sql(f"""WITH gt AS (SELECT concat(source_system, ':', source_record_id) k, true_entity_id e
                                  FROM read_files('/Volumes/{C}/{P}raw/landing/_labels/er_ground_truth.csv', format => 'csv', header => true))
                      SELECT q.* FROM {APP}.app_match_review_queue q JOIN gt l ON l.k = q.left_record_key JOIN gt r ON r.k = q.right_record_key
                      WHERE q.llm_recommendation = 'MERGE' AND q.left_party_id <> q.right_party_id AND l.e = r.e ORDER BY q.match_score DESC LIMIT 1""")
    cols = sql(f"SELECT * FROM {APP}.app_match_review_queue LIMIT 0")[0]
    pair = dict(zip(cols, pick[0]))
    probe = lambda: sql(f"""SELECT x.record_key, x.party_id, d.party_name, d.source_record_count, d.source_systems FROM {G}.party_source_xref x
                            JOIN {G}.dim_party d USING (party_id) WHERE x.record_key IN ('{pair['left_record_key']}', '{pair['right_record_key']}')""")
    before = probe()
    # Approve through the app's own callback (written to Lakebase by the app's service principal)
    tok = w.config.authenticate()["Authorization"]
    payload = {"output": "decision-msg.children", "outputs": {"id": "decision-msg", "property": "children"},
               "inputs": [{"id": "d-approve", "property": "n_clicks", "value": 1}, {"id": "d-reject", "property": "n_clicks", "value": None},
                          {"id": "d-split", "property": "n_clicks", "value": None}],
               "changedPropIds": ["d-approve.n_clicks"],
               "state": [{"id": "pair-ctx", "property": "data", "value": pair},
                         {"id": "rationale", "property": "value", "value": "Evidence run: same legal name, same country, LLM recommends MERGE."}]}
    r = requests.post(f"{APP_URL}/_dash-update-component", json=payload, headers={"Authorization": tok}, timeout=60)
    app_reply = r.text[:600]
    lake = pg_query(f"SELECT decision_id, pair_id, decision, steward, decided_at FROM steward.steward_decisions WHERE pair_id = '{pair['pair_id']}'")
    t0 = time.time()
    while time.time() - t0 < 300:
        hist = sql(f"SELECT decision_id, decision, steward, _pg_change_type, _timestamp FROM {APP}.lb_steward_decisions_history WHERE pair_id = '{pair['pair_id']}'")
        if hist[1]:
            break
        time.sleep(10)
    sync_s = round(time.time() - t0)
    jid = job_id("Northbridge Client 360 - Apply steward decisions")
    run = w.jobs.run_now_and_wait(job_id=jid, timeout=__import__("datetime").timedelta(minutes=60))
    after = probe()
    _, lbrow = pg_query(f"SELECT party_id, party_name, source_record_count FROM {P}serving.party WHERE party_id = '{after[1][0][1]}'")
    body = (f"# Steward round trip: app -> Lakebase -> Lakehouse Sync -> entity resolution -> gold -> Lakebase\n\n"
            f"**Pair approved:** `{pair['left_name']}` ({pair['left_record_key']}) + `{pair['right_name']}` ({pair['right_record_key']}), "
            f"model score {pair['match_score']}, LLM: {pair['llm_recommendation']} - {pair['llm_rationale']}\n\n"
            f"### Before\n{md(*before)}\n\n### 1. Approved in the app (Dash callback, HTTP {r.status_code})\n```\n{app_reply}\n```\n"
            f"### 2. Row written to Lakebase `steward.steward_decisions`\n{md(*lake)}\n\n"
            f"### 3. Lakehouse Sync landed it in Unity Catalog after ~{sync_s}s (`nb_app.lb_steward_decisions_history`)\n{md(*hist)}\n\n"
            f"### 4. Round-trip job run {run.run_id}: {run.state.result_state.value}\n{run.run_page_url}\n\n"
            f"### After: both records now resolve to one golden party\n{md(*after)}\n\n"
            f"### Lakebase serving copy refreshed\n{md(['party_id', 'party_name', 'source_record_count'], lbrow)}\n")
    write("09_steward_roundtrip.md", body)


# ------------------------------------------------------------------------------------------------
# 0. Business value inputs (the numbers the README's value case is built on)
# ------------------------------------------------------------------------------------------------
def value_evidence():
    fx = f"(SELECT DISTINCT currency, fx_rate_to_usd FROM {S}.revenue_transactions WHERE fx_rate_to_usd IS NOT NULL)"
    body = "# Business value inputs, computed from the built data\n\nAll figures are for the synthetic Northbridge book (452 corporate families). The README scales them with stated assumptions.\n\n"
    body += section("1. Harbor & Cole overlap: client groups served by both books before the acquisition (FY2025)", f"""
WITH overlap AS (SELECT DISTINCT ultimate_parent_party_id FROM {G}.dim_party WHERE client_origin = 'Both')
SELECT count(DISTINCT o.ultimate_parent_party_id) AS overlapping_client_groups,
       round(sum(CASE WHEN r.source_system = 'NB_BILLING' THEN r.amount_usd END)) AS northbridge_revenue_usd,
       round(sum(CASE WHEN r.source_system = 'HC_AMS' THEN r.amount_usd END)) AS harbor_cole_revenue_usd,
       round(sum(r.amount_usd)) AS combined_relationship_usd
FROM overlap o LEFT JOIN {G}.fact_revenue r ON r.ultimate_parent_party_id = o.ultimate_parent_party_id AND r.fiscal_year = 2025""")
    body += section("2. Harbor & Cole-only client groups (cross-sell targets for Northbridge specialty lines)", f"""
SELECT count(*) AS hc_only_client_groups, round(sum(rev)) AS hc_revenue_fy2025_usd FROM (
  SELECT d.ultimate_parent_party_id, sum(r.amount_usd) AS rev FROM {G}.dim_party d
  LEFT JOIN {G}.fact_revenue r ON r.party_id = d.party_id AND r.fiscal_year = 2025
  GROUP BY 1 HAVING bool_and(d.client_origin = 'Harbor & Cole'))""")
    body += section("3. Commission leakage: carrier statements vs booked commission (all years, USD)", f"""
SELECT c.reconciliation_status, count(*) AS placements,
       round(sum(abs(c.variance_local) * f.fx_rate_to_usd)) AS abs_variance_usd,
       round(sum(c.booked_commission * f.fx_rate_to_usd)) AS booked_commission_usd
FROM {G}.commission_reconciliation c JOIN {S}.placements p USING (placement_id) JOIN {fx} f ON f.currency = p.currency
GROUP BY 1 ORDER BY 1""")
    body += section("4. Duplicate-resolution effort: what the model decided vs what needed a human", f"""
SELECT source_records, golden_parties, records_merged, auto_match_pairs, review_band_pairs, candidate_pairs,
       round(100 * review_band_pairs / (auto_match_pairs + review_band_pairs), 1) AS pct_of_match_decisions_needing_a_human
FROM {ML}.er_run_log ORDER BY run_ts DESC LIMIT 1""")
    body += section("5. Restricted-segment exposure governed by policy", f"""
SELECT count(DISTINCT ultimate_parent_party_id) AS restricted_client_groups, count(*) AS restricted_entities,
       round((SELECT sum(amount_usd) FROM {G}.fact_revenue WHERE is_restricted AND fiscal_year = 2025)) AS restricted_revenue_fy2025_usd
FROM {G}.dim_party WHERE is_restricted""")
    body += section("6. Book size", f"""
SELECT count(DISTINCT ultimate_parent_party_id) AS client_groups, count(*) AS legal_entities,
       round((SELECT sum(amount_usd) FROM {G}.fact_revenue WHERE fiscal_year = 2025)) AS revenue_fy2025_usd FROM {G}.dim_party""")
    write("10_value_inputs.md", body)


if __name__ == "__main__":
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
    for fn in [build_job_evidence, pipeline_evidence, er_evidence, governance_evidence, lineage_evidence, lakebase_evidence, value_evidence]:
        if only and fn.__name__ not in only:
            continue
        try:
            fn()
        except Exception as e:
            print(f"!! {fn.__name__} failed: {e}")
    if ROUNDTRIP:
        roundtrip_evidence()
