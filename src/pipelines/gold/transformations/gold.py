"""Gold: certified Client 360 assets built on the entity resolution output.

Access control is attribute-based (ABAC), applied by schema-level policies on the gold schema (see
governance/20_governance.py), not by per-table clauses here:
  * every client-level table carries `is_restricted`, tagged `rls_filter_key` -> row filter policy hides the Restricted
    segment (defence & government clients) from anyone outside the restricted group;
  * contact columns tagged `class.name` / `class.email_address` / `class.phone_number` -> column mask policy.

Pipelines evaluate ABAC policies as the pipeline owner at refresh time, so no gold table reads another gold table:
everything is built from silver / ml through private temporary views. That keeps stored gold data complete regardless
of the refreshing identity's entitlements.

The `app_*` tables published to the app schema are the unrestricted, PII-free serving projection synced to Lakebase
(Lakebase cannot sync tables protected by row filters, masks or ABAC policies).
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F

CAT = spark.conf.get("catalog")
P = spark.conf.get("schema_prefix")
SILVER, ML, GOLD = f"{CAT}.{P}silver", f"{CAT}.{P}ml", f"{CAT}.{P}gold"
APP = f"{CAT}.{P}app"
GOLD_PROPS = {"layer": "gold", "certified": "true"}

HC_LOB = {"PROP": "Property", "GL": "Casualty", "DO": "D&O", "CYB": "Cyber", "MCGO": "Marine Cargo", "MHUL": "Marine Hull",
          "PL": "Product Liability", "PI": "Professional Indemnity", "TCR": "Trade Credit", "ENV": "Environmental Liability",
          "PRI": "Political Risk", "CAR": "Construction All Risks", "TERR": "Terrorism", "TEO": "Technology E&O",
          "ENUP": "Energy Upstream", "AVN": "Aviation Hull & Liability", "FIB": "Financial Institutions Bond",
          "PRC": "Product Recall", "CTL": "Clinical Trials"}
HC_LOB_SQL = "CASE lob_code " + " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in HC_LOB.items()) + " ELSE lob_code END"


# ------------------------------------------------------------------------------------------------
# Private building blocks (not published)
# ------------------------------------------------------------------------------------------------
@dp.temporary_view(name="party_members")
def party_members():
    return spark.sql(f"""
      SELECT x.party_id, x.record_key, x.match_method, x.match_confidence, r.*,
             CASE r.source_system WHEN 'NB_CRM' THEN 1 WHEN 'NB_BILLING' THEN 2 WHEN 'NB_PLACEMENT' THEN 3 ELSE 4 END AS source_priority,
             g.legal_name AS registry_legal_name, g.registration_number AS registry_registration_number,
             g.country_iso AS registry_country, g.address_line1 AS registry_address_line1, g.city AS registry_city, g.lei
      FROM {ML}.party_xref x
      JOIN {SILVER}.party_source_records r ON x.record_key = concat(r.source_system, ':', r.source_record_id)
      LEFT JOIN {SILVER}.le_registry g ON r.registration_number_norm = g.registration_number_norm AND r.country_iso = g.country_iso
    """)


@dp.temporary_view(name="party_attributes")
def party_attributes():
    """Survivorship: registry facts win, then NB CRM, billing, placement platform, Harbor & Cole."""
    return spark.sql(f"""
      WITH ranked AS (
        SELECT *, row_number() OVER (PARTITION BY party_id
                    ORDER BY registry_legal_name IS NULL, source_priority, source_name = upper(source_name), length(source_name) DESC) AS rn
        FROM party_members),
      agg AS (
        SELECT party_id,
          max_by(registry_legal_name, registry_legal_name IS NOT NULL) AS registry_name,
          max_by(registry_registration_number, registry_registration_number IS NOT NULL) AS registry_reg,
          max_by(registry_country, registry_country IS NOT NULL) AS registry_country,
          max_by(lei, lei IS NOT NULL) AS lei,
          mode(country_iso) AS country_mode, mode(registration_number) AS reg_mode,
          max_by(industry, CASE WHEN source_system = 'NB_CRM' THEN 3 WHEN source_system = 'HC_AMS' THEN 2 WHEN industry IS NOT NULL THEN 1 ELSE 0 END) AS industry,
          max_by(client_segment, client_segment IS NOT NULL) AS client_segment,
          max_by(account_executive, CASE WHEN source_system = 'NB_CRM' THEN 2 WHEN account_executive IS NOT NULL THEN 1 ELSE 0 END) AS account_executive,
          -- Restricted if any source flags it OR the party is in the Defence & Government industry (policy rule, so an
          -- unflagged record that entity resolution has not yet linked to its restricted parent can never leak)
          bool_or(coalesce(is_restricted_flag, false) OR regexp_replace(lower(coalesce(industry, '')), '[^a-z]', '') = 'defencegovernment') AS record_restricted,
          sort_array(collect_set(source_system)) AS source_systems,
          count(*) AS source_record_count,
          min(match_confidence) AS min_match_confidence,
          bool_or(match_method LIKE 'steward%') AS has_steward_override
        FROM party_members GROUP BY party_id)
      SELECT a.party_id,
             coalesce(a.registry_name, r.source_name) AS party_name,
             coalesce(a.registry_country, a.country_mode) AS country_iso,
             coalesce(a.registry_reg, a.reg_mode) AS registration_number, a.lei,
             coalesce(r.registry_address_line1, r.address_line1) AS address_line1, initcap(coalesce(r.registry_city, r.city)) AS city,
             initcap(a.industry) AS industry, a.client_segment, a.account_executive, a.record_restricted,
             a.source_systems, size(a.source_systems) AS source_system_count, a.source_record_count,
             a.min_match_confidence, a.has_steward_override,
             h.parent_party_id, h.ultimate_parent_party_id, h.hierarchy_level, h.hierarchy_path, h.parent_link_source
      FROM agg a JOIN ranked r ON a.party_id = r.party_id AND r.rn = 1
      JOIN {ML}.party_hierarchy h ON a.party_id = h.party_id
    """)


@dp.temporary_view(name="party_family")
def party_family():
    """Restricted status is a family-level decision: if any entity in a corporate family is restricted, the family is."""
    return spark.sql("""
      WITH fam AS (SELECT ultimate_parent_party_id, bool_or(record_restricted) AS family_restricted,
                          max(coalesce(client_segment, '')) AS family_segment
                   FROM party_attributes GROUP BY ultimate_parent_party_id)
      SELECT p.*, f.family_restricted AS is_restricted, coalesce(p.client_segment, nullif(f.family_segment, ''), 'Unassigned') AS segment,
             up.party_name AS ultimate_parent_name, pp.party_name AS parent_party_name
      FROM party_attributes p JOIN fam f USING (ultimate_parent_party_id)
      JOIN party_attributes up ON p.ultimate_parent_party_id = up.party_id
      LEFT JOIN party_attributes pp ON p.parent_party_id = pp.party_id
    """)


# ------------------------------------------------------------------------------------------------
# Certified gold assets
# ------------------------------------------------------------------------------------------------
@dp.materialized_view(name="dim_party", table_properties=GOLD_PROPS, comment=(
    "Golden party record: one row per resolved real-world client legal entity, unified by entity resolution from the "
    "Northbridge CRM, Northbridge billing, the placement platform and the Harbor & Cole AMS. A 'client' for reporting is "
    "normally the ultimate parent (ultimate_parent_party_id); subsidiaries roll up to it. Restricted-segment rows are filtered by row filter."))
def dim_party():
    return spark.sql("""
      SELECT party_id, party_name, country_iso, registration_number, lei, address_line1, city, industry,
             segment AS client_segment, is_restricted, account_executive,
             parent_party_id, parent_party_name, ultimate_parent_party_id, ultimate_parent_name, hierarchy_level,
             hierarchy_level = 0 AS is_ultimate_parent, hierarchy_path, parent_link_source,
             source_systems, source_system_count, source_record_count,
             array_contains(source_systems, 'NB_CRM') AS in_nb_crm, array_contains(source_systems, 'NB_BILLING') AS in_nb_billing,
             array_contains(source_systems, 'NB_PLACEMENT') AS in_nb_placement, array_contains(source_systems, 'HC_AMS') AS in_harbor_cole,
             CASE WHEN array_contains(source_systems, 'HC_AMS') AND size(array_remove(source_systems, 'HC_AMS')) > 0 THEN 'Both'
                  WHEN array_contains(source_systems, 'HC_AMS') THEN 'Harbor & Cole' ELSE 'Northbridge' END AS client_origin,
             min_match_confidence, has_steward_override, current_timestamp() AS golden_record_refreshed_at
      FROM party_family
    """)


@dp.materialized_view(name="party_hierarchy", table_properties=GOLD_PROPS, comment=(
    "Legal-entity hierarchy over golden parties (parent -> subsidiary). hierarchy_level 0 = ultimate parent. "
    "parent_link_source shows whether the link came from the legal-entity registry or an explicit CRM parent account."))
def party_hierarchy():
    return spark.sql("""
      SELECT party_id, party_name, country_iso, parent_party_id, parent_party_name, ultimate_parent_party_id, ultimate_parent_name,
             hierarchy_level, hierarchy_path, parent_link_source, is_restricted
      FROM party_family
    """)


@dp.materialized_view(name="party_source_xref", table_properties=GOLD_PROPS, comment=(
    "Cross-reference from every source-system client record to its golden party_id, with match method and confidence. "
    "Shows which source systems contributed to each golden record (lineage summary)."))
def party_source_xref():
    return spark.sql("""
      SELECT m.party_id, m.record_key, m.source_system, m.source_record_id, m.source_name, m.country_iso, m.registration_number,
             m.match_method, m.match_confidence, f.ultimate_parent_party_id, f.is_restricted
      FROM party_members m JOIN party_family f USING (party_id)
    """)


@dp.temporary_view(name="revenue_lines")
def revenue_lines():
    return spark.sql(f"""
      WITH nb AS (
        SELECT t.transaction_id AS source_transaction_id, 'NB_BILLING' AS source_system, x.party_id, t.placement_ref AS placement_id,
               t.revenue_type, CASE WHEN t.revenue_type = 'Fee' THEN 'Fee' ELSE 'Commission' END AS revenue_category,
               t.line_of_business, coalesce(p.carrier_name, t.carrier_code) AS carrier_name, t.transaction_date AS revenue_date,
               t.currency, t.amount AS amount_original, t.fx_rate_to_usd, t.amount_usd
        FROM {SILVER}.revenue_transactions t
        JOIN {ML}.party_xref x ON x.record_key = concat('NB_BILLING:', t.billing_client_id)
        LEFT JOIN {SILVER}.placements p ON p.placement_id = t.placement_ref),
      hc AS (
        SELECT concat(policy_no, '-', k.kind) AS source_transaction_id, 'HC_AMS' AS source_system, x.party_id, policy_no AS placement_id,
               k.kind AS revenue_type, k.kind AS revenue_category, {HC_LOB_SQL} AS line_of_business, carrier_name,
               effective_date AS revenue_date, currency,
               CASE k.kind WHEN 'Commission' THEN commission_amount ELSE fee_amount END AS amount_original, fx_rate_to_usd,
               CAST(CASE k.kind WHEN 'Commission' THEN commission_amount ELSE fee_amount END * fx_rate_to_usd AS DECIMAL(18,2)) AS amount_usd
        FROM {SILVER}.hc_policies
        CROSS JOIN (VALUES ('Commission'), ('Fee')) AS k(kind)
        JOIN {ML}.party_xref x ON x.record_key = concat('HC_AMS:', client_code)
        WHERE effective_date <= current_date())
      SELECT md5(concat(r.source_system, r.source_transaction_id)) AS revenue_id, r.*, year(r.revenue_date) AS fiscal_year,
             concat('FY', year(r.revenue_date), ' Q', quarter(r.revenue_date)) AS fiscal_quarter,
             f.ultimate_parent_party_id, f.is_restricted
      FROM (SELECT * FROM nb UNION ALL SELECT * FROM hc) r JOIN party_family f USING (party_id)
      WHERE r.amount_usd <> 0
    """)


@dp.temporary_view(name="placement_lines")
def placement_lines():
    return spark.sql(f"""
      WITH nb AS (
        SELECT p.placement_id, 'NB_PLACEMENT' AS source_system, x.party_id, p.line_of_business, p.carrier_name,
               p.inception_date, p.expiry_date, p.broker_of_record, p.placing_office, p.remuneration_basis, p.commission_rate, p.gwp_usd
        FROM {SILVER}.placements p JOIN {ML}.party_xref x ON x.record_key = concat('NB_PLACEMENT:', p.insured_id)),
      hc AS (
        SELECT policy_no, 'HC_AMS', x.party_id, {HC_LOB_SQL}, carrier_name, effective_date, expiry_date, producer, 'Harbor & Cole',
               CASE WHEN fee_amount > 0 THEN 'Commission + Fee' ELSE 'Commission' END, CAST(commission_pct / 100 AS DECIMAL(9,4)),
               CAST(premium * fx_rate_to_usd AS DECIMAL(18,2))
        FROM {SILVER}.hc_policies JOIN {ML}.party_xref x ON x.record_key = concat('HC_AMS:', client_code))
      SELECT r.*, current_date() BETWEEN r.inception_date AND r.expiry_date AS is_in_force, year(r.inception_date) AS inception_year,
             f.ultimate_parent_party_id, f.is_restricted
      FROM (SELECT * FROM nb UNION ALL SELECT * FROM hc) r JOIN party_family f USING (party_id)
    """)


@dp.materialized_view(name="fact_revenue", table_properties={**GOLD_PROPS, "sox_relevant": "true"}, comment=(
    "Broker revenue = fee and commission income (never premium). One row per revenue transaction from Northbridge billing "
    "and the Harbor & Cole AMS, converted to USD at finance planning rates, attributed to the golden party billed and to its "
    "ultimate parent. Fiscal year = calendar year. Use the metric view client_revenue_metrics for governed totals."))
def fact_revenue():
    return spark.read.table("revenue_lines")


@dp.materialized_view(name="fact_placements", table_properties=GOLD_PROPS, comment=(
    "Placements (insurance programmes placed by the broker) from the Northbridge placement platform and Harbor & Cole AMS, "
    "attributed to golden parties. gwp_usd is gross written premium for reference only - it is NOT broker revenue."))
def fact_placements():
    return spark.read.table("placement_lines")


@dp.temporary_view(name="revenue_by_party_year")
def revenue_by_party_year():
    return spark.sql("""
      WITH rev AS (
        SELECT party_id, fiscal_year,
               sum(CASE WHEN revenue_category = 'Commission' THEN amount_usd ELSE 0 END) AS commission_income_usd,
               sum(CASE WHEN revenue_category = 'Fee' THEN amount_usd ELSE 0 END) AS fee_income_usd,
               sum(amount_usd) AS total_revenue_usd, count(DISTINCT carrier_name) AS carrier_count,
               count(DISTINCT line_of_business) AS line_count, count(DISTINCT placement_id) AS placement_count
        FROM revenue_lines GROUP BY ALL)
      SELECT concat(r.party_id, '-', r.fiscal_year) AS summary_id, r.*, f.party_name, f.ultimate_parent_party_id,
             f.ultimate_parent_name, f.hierarchy_level, f.is_restricted
      FROM rev r JOIN party_family f USING (party_id)
    """)


@dp.materialized_view(name="client_revenue_summary", table_properties={**GOLD_PROPS, "sox_relevant": "true"}, comment=(
    "Fee and commission revenue per golden party per fiscal year, with the ultimate parent for roll-up. Built from fact_revenue "
    "so totals tie to the metric view to the dollar. Synced to Lakebase for the Client 360 app."))
def client_revenue_summary():
    return spark.read.table("revenue_by_party_year")


@dp.materialized_view(
    name="party_contacts", table_properties={**GOLD_PROPS, "pii": "true"},
    comment="Client contacts from the Northbridge CRM attached to golden parties. contact_name, email and phone are PII: classification-tagged and masked by ABAC policy for anyone outside the PII readers group.")
def party_contacts():
    return spark.sql(f"""
      SELECT c.contact_id, x.party_id, f.ultimate_parent_party_id, concat(c.first_name, ' ', c.last_name) AS contact_name,
             c.title, c.email, c.phone, f.is_restricted
      FROM {SILVER}.crm_contacts c JOIN {ML}.party_xref x ON x.record_key = concat('NB_CRM:', c.account_id)
      JOIN party_family f USING (party_id)
    """)


@dp.materialized_view(name="commission_reconciliation", table_properties={**GOLD_PROPS, "sox_relevant": "true"}, comment=(
    "Per placement: commission booked in Northbridge billing vs commission reported on the carrier's statement (local currency). "
    "variance_local <> 0 flags short-paid or missing carrier commission."))
def commission_reconciliation():
    return spark.sql(f"""
      WITH booked AS (SELECT placement_ref AS placement_id, sum(amount) AS booked_commission
                      FROM {SILVER}.revenue_transactions WHERE revenue_type IN ('Commission', 'Commission Adjustment') GROUP BY 1),
           stmt AS (SELECT policy_ref AS placement_id, sum(commission_amount) AS statement_commission, max(carrier_name) AS statement_carrier
                    FROM {SILVER}.carrier_statement_lines GROUP BY 1)
      SELECT p.placement_id, p.party_id, p.ultimate_parent_party_id, p.carrier_name, p.line_of_business, p.inception_date,
             b.booked_commission, s.statement_commission,
             CAST(coalesce(s.statement_commission, 0) - coalesce(b.booked_commission, 0) AS DECIMAL(18,2)) AS variance_local,
             CASE WHEN s.placement_id IS NULL THEN 'Missing from statement'
                  WHEN abs(coalesce(s.statement_commission, 0) - coalesce(b.booked_commission, 0)) < 1 THEN 'Reconciled'
                  ELSE 'Variance' END AS reconciliation_status, p.is_restricted
      FROM placement_lines p JOIN booked b USING (placement_id) LEFT JOIN stmt s USING (placement_id)
      WHERE p.source_system = 'NB_PLACEMENT'
    """)


@dp.materialized_view(name="er_run_history", table_properties=GOLD_PROPS, comment=(
    "History of entity resolution runs: source records in, golden parties out, records_merged (source records folded into "
    "another record's golden party), auto-matched pairs, pairs sent to steward review, and steward decisions applied. "
    "The latest run is the row with the max run_ts."))
def er_run_history():
    return spark.sql(f"""
      SELECT *, run_ts = max(run_ts) OVER () AS is_latest_run FROM {ML}.er_run_log
    """)


# ------------------------------------------------------------------------------------------------
# App serving projection (synced to Lakebase). Unrestricted segment only, no contact PII: exactly what the
# Client 360 app's service principal is entitled to. Restricted clients are served to entitled users from
# gold over the SQL warehouse, on behalf of the signed-in user, so the ABAC policy decides.
# ------------------------------------------------------------------------------------------------
APP_PROPS = {"layer": "app_serving", "delta.enableChangeDataFeed": "true"}


@dp.materialized_view(name=f"{APP}.app_party", table_properties=APP_PROPS, comment=(
    "Serving projection of gold.dim_party for the Client 360 app: unrestricted segment only, synced to Lakebase."))
def app_party():
    return spark.sql("""
      SELECT party_id, party_name, country_iso, registration_number, lei, address_line1, city, industry,
             segment AS client_segment, account_executive, parent_party_id, parent_party_name, ultimate_parent_party_id,
             ultimate_parent_name, hierarchy_level, parent_link_source, to_json(source_systems) AS source_systems,
             source_system_count, source_record_count,
             CASE WHEN array_contains(source_systems, 'HC_AMS') AND size(array_remove(source_systems, 'HC_AMS')) > 0 THEN 'Both'
                  WHEN array_contains(source_systems, 'HC_AMS') THEN 'Harbor & Cole' ELSE 'Northbridge' END AS client_origin,
             min_match_confidence, has_steward_override,
             lower(concat_ws(' ', party_name, ultimate_parent_name, registration_number, party_id)) AS search_text,
             current_timestamp() AS golden_record_refreshed_at
      FROM party_family WHERE NOT is_restricted
    """)


@dp.materialized_view(name=f"{APP}.app_party_source_xref", table_properties=APP_PROPS, comment=(
    "Serving projection of gold.party_source_xref (unrestricted segment) - which source records make up each golden party."))
def app_party_source_xref():
    return spark.sql("""
      SELECT m.record_key, m.party_id, m.source_system, m.source_record_id, m.source_name, m.country_iso,
             m.registration_number, m.match_method, m.match_confidence, f.ultimate_parent_party_id
      FROM party_members m JOIN party_family f USING (party_id) WHERE NOT f.is_restricted
    """)


@dp.materialized_view(name=f"{APP}.app_client_revenue_summary", table_properties=APP_PROPS, comment=(
    "Serving projection of gold.client_revenue_summary (unrestricted segment): fee + commission revenue per party per fiscal year."))
def app_client_revenue_summary():
    return spark.read.table("revenue_by_party_year").where("NOT is_restricted").drop("is_restricted")


@dp.materialized_view(name=f"{APP}.app_placements", table_properties=APP_PROPS, comment=(
    "Serving projection of gold.fact_placements (unrestricted segment)."))
def app_placements():
    return spark.read.table("placement_lines").where("NOT is_restricted").drop("is_restricted")


@dp.materialized_view(name=f"{APP}.app_match_review_queue", table_properties=APP_PROPS, comment=(
    "Steward review queue for the app: review-band pairs with model score and LLM rationale, excluding pairs that touch the "
    "Restricted segment."))
def app_match_review_queue():
    return spark.sql(f"""
      SELECT q.* FROM {ML}.match_review_queue q
      JOIN party_family l ON q.left_party_id = l.party_id
      JOIN party_family r ON q.right_party_id = r.party_id
      WHERE NOT l.is_restricted AND NOT r.is_restricted
    """)
