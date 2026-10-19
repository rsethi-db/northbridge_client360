"""Silver: standardized, validated source records.

Each table declares its data quality rules once (RULES). The same rules drive
  * `@dp.expect_all_or_drop` on the silver table (violations dropped, counted in the pipeline UI), and
  * the `dq_quarantine` table, which keeps every dropped row with the rule it broke so stewards can fix the source.
"""
from functools import reduce

from pyspark import pipelines as dp
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from utilities.standardize import (VALID_COUNTRIES, address_norm, country_iso, fx_rate, name_clean, name_core,
                                   parse_amount, postcode_norm, reg_norm)

CAT = spark.conf.get("catalog")
P = spark.conf.get("schema_prefix")
BRONZE, SILVER = f"{CAT}.{P}bronze", f"{CAT}.{P}silver"
COUNTRY_LIST = ",".join(f"'{c}'" for c in VALID_COUNTRIES)
SILVER_PROPS = {"layer": "silver", "delta.enableChangeDataFeed": "true"}


# ------------------------------------------------------------------------------------------------
# Row-level transforms (shared by the silver tables and the quarantine)
# ------------------------------------------------------------------------------------------------
def t_crm_accounts(df: DataFrame) -> DataFrame:
    return df.select(
        "account_id", "account_name",
        country_iso(F.col("billing_country")).alias("country_iso"), F.col("billing_country").alias("country_raw"),
        F.col("billing_street").alias("address_line1"), F.col("billing_city").alias("city"), F.col("billing_postal_code").alias("postcode"),
        F.col("company_registration_no").alias("registration_number"), reg_norm(F.col("company_registration_no")).alias("registration_number_norm"),
        "industry", "client_segment", "client_confidentiality", "account_executive", "parent_account_id",
        F.to_date("created_date").alias("created_date"), F.to_date("last_modified").alias("last_modified"),
        name_clean(F.col("account_name")).alias("name_clean"), name_core(F.col("account_name")).alias("name_core"),
        "_source_file", "_ingested_at")


def t_crm_contacts(df):
    return df.select("contact_id", "account_id", "first_name", "last_name", "title", F.lower("email").alias("email"), "phone",
                     "_source_file", "_ingested_at")


def t_billing_clients(df):
    parts = F.split("invoice_address", ";\\s*")
    return df.select(
        "billing_client_id", "billing_name", F.col("tax_or_registration_id").alias("registration_number"),
        reg_norm(F.col("tax_or_registration_id")).alias("registration_number_norm"),
        country_iso(F.col("country_code")).alias("country_iso"), F.col("country_code").alias("country_raw"),
        parts[0].alias("address_line1"), parts[1].alias("city"), parts[2].alias("postcode"),
        "invoice_currency", "payment_terms", "ar_status",
        name_clean(F.col("billing_name")).alias("name_clean"), name_core(F.col("billing_name")).alias("name_core"),
        "_source_file", "_ingested_at")


def t_revenue_transactions(df):
    amt = parse_amount(F.col("amount"))
    return df.select(
        "transaction_id", F.nullif(F.trim("billing_client_id"), F.lit("")).alias("billing_client_id"), "placement_ref",
        F.to_date("transaction_date").alias("transaction_date"), "revenue_type", "line_of_business", "carrier_code",
        F.upper("currency").alias("currency"), F.col("amount").alias("amount_raw"), amt.alias("amount"),
        fx_rate(F.col("currency")).alias("fx_rate_to_usd"), (amt * fx_rate(F.col("currency"))).cast("decimal(18,2)").alias("amount_usd"),
        "_source_file", "_ingested_at")


def t_insureds(df):
    parts = F.split("address", ",\\s*")
    return df.select(
        "insured_id", "insured_name", F.col("domicile_country").alias("country_iso"),
        "registration_number", reg_norm(F.col("registration_number")).alias("registration_number_norm"),
        parts[0].alias("address_line1"), parts[1].alias("city"), parts[2].alias("postcode"), "industry_code",
        name_clean(F.col("insured_name")).alias("name_clean"), name_core(F.col("insured_name")).alias("name_core"),
        "_source_file", "_ingested_at")


def t_placements(df):
    return df.select(
        "placement_id", "insured_id", "line_of_business", "carrier_code", "carrier_name",
        F.to_date("inception_date").alias("inception_date"), F.to_date("expiry_date").alias("expiry_date"),
        "broker_of_record", "placing_office", "currency",
        F.col("gross_written_premium").cast("decimal(18,2)").alias("gross_written_premium"),
        (F.col("gross_written_premium") * fx_rate(F.col("currency"))).cast("decimal(18,2)").alias("gwp_usd"),
        "remuneration_basis", F.col("commission_rate").cast("decimal(9,4)").alias("commission_rate"),
        F.col("fee_amount").cast("decimal(18,2)").alias("fee_amount"), "placement_status",
        "_source_file", "_ingested_at")


def t_hc_clients(df):
    parts = F.split("ADDR", ",\\s*")
    return df.select(
        F.col("CLIENT_CODE").alias("client_code"), F.nullif(F.trim("CLIENT_NAME"), F.lit("")).alias("client_name"),
        parts[0].alias("address_line1"), parts[1].alias("city"), parts[2].alias("postcode"),
        country_iso(F.col("CNTRY")).alias("country_iso"), F.col("CNTRY").alias("country_raw"),
        F.col("REG_NO").alias("registration_number"), reg_norm(F.col("REG_NO")).alias("registration_number_norm"),
        F.initcap("SIC_DESC").alias("industry"), (F.col("SENS_FLAG") == "Y").alias("sensitive_client_flag"),
        F.col("PRODUCER").alias("producer"), F.to_date("DATE_OPENED", "MM/dd/yyyy").alias("date_opened"),
        F.nullif(F.col("PARENT_CLIENT_CODE"), F.lit("")).alias("parent_client_code"),
        name_clean(F.col("CLIENT_NAME")).alias("name_clean"), name_core(F.col("CLIENT_NAME")).alias("name_core"),
        "_source_file", "_ingested_at")


def t_hc_policies(df):
    return df.select(
        F.col("POLICY_NO").alias("policy_no"), F.col("CLIENT_CODE").alias("client_code"), F.col("LOB").alias("lob_code"),
        F.initcap("CARRIER").alias("carrier_name"), F.to_date("EFF_DATE", "MM/dd/yyyy").alias("effective_date"),
        F.to_date("EXP_DATE", "MM/dd/yyyy").alias("expiry_date"), parse_amount(F.col("PREMIUM")).alias("premium"),
        F.col("COMM_PCT").cast("decimal(6,2)").alias("commission_pct"), parse_amount(F.col("COMM_AMT")).alias("commission_amount"),
        parse_amount(F.col("FEE")).alias("fee_amount"), F.col("CCY").alias("currency"), fx_rate(F.col("CCY")).alias("fx_rate_to_usd"),
        F.col("PRODUCER").alias("producer"), "_source_file", "_ingested_at")


def t_registry(df):
    parts = F.split("registered_address", ",\\s*")
    return df.select(
        "lei", "legal_name", F.col("jurisdiction").alias("country_iso"), "registration_number",
        reg_norm(F.col("registration_number")).alias("registration_number_norm"),
        parts[0].alias("address_line1"), parts[1].alias("city"), parts[2].alias("postcode"),
        reg_norm(F.col("direct_parent_registration_number")).alias("direct_parent_registration_number_norm"),
        F.col("direct_parent_jurisdiction"), reg_norm(F.col("ultimate_parent_registration_number")).alias("ultimate_parent_registration_number_norm"),
        F.col("ultimate_parent_jurisdiction"), "entity_status",
        name_clean(F.col("legal_name")).alias("name_clean"), name_core(F.col("legal_name")).alias("name_core"),
        "_source_file", "_ingested_at")


# Carrier statements: three inbound layouts normalized to one schema.
def t_stmt_a(df):
    return df.select(F.col("Carrier").alias("carrier_name"), F.to_date("Statement Period").alias("statement_period"),
                     F.nullif(F.col("Policy Ref"), F.lit("")).alias("policy_ref"), F.col("Insured Name").alias("insured_name"),
                     F.col("Line").alias("line_of_business"), parse_amount(F.col("Comm Amt")).alias("commission_amount"),
                     F.col("Ccy").alias("currency"), F.lit("A").alias("statement_layout"), "_source_file", "_ingested_at")


def t_stmt_b(df):
    return df.select(F.col("carrier_name"), F.to_date("stmt_month", "dd/MM/yyyy").alias("statement_period"),
                     F.nullif(F.col("policy_number"), F.lit("")).alias("policy_ref"), F.initcap("client").alias("insured_name"),
                     F.lit(None).cast("string").alias("line_of_business"), parse_amount(F.col("commission")).alias("commission_amount"),
                     F.col("currency_code").alias("currency"), F.lit("B").alias("statement_layout"), "_source_file", "_ingested_at")


def t_stmt_c(df):
    return df.select(F.col("SYNDICATE").alias("carrier_name"), F.to_date("PERIOD_END", "yyyyMMdd").alias("statement_period"),
                     F.nullif(F.col("POLICY"), F.lit("")).alias("policy_ref"), F.col("ASSURED").alias("insured_name"),
                     F.initcap("CLASS").alias("line_of_business"), parse_amount(F.col("BROKERAGE")).alias("commission_amount"),
                     F.col("CURRENCY").alias("currency"), F.lit("C").alias("statement_layout"), "_source_file", "_ingested_at")


# ------------------------------------------------------------------------------------------------
# Data quality rules (rule name -> SQL predicate that must be TRUE for a valid row)
# ------------------------------------------------------------------------------------------------
RULES = {
    "crm_accounts": {"valid_account_id": "account_id IS NOT NULL", "valid_account_name": "account_name IS NOT NULL",
                     "valid_country": f"country_iso IN ({COUNTRY_LIST})"},
    "crm_contacts": {"valid_account_ref": "account_id IS NOT NULL"},
    "billing_clients": {"valid_billing_client_id": "billing_client_id IS NOT NULL", "valid_country": f"country_iso IN ({COUNTRY_LIST})"},
    "revenue_transactions": {"valid_billing_client_ref": "billing_client_id IS NOT NULL", "valid_amount": "amount IS NOT NULL",
                             "valid_transaction_date": "transaction_date IS NOT NULL", "known_currency": "fx_rate_to_usd IS NOT NULL"},
    "placement_insureds": {"valid_insured_id": "insured_id IS NOT NULL"},
    "placements": {"valid_policy_period": "expiry_date > inception_date", "commission_rate_is_ratio": "commission_rate BETWEEN 0 AND 0.5"},
    "hc_clients": {"valid_client_name": "client_name IS NOT NULL", "valid_country": f"country_iso IN ({COUNTRY_LIST})"},
    "hc_policies": {"valid_client_ref": "client_code IS NOT NULL", "valid_effective_date": "effective_date IS NOT NULL"},
    "carrier_statement_lines": {"valid_policy_ref": "policy_ref IS NOT NULL", "valid_commission_amount": "commission_amount IS NOT NULL"},
    "le_registry": {"valid_registration_number": "registration_number_norm IS NOT NULL"},
}
WARN = {  # tracked, not dropped
    "crm_accounts": {"has_registration_number": "registration_number_norm IS NOT NULL"},
    "hc_clients": {"has_registration_number": "registration_number_norm IS NOT NULL"},
    "crm_contacts": {"plausible_email": "email RLIKE '^[^@]+@[^@]+\\\\.[a-z]+$'"},
}

# silver table -> (bronze tables, transform, business key)
SOURCES = {
    "crm_accounts": (["crm_accounts"], t_crm_accounts, "account_id"),
    "crm_contacts": (["crm_contacts"], t_crm_contacts, "contact_id"),
    "billing_clients": (["billing_clients"], t_billing_clients, "billing_client_id"),
    "revenue_transactions": (["billing_revenue_transactions"], t_revenue_transactions, "transaction_id"),
    "placement_insureds": (["placement_insureds"], t_insureds, "insured_id"),
    "placements": (["placement_placements"], t_placements, "placement_id"),
    "hc_clients": (["hc_clients"], t_hc_clients, "client_code"),
    "hc_policies": (["hc_policies"], t_hc_policies, "policy_no"),
    "le_registry": (["le_registry"], t_registry, "registration_number"),
}
COMMENTS = {
    "crm_accounts": "Northbridge CRM accounts, standardized (ISO country, normalized registration number, cleaned name). Rows failing DQ rules are in dq_quarantine.",
    "crm_contacts": "Northbridge CRM client contacts. PII - masked in gold.party_contacts.",
    "billing_clients": "Northbridge billing system billed entities, standardized.",
    "revenue_transactions": "Northbridge fee and commission income transactions with parsed amounts and USD conversion at finance planning rates. SOX-relevant.",
    "placement_insureds": "Placement platform insured parties, standardized.",
    "placements": "Placement platform placements, validated (policy period, commission rate stored as a ratio). GWP is a reference attribute, not broker revenue.",
    "hc_clients": "Harbor & Cole legacy AMS clients, standardized. Many duplicates - resolved by entity resolution.",
    "hc_policies": "Harbor & Cole legacy AMS policies with commission and fee income. SOX-relevant.",
    "le_registry": "Legal-entity registry reference feed with direct and ultimate parent registration numbers; drives the legal-entity hierarchy.",
}


def _make_silver(name, bronze, fn):
    def _t():
        return fn(spark.readStream.table(f"{BRONZE}.{bronze[0]}"))
    _t.__name__ = name
    _t = dp.expect_all_or_drop(RULES[name])(_t)
    if name in WARN:
        _t = dp.expect_all(WARN[name])(_t)
    dp.table(name=f"{SILVER}.{name}", comment=COMMENTS[name], table_properties=SILVER_PROPS)(_t)


for _name, (_bronze, _fn, _key) in SOURCES.items():
    _make_silver(_name, _bronze, _fn)


@dp.table(name=f"{SILVER}.carrier_statement_lines", table_properties=SILVER_PROPS,
          comment="Carrier commission statement lines from all carriers, normalized from three inbound layouts into one schema. Used to reconcile booked commission.")
@dp.expect_all_or_drop(RULES["carrier_statement_lines"])
def carrier_statement_lines():
    return (t_stmt_a(spark.readStream.table(f"{BRONZE}.carrier_statements_layout_a"))
            .unionByName(t_stmt_b(spark.readStream.table(f"{BRONZE}.carrier_statements_layout_b")))
            .unionByName(t_stmt_c(spark.readStream.table(f"{BRONZE}.carrier_statements_layout_c"))))


# ------------------------------------------------------------------------------------------------
# Quarantine: every row a silver rule dropped, with the rule it broke
# ------------------------------------------------------------------------------------------------
@dp.materialized_view(name=f"{SILVER}.dq_quarantine", table_properties={"layer": "silver"},
                      comment="Rows rejected by silver data quality rules, one row per (record, failed rule). Source of the steward data-quality worklist.")
def dq_quarantine():
    parts = []
    srcs = {**{k: (v[0][0], v[1], v[2]) for k, v in SOURCES.items()}}
    for silver_name, (bronze, fn, key) in srcs.items():
        df = fn(spark.read.table(f"{BRONZE}.{bronze}"))
        for rule, pred in RULES[silver_name].items():
            parts.append(df.where(f"NOT coalesce({pred}, false)").select(
                F.lit(silver_name).alias("silver_table"), F.lit(rule).alias("failed_rule"), F.lit(pred).alias("rule_definition"),
                F.col(key).cast("string").alias("record_key"), F.to_json(F.struct(*df.columns)).alias("record"),
                "_source_file", "_ingested_at"))
    stmt = (t_stmt_a(spark.read.table(f"{BRONZE}.carrier_statements_layout_a"))
            .unionByName(t_stmt_b(spark.read.table(f"{BRONZE}.carrier_statements_layout_b")))
            .unionByName(t_stmt_c(spark.read.table(f"{BRONZE}.carrier_statements_layout_c"))))
    for rule, pred in RULES["carrier_statement_lines"].items():
        parts.append(stmt.where(f"NOT coalesce({pred}, false)").select(
            F.lit("carrier_statement_lines").alias("silver_table"), F.lit(rule).alias("failed_rule"), F.lit(pred).alias("rule_definition"),
            F.concat_ws("|", "carrier_name", "insured_name", "statement_period").alias("record_key"),
            F.to_json(F.struct(*stmt.columns)).alias("record"), "_source_file", "_ingested_at"))
    return reduce(DataFrame.unionByName, parts)


# ------------------------------------------------------------------------------------------------
# Entity resolution input: every party record from all four source systems in one schema
# ------------------------------------------------------------------------------------------------
PARTY_COLS = ["source_system", "source_record_id", "source_name", "name_clean", "name_core", "country_iso",
              "registration_number", "registration_number_norm", "address_line1", "address_norm", "city", "postcode_norm",
              "industry", "client_segment", "is_restricted_flag", "source_parent_record_id", "account_executive"]


def _party(df, system, id_col, name_col, industry, segment, restricted, parent, ae):
    return df.select(
        F.lit(system).alias("source_system"), F.col(id_col).alias("source_record_id"), F.col(name_col).alias("source_name"),
        "name_clean", "name_core", "country_iso", "registration_number", "registration_number_norm", "address_line1",
        address_norm(F.col("address_line1")).alias("address_norm"), F.upper("city").alias("city"),
        postcode_norm(F.col("postcode")).alias("postcode_norm"), industry.alias("industry"), segment.alias("client_segment"),
        restricted.alias("is_restricted_flag"), parent.alias("source_parent_record_id"), ae.alias("account_executive"))


@dp.materialized_view(name=f"{SILVER}.party_source_records", table_properties={"layer": "silver"},
                      comment="All client/party records from the four source systems (NB_CRM, NB_BILLING, NB_PLACEMENT, HC_AMS) in one standardized schema. Input to entity resolution. Not certified: one real-world client appears many times here.")
def party_source_records():
    null = F.lit(None).cast("string")
    crm = _party(spark.read.table(f"{SILVER}.crm_accounts"), "NB_CRM", "account_id", "account_name", F.col("industry"),
                 F.col("client_segment"), F.col("client_confidentiality") == "Restricted", F.col("parent_account_id"), F.col("account_executive"))
    bil = _party(spark.read.table(f"{SILVER}.billing_clients"), "NB_BILLING", "billing_client_id", "billing_name", null, null,
                 F.lit(None).cast("boolean"), null, null)
    ins = _party(spark.read.table(f"{SILVER}.placement_insureds"), "NB_PLACEMENT", "insured_id", "insured_name",
                 F.initcap(F.regexp_replace("industry_code", "_", " ")), null, F.lit(None).cast("boolean"), null, null)
    hc = _party(spark.read.table(f"{SILVER}.hc_clients"), "HC_AMS", "client_code", "client_name", F.col("industry"), null,
                F.col("sensitive_client_flag"), F.col("parent_client_code"), F.col("producer"))
    return crm.unionByName(bil).unionByName(ins).unionByName(hc).select(*PARTY_COLS)
