# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Catalog setup
# MAGIC Creates the six Northbridge schemas, the raw landing Volume, and the governance functions
# MAGIC (row filter + column masks) that the gold pipeline binds to its tables. Idempotent.

# COMMAND ----------

dbutils.widgets.text("catalog", "richasethi_febar_catalog")
dbutils.widgets.text("schema_prefix", "nb_")
dbutils.widgets.text("restricted_group", "northbridge_restricted_clients")
dbutils.widgets.text("pii_group", "northbridge_pii_readers")
dbutils.widgets.text("steward_group", "northbridge_data_stewards")

CATALOG = dbutils.widgets.get("catalog")
P = dbutils.widgets.get("schema_prefix")
RESTRICTED_GROUP = dbutils.widgets.get("restricted_group")
PII_GROUP = dbutils.widgets.get("pii_group")
STEWARD_GROUP = dbutils.widgets.get("steward_group")

# COMMAND ----------

schemas = {
    "raw": "Raw drop zone. Files exactly as they arrive from Northbridge CRM, billing, placement platform, Harbor & Cole AMS, carrier commission statements and the legal-entity registry feed.",
    "bronze": "Bronze: append-only Auto Loader ingest of the raw drop zone, one table per source feed, no business rules applied.",
    "silver": "Silver: standardized, validated source records (names, countries, registration numbers, currencies normalized). Not certified - use gold for reporting.",
    "gold": "Gold: certified Client 360 assets - golden party record, legal-entity hierarchy, fee & commission revenue, placements. The only schema exposed to Genie and the Client 360 app.",
    "ml": "Entity resolution: candidate pairs, match model features and scores, LLM review assist, cluster assignments and run log.",
    "app": "Client 360 app layer: unrestricted serving projections (app_*) synced to Lakebase, and steward decisions landed back from Lakebase by Lakehouse Sync.",
    "serving": "Lakebase synced tables (UC side). Each is a managed copy of an app_* serving projection, queryable in Postgres schema nb_serving by the Client 360 app.",
}
for s, comment in schemas.items():
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{P}{s} COMMENT '{comment}'")

spark.sql(f"""CREATE VOLUME IF NOT EXISTS {CATALOG}.{P}raw.landing
COMMENT 'Raw drop zone for all source-system extracts. Subfolders: crm/, billing/, placement/, harbor_cole/, carrier_statements/, reference/. _labels/ holds synthetic steward-labelled match history used to train the entity resolution model.'""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Governance functions (used by the ABAC policies created in governance/20_governance.py)
# MAGIC * `restricted_client_filter` - row filter: the Restricted segment (defence & government clients) is
# MAGIC   only visible to members of the restricted group. Workspace-local groups are used here, so the
# MAGIC   function uses `is_member()`.
# MAGIC * `mask_pii` - column mask for contact names, emails and phone numbers.

# COMMAND ----------

# Groups (workspace-local; created if missing). The job owner joins the restricted group (pipelines and the presenter see
# the full book) and the data stewards group (may record match decisions in the app); nobody joins PII readers by default.
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import iam

w = WorkspaceClient()
me = w.current_user.me()
for gname in [RESTRICTED_GROUP, PII_GROUP, STEWARD_GROUP]:
    existing = list(w.groups.list(filter=f'displayName eq "{gname}"'))
    g = existing[0] if existing else w.groups.create(display_name=gname)
    if gname in (RESTRICTED_GROUP, STEWARD_GROUP) and not any(m.value == me.id for m in (w.groups.get(g.id).members or [])):
        w.groups.patch(g.id, operations=[iam.Patch(op=iam.PatchOp.ADD, path="members", value=[{"value": me.id}])],
                       schemas=[iam.PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP])
    print("group ready:", gname)

gov = f"{CATALOG}.{P}gold"
spark.sql(f"""
CREATE OR REPLACE FUNCTION {gov}.restricted_client_filter(is_restricted BOOLEAN)
RETURNS BOOLEAN
COMMENT 'Row filter: rows for Restricted-segment clients (defence, sovereign & government) are only returned to members of {RESTRICTED_GROUP}.'
RETURN NOT coalesce(is_restricted, false) OR is_member('{RESTRICTED_GROUP}')
""")
spark.sql(f"""
CREATE OR REPLACE FUNCTION {gov}.mask_pii(val STRING)
RETURNS STRING
COMMENT 'Column mask: client contact PII is shown only to members of {PII_GROUP}; everyone else sees a redacted value.'
RETURN CASE WHEN is_member('{PII_GROUP}') THEN val
            WHEN val IS NULL THEN NULL
            WHEN val LIKE '%@%' THEN concat('***@', split_part(val, '@', 2))
            ELSE '*** REDACTED ***' END
""")
print("setup complete")
