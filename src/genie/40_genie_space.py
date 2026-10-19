# Databricks notebook source
# MAGIC %md
# MAGIC # 40 · Genie space: "Northbridge Client 360"
# MAGIC
# MAGIC Points only at certified gold assets and the `client_revenue_metrics` metric view (never bronze or silver).
# MAGIC Business logic that must be answered the same way every time lives in **trusted UC SQL functions**; the
# MAGIC metric view owns the definition of revenue. Created or updated in place (matched by title), so re-runs are safe.

# COMMAND ----------

dbutils.widgets.text("catalog", "richasethi_febar_catalog")
dbutils.widgets.text("schema_prefix", "nb_")
dbutils.widgets.text("warehouse_id", "f4edbf03911f5f8e")
dbutils.widgets.text("title", "Northbridge Client 360")
CATALOG, P = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema_prefix")
WAREHOUSE, TITLE = dbutils.widgets.get("warehouse_id"), dbutils.widgets.get("title")
G = f"{CATALOG}.{P}gold"
MV = f"{G}.client_revenue_metrics"

# COMMAND ----------

# MAGIC %md ## Trusted assets: UC SQL functions

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {G}.client_total_revenue(p_client_name STRING, p_fiscal_year INT DEFAULT NULL)
RETURNS TABLE (ultimate_parent_client STRING, ultimate_parent_party_id STRING, fiscal_year INT, total_client_revenue_usd DECIMAL(38,2),
               commission_income_usd DECIMAL(38,2), fee_income_usd DECIMAL(38,2), billed_entity_count BIGINT)
COMMENT 'Trusted: total fee + commission revenue with a client group across ALL its legal entities (rolled up to the ultimate parent), per fiscal year, from the certified metric view client_revenue_metrics. p_client_name matches the ultimate parent client name (case-insensitive, partial); for a subsidiary name, look up its ultimate_parent_name in dim_party first. p_fiscal_year NULL = every year.'
RETURN
  SELECT `Ultimate Parent Client`, `Ultimate Parent Party ID`, `Fiscal Year`, MEASURE(`Total Client Revenue`), MEASURE(`Commission Income`),
         MEASURE(`Fee Income`), MEASURE(`Billed Entity Count`)
  FROM {MV}
  WHERE lower(`Ultimate Parent Client`) LIKE concat('%', lower(p_client_name), '%')
    AND (p_fiscal_year IS NULL OR `Fiscal Year` = p_fiscal_year)
  GROUP BY ALL
""")

spark.sql(f"""
CREATE OR REPLACE FUNCTION {G}.harbor_cole_overlap_clients()
RETURNS TABLE (ultimate_parent_client STRING, ultimate_parent_party_id STRING, overlapping_entity STRING, party_id STRING, country_iso STRING,
               source_systems ARRAY<STRING>, northbridge_revenue_prior_fy_usd DECIMAL(38,2), harbor_cole_revenue_prior_fy_usd DECIMAL(38,2))
COMMENT 'Trusted: acquired Harbor & Cole clients that overlap existing Northbridge clients - golden parties held in the Harbor & Cole AMS AND at least one Northbridge system (client_origin = Both), with each book''s revenue in the prior fiscal year.'
RETURN
  WITH rev AS (
    SELECT party_id,
           sum(CASE WHEN source_system = 'NB_BILLING' THEN amount_usd ELSE 0 END) AS nb_rev,
           sum(CASE WHEN source_system = 'HC_AMS' THEN amount_usd ELSE 0 END) AS hc_rev
    FROM {G}.fact_revenue WHERE fiscal_year = year(current_date()) - 1 GROUP BY party_id)
  SELECT d.ultimate_parent_name, d.ultimate_parent_party_id, d.party_name, d.party_id, d.country_iso, d.source_systems,
         coalesce(r.nb_rev, 0), coalesce(r.hc_rev, 0)
  FROM {G}.dim_party d LEFT JOIN rev r USING (party_id)
  WHERE d.client_origin = 'Both'
""")

spark.sql(f"""
CREATE OR REPLACE FUNCTION {G}.clients_by_carrier_count(p_min_carriers INT DEFAULT 4)
RETURNS TABLE (ultimate_parent_client STRING, ultimate_parent_party_id STRING, carrier_count BIGINT, in_force_placements BIGINT, carriers ARRAY<STRING>)
COMMENT 'Trusted: clients (rolled up to the ultimate parent) whose IN-FORCE placements are spread across at least p_min_carriers distinct carriers. "More than three carriers" = p_min_carriers 4.'
RETURN
  SELECT d.ultimate_parent_name, p.ultimate_parent_party_id, count(DISTINCT p.carrier_name), count(*), sort_array(collect_set(p.carrier_name))
  FROM {G}.fact_placements p JOIN {G}.dim_party d ON d.party_id = p.ultimate_parent_party_id
  WHERE p.is_in_force
  GROUP BY ALL
  HAVING count(DISTINCT p.carrier_name) >= p_min_carriers
""")

spark.sql(f"""
CREATE OR REPLACE FUNCTION {G}.latest_entity_resolution_run()
RETURNS TABLE (run_ts TIMESTAMP, source_records BIGINT, golden_parties BIGINT, records_merged BIGINT, multi_system_parties BIGINT,
               auto_match_pairs BIGINT, review_band_pairs BIGINT, steward_decisions_applied BIGINT, model_version BIGINT,
               pairwise_precision DOUBLE, pairwise_recall DOUBLE)
COMMENT 'Trusted: the most recent entity resolution run. records_merged = source records folded into another record''s golden party (source_records - golden_parties).'
RETURN
  SELECT run_ts, source_records, golden_parties, records_merged, multi_system_parties, auto_match_pairs, review_band_pairs,
         steward_decisions_applied, model_version, pairwise_precision, pairwise_recall
  FROM {G}.er_run_history WHERE is_latest_run
""")
print("trusted functions created")

# COMMAND ----------

# MAGIC %md ## Space definition

# COMMAND ----------

import hashlib, json

def hid(s):   # deterministic 32-hex ids so re-runs produce an identical definition
    return hashlib.md5(s.encode()).hexdigest()

INSTRUCTIONS = [
    "You are the Client 360 assistant for Northbridge Risk Partners, a global insurance broker that acquired the regional agency Harbor & Cole in 2026.",
    "CLIENT: a client is a corporate family. Unless the user names a specific legal entity or subsidiary, answer at the ULTIMATE PARENT level (Ultimate Parent Client / ultimate_parent_party_id) and roll all subsidiaries up to it.",
    "REVENUE: broker revenue means FEE AND COMMISSION INCOME in USD, net of commission adjustments. Always use the metric view client_revenue_metrics measure `Total Client Revenue` (or Commission Income / Fee Income). Never use premium or gwp_usd as revenue; GWP is the client's insurance spend, not Northbridge income.",
    "FISCAL YEAR: Northbridge fiscal year = calendar year. 'This year' means the current fiscal year to date; 'last year' means the prior full fiscal year.",
    "RETENTION: a client is retained in fiscal year Y if it had Total Client Revenue > 0 in both Y-1 and Y. Retention rate = retained clients / clients with revenue in Y-1.",
    "HARBOR & COLE: 'acquired clients' or 'Harbor & Cole clients' are golden parties whose source_systems include HC_AMS. Overlap with Northbridge = client_origin 'Both'. Use the function harbor_cole_overlap_clients for overlap questions.",
    "Use the trusted functions when they fit: client_total_revenue(p_client_name, p_fiscal_year) for a client's total relationship; clients_by_carrier_count(p_min_carriers) for carrier spread (more than N carriers -> p_min_carriers = N+1); latest_entity_resolution_run() for questions about merges or the entity resolution model.",
    "Restricted clients (defence, sovereign and government) are governed by Unity Catalog policy. If a client is not visible, say it may be restricted; never guess its figures.",
    "Format money as USD with thousands separators. When ranking clients, show the ultimate parent name, not a party id.",
]
SAMPLE_QUESTIONS = [
    "What's our total revenue with Kestrel Industries plc across all entities?",
    "Which acquired Harbor & Cole clients overlap with existing Northbridge clients?",
    "Top 10 clients by commission income this year, rolled up to parent",
    "Which clients have placements with more than three carriers?",
    "How many party records were merged by the entity resolution model last run?",
]
EXAMPLE_SQL = [
    ("What's our total revenue with Kestrel Industries plc across all entities?",
     f"SELECT * FROM {G}.client_total_revenue('Kestrel Industries plc') ORDER BY fiscal_year"),
    ("Top 10 clients by commission income this year, rolled up to parent",
     f"SELECT `Ultimate Parent Client`, MEASURE(`Commission Income`) AS commission_income_usd, MEASURE(`Total Client Revenue`) AS total_client_revenue_usd\n"
     f"FROM {MV}\nWHERE `Fiscal Year` = year(current_date())\nGROUP BY ALL\nORDER BY commission_income_usd DESC\nLIMIT 10"),
    ("Which acquired Harbor & Cole clients overlap with existing Northbridge clients?",
     f"SELECT * FROM {G}.harbor_cole_overlap_clients() ORDER BY northbridge_revenue_prior_fy_usd + harbor_cole_revenue_prior_fy_usd DESC"),
    ("Which clients have placements with more than three carriers?",
     f"SELECT * FROM {G}.clients_by_carrier_count(4) ORDER BY carrier_count DESC, in_force_placements DESC"),
    ("How many party records were merged by the entity resolution model last run?",
     f"SELECT records_merged, source_records, golden_parties, run_ts FROM {G}.latest_entity_resolution_run()"),
    ("What is our client retention rate this year?",
     f"WITH r AS (SELECT `Ultimate Parent Party ID` AS client, `Fiscal Year` AS fy, MEASURE(`Total Client Revenue`) AS rev FROM {MV} GROUP BY ALL)\n"
     f"SELECT count_if(cur.rev > 0) / count(*) AS retention_rate, count_if(cur.rev > 0) AS retained_clients, count(*) AS prior_year_clients\n"
     f"FROM r prev LEFT JOIN r cur ON cur.client = prev.client AND cur.fy = prev.fy + 1\nWHERE prev.fy = year(current_date()) - 1 AND prev.rev > 0"),
]
TABLES = {
    f"{G}.dim_party": [("client_origin", True), ("client_segment", True), ("country_iso", True), ("industry", True), ("party_name", True), ("ultimate_parent_name", True)],
    f"{G}.party_hierarchy": [("ultimate_parent_name", True)],
    f"{G}.fact_placements": [("carrier_name", True), ("line_of_business", True)],
    f"{G}.party_source_xref": [("source_system", True)],
    f"{G}.er_run_history": [],
}

space = {
    "version": 2,
    "config": {"sample_questions": sorted([{"id": hid("sq" + q), "question": [q]} for q in SAMPLE_QUESTIONS], key=lambda x: x["id"])},
    "data_sources": {
        "tables": sorted([{"identifier": t, **({"column_configs": sorted([{"column_name": c, "enable_entity_matching": em, "enable_format_assistance": True}
                                                                          for c, em in cols], key=lambda x: x["column_name"])} if cols else {})}
                          for t, cols in TABLES.items()], key=lambda x: x["identifier"]),
        "metric_views": [{"identifier": MV}],
    },
    "instructions": {
        "text_instructions": [{"id": hid("instructions"), "content": [i + "\n" for i in INSTRUCTIONS]}],
        "example_question_sqls": sorted([{"id": hid("ex" + q), "question": [q], "sql": [s]} for q, s in EXAMPLE_SQL], key=lambda x: x["id"]),
        "sql_functions": sorted([{"id": hid("fn" + f), "identifier": f"{G}.{f}"} for f in
                                 ["client_total_revenue", "harbor_cole_overlap_clients", "clients_by_carrier_count", "latest_entity_resolution_run"]], key=lambda x: x["id"]),
    },
    "benchmarks": {"questions": sorted([{"id": hid("bm" + q), "question": [q], "answer": [{"format": "SQL", "content": [s]}]} for q, s in EXAMPLE_SQL[:5]],
                                       key=lambda x: x["id"])},
}
DESCRIPTION = ("Ask about Northbridge clients in plain English: total fee & commission revenue rolled up to the parent client, legal-entity "
               "hierarchies, placements by line and carrier, Harbor & Cole overlap, and entity resolution results. Certified gold data only; "
               "restricted clients are governed by Unity Catalog ABAC policy.")

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
api = w.api_client.do
me = w.current_user.me().user_name
parent = f"/Workspace/Users/{me}/northbridge_client360"
w.workspace.mkdirs(parent)

existing, token = [], None
while True:
    page = api("GET", "/api/2.0/genie/spaces", query={"page_token": token} if token else None)
    existing += [s for s in (page.get("spaces") or []) if s.get("title") == TITLE]
    token = page.get("next_page_token")
    if not token:
        break
body = {"warehouse_id": WAREHOUSE, "title": TITLE, "description": DESCRIPTION, "serialized_space": json.dumps(space)}
if existing:
    space_id = existing[0]["space_id"]
    api("PATCH", f"/api/2.0/genie/spaces/{space_id}", body=body)
    print("updated", space_id)
else:
    space_id = api("POST", "/api/2.0/genie/spaces", body={**body, "parent_path": parent})["space_id"]
    print("created", space_id)
# Share with workspace users so the app's on-behalf-of Genie calls work for every AE, not only the owner.
# Data access is still decided per user by Unity Catalog (ABAC) when Genie runs their query.
api("PATCH", f"/api/2.0/permissions/genie/{space_id}", body={"access_control_list": [{"group_name": "users", "permission_level": "CAN_RUN"}]})
spark.sql(f"CREATE TABLE IF NOT EXISTS {CATALOG}.{P}app.app_config (key STRING, value STRING) COMMENT 'Client 360 app configuration written by setup jobs.'")
spark.sql(f"MERGE INTO {CATALOG}.{P}app.app_config t USING (SELECT 'genie_space_id' AS key, '{space_id}' AS value) s ON t.key = s.key "
          "WHEN MATCHED THEN UPDATE SET value = s.value WHEN NOT MATCHED THEN INSERT *")
dbutils.notebook.exit(space_id)
