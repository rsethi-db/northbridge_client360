# Notebook run: 44eddb56-1cc0-4946-9819-1aebcb3e1705

```markdown
%md
# 20 · Unity Catalog governance

* **Tags** - `confidentiality`, `sox_relevant`, `layer`, `certified` + `system.certification_status` (gold only),
  and Databricks data-classification tags (`class.name`, `class.email_address`, `class.phone_number`,
  `class.street_address`) on PII columns. In this account `pii` is a governed tag whose allowed values are
  `ssn`/`address`, so it is applied as `pii=address` on address columns only.
* **Column comments** on every gold column Genie and Discover will surface.
* **Metric view** `gold.client_revenue_metrics` - the single definition of `Total Client Revenue`.
* **Grants** - the app service principal reads gold and nothing else.

* **ABAC policies** on the gold schema - one row-filter policy and one column-mask policy, matched by tags,
  so every current and future gold table tagged the same way is governed without per-table clauses.
```

```python
dbutils.widgets.text("catalog", "richasethi_febar_catalog")
dbutils.widgets.text("schema_prefix", "nb_")
dbutils.widgets.text("app_name", "northbridge-client360")
CATALOG, P = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema_prefix")
try:   # the app's service principal (application id) - granted read on gold only
    from databricks.sdk import WorkspaceClient
    APP_SP = WorkspaceClient().apps.get(dbutils.widgets.get("app_name")).service_principal_client_id
except Exception:
    APP_SP = ""
S = lambda layer: f"{CATALOG}.{P}{layer}"

def sql(stmt):
    try:
        spark.sql(stmt)
    except Exception as e:
        print(f"FAILED: {stmt[:120]}...\n  {str(e)[:300]}")
        raise

def tag(obj, tags, kind="TABLE"):
    kv = ", ".join(f"'{k}' = '{v}'" for k, v in tags.items())
    sql(f"ALTER {kind} {obj} SET TAGS ({kv})")

def col_tag(table, col, tags):
    kv = ", ".join(f"'{k}' = '{v}'" if v is not None else f"'{k}'" for k, v in tags.items())
    sql(f"ALTER TABLE {table} ALTER COLUMN {col} SET TAGS ({kv})")

def is_view(t):
    return spark.sql(f"DESCRIBE TABLE EXTENDED {t}").where("col_name = 'Type'").first()[1] in ("MATERIALIZED_VIEW", "VIEW", "METRIC_VIEW")
```

```markdown
%md ## Table tags
```

```python
REVENUE = {"billing_revenue_transactions", "hc_policies", "revenue_transactions", "fact_revenue", "client_revenue_summary", "commission_reconciliation"}
RESTRICTED = {"crm_contacts", "party_contacts"}
CONFIDENTIAL = {"crm_accounts", "billing_clients", "hc_clients", "placement_insureds", "party_source_records", "dim_party",
                "party_source_xref", "party_hierarchy", "fact_placements", "placements", "placement_placements"} | REVENUE

for layer in ["bronze", "silver", "gold"]:
    for t in spark.sql(f"SHOW TABLES IN {S(layer)}").where("NOT isTemporary").collect():
        name, fq = t.tableName, f"{S(layer)}.{t.tableName}"
        tags = {"layer": layer, "confidentiality": "restricted" if name in RESTRICTED else "confidential" if name in CONFIDENTIAL else "internal"}
        if name in REVENUE:
            tags["sox_relevant"] = "true"
        if layer == "gold":
            tags.update({"certified": "true", "system.certification_status": "certified"})
        elif layer == "silver":
            tags["certified"] = "false"   # deliberately uncertified: one client appears many times here
        tag(fq, tags, "TABLE")
        print("tagged", fq, tags)

for t in ["party_xref", "party_hierarchy", "match_candidates_scored", "match_review_queue", "er_run_log", "llm_match_assessments"]:
    tag(f"{S('ml')}.{t}", {"confidentiality": "confidential", "nb_domain": "entity_resolution"})
for t in spark.sql(f"SHOW TABLES IN {S('app')}").where("NOT isTemporary AND tableName LIKE 'app_%'").collect():
    tag(f"{S('app')}.{t.tableName}", {"confidentiality": "internal", "nb_domain": "app_serving_unrestricted"})
```
**Output:**
```
tagged richasethi_febar_catalog.nb_bronze.billing_clients {'layer': 'bronze', 'confidentiality': 'confidential'}
tagged richasethi_febar_catalog.nb_bronze.billing_revenue_transactions {'layer': 'bronze', 'confidentiality': 'confidential', 'sox_relevant': 'true'}
tagged richasethi_febar_catalog.nb_bronze.carrier_statements_layout_a {'layer': 'bronze', 'confidentiality': 'internal'}
tagged richasethi_febar_catalog.nb_bronze.carrier_statements_layout_b {'layer': 'bronze', 'confidentiality': 'internal'}
tagged richasethi_febar_catalog.nb_bronze.carrier_statements_layout_c {'layer': 'bronze', 'confidentiality': 'internal'}
tagged richasethi_febar_catalog.nb_bronze.crm_accounts {'layer': 'bronze', 'confidentiality': 'confidential'}
tagged richasethi_febar_catalog.nb_bronze.crm_contacts {'layer': 'bronze', 'confidentiality': 'restricted'}
tagged richasethi_febar_catalog.nb_bronze.hc_clients {'layer': 'bronze', 'confidentiality': 'confidential'}
tagged richasethi_febar_catalog.nb_bronze.hc_policies {'layer': 'bronze', 'confidentiality': 'confidential', 'sox_relevant': 'true'}
tagged richasethi_febar_catalog.nb_bronze.le_registry {'layer': 'bronze', 'confidentiality': 'internal'}
tagged richasethi_febar_catalog.nb_bronze.placement_insureds {'layer': 'bronze', 'confidentiality': 'confidential'}
tagged richasethi_febar_catalog.nb_bronze.placement_placements {'layer': 'bronze', 'confidentiality': 'confidential'}
tagged richasethi_febar_catalog.nb_silver.billing_clients {'layer': 'silver', 'confidentiality': 'confidential', 'certified': 'false'}
tagged richasethi_febar_catalog.nb_silver.carrier_statement_lines {'layer': 'silver', 'confidentiality': 'internal', 'certified': 'false'}
tagged richasethi_febar_catalog.nb_silver.crm_accounts {'layer': 'silver', 'confidentiality': 'confidential', 'certified': 'false'}
tagged richasethi_febar_catalog.nb_silver.crm_contacts {'layer': 'silver', 'confidentiality': 'restricted', 'certified': 'false'}
tagged richasethi_febar_catalog.nb_silver.dq_quarantine {'layer': 'silver', 'confidentiality': 'internal', 'certified': 'false'}
tagged richasethi_febar_catalog.nb_silver.hc_clients {'layer': 'silver', 'confidentiality': 'confidential', 'certified': 'false'}
tagged richasethi_febar_catalog.nb_silver.hc_policies {'layer': 'silver', 'confidentiality': 'confidential', 'sox_relevant': 'true', 'certified': 'false'}
tagged richasethi_febar_catalog.nb_silver.le_registry {'layer': 'silver', 'confidentiality': 'internal', 'certified': 'false'}
tagged richasethi_febar_catalog.nb_silver.party_source_records {'layer': 'silver', 'confidentiality': 'confidential', 'certified': 'false'}
tagged richasethi_febar_catalog.nb_silver.placement_insureds {'layer': 'silver', 'confidentiality': 'confidential', 'certified': 'false'}
tagged richasethi_febar_catalog.nb_silver.placements {'layer': 'silver', 'confidentiality': 'confidential', 'certified': 'false'}
tagged richasethi_febar_catalog.nb_silver.revenue_transactions {'layer': 'silver', 'confidentiality': 'confidential', 'sox_relevant': 'true', 'certified': 'false'}
tagged richasethi_febar_catalog.nb_gold.client_revenue_summary {'layer': 'gold', 'confidentiality': 'confidential', 'sox_relevant': 'true', 'certified': 'true', 'system.certification_status': 'certified'}
tagged richasethi_febar_catalog.nb_gold.commission_reconciliation {'layer': 'gold', 'confidentiality': 'confidential', 'sox_relevant': 'true', 'certified': 'true', 'system.certification_status': 'certified'}
tagged richasethi_febar_catalog.nb_gold.dim_party {'layer': 'gold', 'confidentiality': 'confidential', 'certified': 'true', 'system.certification_status': 'certified'}
tagged richasethi_febar_catalog.nb_gold.er_run_history {'layer': 'gold', 'confidentiality': 'internal', 'certified': 'true', 'system.certification_status': 'certified'}
tagged richasethi_febar_catalog.nb_gold.fact_placements {'layer': 'gold', 'confidentiality': 'confidential', 'certified': 'true', 'system.certification_status': 'certified'}
tagged richasethi_febar_catalog.nb_gold.fact_revenue {'layer': 'gold', 'confidentiality': 'confidential', 'sox_relevant': 'true', 'certified': 'true', 'system.certification_status': 'certified'}
tagged richasethi_febar_catalog.nb_gold.party_contacts {'layer': 'gold', 'confidentiality': 'restricted', 'certified': 'true', 'system.certification_status': 'certified'}
tagged richasethi_febar_catalog.nb_gold.party_hierarchy {'layer': 'gold', 'confidentiality': 'confidential', 'certified': 'true', 'system.certification_status': 'certified'}
tagged richasethi_febar_catalog.nb_gold.party_source_xref {'layer': 'gold', 'confidentiality': 'confidential', 'certified': 'true', 'system.certification_status': 'certified'}
```

```markdown
%md ## PII column classification
```

```python
PII_COLUMNS = {
    f"{S('bronze')}.crm_contacts": {"first_name": "class.name", "last_name": "class.name", "email": "class.email_address", "phone": "class.phone_number"},
    f"{S('silver')}.crm_contacts": {"first_name": "class.name", "last_name": "class.name", "email": "class.email_address", "phone": "class.phone_number"},
    f"{S('gold')}.party_contacts": {"contact_name": "class.name", "email": "class.email_address", "phone": "class.phone_number"},
}
ADDRESS_COLUMNS = {f"{S('silver')}.crm_accounts": ["address_line1"], f"{S('silver')}.party_source_records": ["address_line1"],
                   f"{S('gold')}.dim_party": ["address_line1"]}
for table, cols in PII_COLUMNS.items():
    for c, cls in cols.items():
        col_tag(table, c, {cls: None})
for table, cols in ADDRESS_COLUMNS.items():
    for c in cols:
        col_tag(table, c, {"class.street_address": None})   # valueless and key=value tags need separate statements
        col_tag(table, c, {"pii": "address"})
```

```markdown
%md ## ABAC: tag the attributes, then attach two policies to the gold schema
* `nb_hide_restricted_clients` - row filter on every gold table with a column tagged `rls_filter_key`
  (the `is_restricted` flag). Function: `restricted_client_filter` (visible unless restricted, or caller in the restricted group).
* `nb_mask_contact_pii` - column mask on every gold column classified `class.name`, `class.email_address` or `class.phone_number`.

New tag policies cannot be created in this account (tag policy limit reached), so the policies match the existing
governed key `rls_filter_key` and Databricks' system `class.*` classification tags.
```

```python
G = S("gold")
for t in spark.sql(f"SHOW TABLES IN {G}").where("NOT isTemporary").collect():
    cols = [c.col_name for c in spark.sql(f"DESCRIBE TABLE {G}.{t.tableName}").collect()]
    if "is_restricted" in cols:
        col_tag(f"{G}.{t.tableName}", "is_restricted", {"rls_filter_key": None})
        print("rls_filter_key ->", t.tableName)

sql(f"""CREATE OR REPLACE POLICY nb_hide_restricted_clients ON SCHEMA {G}
COMMENT 'Restricted client segment (defence, sovereign & government) is visible only to the restricted-clients group. Applies to every gold table whose restriction flag is tagged rls_filter_key.'
ROW FILTER {G}.restricted_client_filter
TO `account users`
FOR TABLES
MATCH COLUMNS has_tag('rls_filter_key') AS restricted_flag
USING COLUMNS (restricted_flag)""")
for cls in ["class.name", "class.email_address", "class.phone_number"]:
    sql(f"""CREATE OR REPLACE POLICY nb_mask_{cls.split('.')[1]} ON SCHEMA {G}
COMMENT 'Client contact PII ({cls}) is masked for everyone outside the PII readers group.'
COLUMN MASK {G}.mask_pii
TO `account users`
FOR TABLES
MATCH COLUMNS has_tag('{cls}') AS pii_col
ON COLUMN pii_col""")
display(spark.sql(f"SHOW POLICIES ON SCHEMA {G}"))
```
**Output:**
```
rls_filter_key -> client_revenue_summary
rls_filter_key -> commission_reconciliation
rls_filter_key -> dim_party
rls_filter_key -> fact_placements
rls_filter_key -> fact_revenue
rls_filter_key -> party_contacts
rls_filter_key -> party_hierarchy
rls_filter_key -> party_source_xref
```

```markdown
%md ## Gold column comments (feed Genie and Discover)
```

```python
COLUMN_COMMENTS = {
    "dim_party": {
        "party_id": "Golden party identifier assigned by entity resolution. Stable across runs.",
        "party_name": "Survivored legal name (registry name first, then Northbridge CRM, billing, placement platform, Harbor & Cole).",
        "country_iso": "ISO 3166-1 alpha-2 country of the legal entity.",
        "registration_number": "Company registration / tax number of the legal entity.",
        "industry": "Client industry.",
        "client_segment": "Northbridge client segment: Global Corporate, Large Corporate, Middle Market.",
        "is_restricted": "TRUE for the Restricted segment (defence, sovereign & government clients). Rows are hidden by row filter unless the user is in the restricted group.",
        "account_executive": "Northbridge account executive (or Harbor & Cole producer) responsible for the client.",
        "parent_party_id": "Direct parent legal entity (golden party_id).",
        "ultimate_parent_party_id": "Ultimate parent of the corporate family. Roll revenue up to this to answer 'total relationship with a client'.",
        "ultimate_parent_name": "Name of the ultimate parent - use this as the client name when the question is about a client group.",
        "hierarchy_level": "0 = ultimate parent, 1 = regional holding company / direct subsidiary, 2+ = operating subsidiary.",
        "is_ultimate_parent": "TRUE if this party is the top of its corporate family.",
        "source_systems": "Source systems that hold a record for this party: NB_CRM, NB_BILLING, NB_PLACEMENT, HC_AMS (Harbor & Cole).",
        "source_record_count": "Number of source-system records unified into this golden record.",
        "in_harbor_cole": "TRUE if the acquired Harbor & Cole agency holds a record for this party.",
        "client_origin": "Northbridge (Northbridge systems only), Harbor & Cole (acquired agency only) or Both (overlap - client served by both before the acquisition).",
        "min_match_confidence": "Lowest model match confidence among the records merged into this party.",
        "has_steward_override": "TRUE if a data steward approved or split a match for this party.",
    },
    "fact_revenue": {
        "revenue_id": "Unique revenue line id.",
        "source_system": "NB_BILLING (Northbridge billing) or HC_AMS (Harbor & Cole AMS).",
        "party_id": "Golden party that was billed.",
        "ultimate_parent_party_id": "Ultimate parent of the billed party - roll up to this for client-group revenue.",
        "revenue_type": "Commission, Fee, or Commission Adjustment (return commission / mid-term adjustments, negative).",
        "revenue_category": "Commission or Fee. Commission adjustments are counted as Commission.",
        "line_of_business": "Insurance line of business, e.g. Property, Casualty, D&O, Cyber, Marine Cargo.",
        "carrier_name": "Insurance carrier the business was placed with.",
        "revenue_date": "Date the fee or commission income was recognized.",
        "fiscal_year": "Northbridge fiscal year (= calendar year).",
        "amount_original": "Amount in the original invoice currency.",
        "amount_usd": "Fee or commission income in USD at finance planning rates. This is broker revenue. Never premium.",
    },
    "fact_placements": {
        "placement_id": "Placement / policy identifier.",
        "line_of_business": "Insurance line of business.",
        "carrier_name": "Insurance carrier.",
        "inception_date": "Policy inception date.",
        "expiry_date": "Policy expiry date.",
        "is_in_force": "TRUE if today is between inception and expiry.",
        "broker_of_record": "Broker of record (Northbridge broker or Harbor & Cole producer).",
        "remuneration_basis": "Commission, Fee, or Commission + Fee.",
        "commission_rate": "Commission rate as a ratio (0.125 = 12.5%).",
        "gwp_usd": "Gross written premium in USD - reference only, this is the client's premium, NOT broker revenue.",
    },
    "client_revenue_summary": {
        "total_revenue_usd": "Fee + commission income in USD for the party and fiscal year. Sums to the metric view Total Client Revenue.",
        "commission_income_usd": "Commission income in USD (net of adjustments).",
        "fee_income_usd": "Fee income in USD.",
    },
}
for table, cols in COLUMN_COMMENTS.items():
    for c, txt in cols.items():
        sql(f"COMMENT ON COLUMN {S('gold')}.{table}.{c} IS '{txt.replace(chr(39), chr(39) * 2)}'")
```

```markdown
%md ## Metric view: the one definition of client revenue
```

```python
sql(f"""
CREATE OR REPLACE VIEW {G}.client_revenue_metrics
WITH METRICS
LANGUAGE YAML
COMMENT 'Certified definition of Northbridge client revenue. Total Client Revenue = SUM of fee and commission income in USD (net of commission adjustments) from gold.fact_revenue, across Northbridge billing and the Harbor & Cole AMS. Premium is never revenue. Subsidiaries roll up to the Ultimate Parent Client. Fiscal year = calendar year. Finance, placement, the Client 360 app and Genie all use this definition.'
AS $$
version: 1.1
comment: "Northbridge client revenue (fee + commission income, USD). Roll up to Ultimate Parent Client for total relationship."
source: {G}.fact_revenue
joins:
  - name: dim_client
    source: {G}.dim_party
    'on': source.party_id = dim_client.party_id
  - name: dim_ultimate_parent
    source: {G}.dim_party
    'on': source.ultimate_parent_party_id = dim_ultimate_parent.party_id
dimensions:
  - name: Ultimate Parent Client
    expr: dim_ultimate_parent.party_name
    comment: "Top of the corporate family. Default level for 'client' questions."
    synonyms: [client, client group, parent client, account, customer, group]
  - name: Ultimate Parent Party ID
    expr: source.ultimate_parent_party_id
  - name: Billed Entity
    expr: dim_client.party_name
    comment: "Legal entity that was billed (subsidiary level)."
    synonyms: [legal entity, subsidiary, entity]
  - name: Billed Party ID
    expr: source.party_id
  - name: Client Country
    expr: dim_ultimate_parent.country_iso
    synonyms: [country, headquarters country]
  - name: Client Segment
    expr: dim_ultimate_parent.client_segment
    synonyms: [segment]
  - name: Industry
    expr: dim_ultimate_parent.industry
  - name: Client Origin
    expr: dim_ultimate_parent.client_origin
    comment: "Northbridge, Harbor & Cole, or Both."
  - name: Account Executive
    expr: dim_ultimate_parent.account_executive
    synonyms: [AE, account manager]
  - name: Revenue Source System
    expr: source.source_system
  - name: Revenue Category
    expr: source.revenue_category
    comment: "Commission or Fee."
  - name: Line of Business
    expr: source.line_of_business
    synonyms: [LOB, line, coverage]
  - name: Carrier
    expr: source.carrier_name
    synonyms: [insurer, market, underwriter]
  - name: Fiscal Year
    expr: source.fiscal_year
    synonyms: [year, FY]
  - name: Fiscal Quarter
    expr: source.fiscal_quarter
  - name: Revenue Month
    expr: "DATE_TRUNC('MONTH', source.revenue_date)"
measures:
  - name: Total Client Revenue
    expr: SUM(source.amount_usd)
    comment: "Fee + commission income in USD, net of commission adjustments. THE definition of client revenue."
    synonyms: [revenue, total revenue, income, total relationship, brokerage revenue, fee and commission income]
    format:
      type: currency
      currency_code: USD
      decimal_places: {{type: exact, places: 2}}
  - name: Commission Income
    expr: SUM(source.amount_usd) FILTER (WHERE source.revenue_category = 'Commission')
    synonyms: [commission, commissions, brokerage]
    format:
      type: currency
      currency_code: USD
      decimal_places: {{type: exact, places: 2}}
  - name: Fee Income
    expr: SUM(source.amount_usd) FILTER (WHERE source.revenue_category = 'Fee')
    synonyms: [fees, fee revenue]
    format:
      type: currency
      currency_code: USD
      decimal_places: {{type: exact, places: 2}}
  - name: Billed Entity Count
    expr: COUNT(DISTINCT source.party_id)
  - name: Carrier Count
    expr: COUNT(DISTINCT source.carrier_name)
$$
""")
tag(f"{G}.client_revenue_metrics", {"certified": "true", "system.certification_status": "certified", "sox_relevant": "true",
                                     "confidentiality": "confidential"}, "VIEW")
```

```markdown
%md ## Grants: app service principal reads gold only
```

```python
if APP_SP:
    sql(f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{APP_SP}`")
    sql(f"GRANT USE SCHEMA, SELECT, EXECUTE ON SCHEMA {S('gold')} TO `{APP_SP}`")
    print(f"granted gold read to {APP_SP}")
else:
    print("no app service principal yet - grants applied after the app is deployed")
display(spark.sql(f"SHOW GRANTS ON SCHEMA {S('gold')}"))
```
**Output:**
```
granted gold read to a7f42769-5583-4060-a22f-b83d50f384d9
```
