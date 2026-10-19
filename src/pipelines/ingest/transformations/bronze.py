"""Bronze: Auto Loader ingest of the raw drop zone. One streaming table per source feed, no business rules."""
from pyspark import pipelines as dp
from pyspark.sql import functions as F

LANDING = spark.conf.get("landing_path")


def autoload(path, fmt, **opts):
    reader = spark.readStream.format("cloudFiles").option("cloudFiles.format", fmt)
    for k, v in opts.items():
        reader = reader.option(k, v)
    return (reader.load(f"{LANDING}/{path}")
            .withColumn("_source_file", F.col("_metadata.file_path"))
            .withColumn("_ingested_at", F.current_timestamp()))


CSV = {"header": "true", "cloudFiles.inferColumnTypes": "false"}
TAGS = lambda system: {"source_system": system, "layer": "bronze"}


# --- Northbridge CRM --------------------------------------------------------------------------
@dp.table(name="crm_accounts", comment="Northbridge CRM account extract (JSON), as delivered. One row per CRM account; the same client can appear more than once.",
          table_properties=TAGS("NB_CRM"))
def crm_accounts():
    return autoload("crm/accounts", "json", **{"cloudFiles.inferColumnTypes": "false"})


@dp.table(name="crm_contacts", comment="Northbridge CRM client contacts (JSON). Contains PII: names, emails, phone numbers.",
          table_properties=TAGS("NB_CRM"))
def crm_contacts():
    return autoload("crm/contacts", "json", **{"cloudFiles.inferColumnTypes": "false"})


# --- Northbridge billing & commission -----------------------------------------------------------
@dp.table(name="billing_clients", comment="Northbridge billing system client (billed entity) master, CSV extract.",
          table_properties=TAGS("NB_BILLING"))
def billing_clients():
    return autoload("billing/clients", "csv", **CSV)


@dp.table(name="billing_revenue_transactions", comment="Northbridge billing system fee and commission income transactions, CSV extract. Amounts arrive as text in the invoice currency.",
          table_properties=TAGS("NB_BILLING"))
def billing_revenue_transactions():
    return autoload("billing/transactions", "csv", **CSV)


# --- Placement platform -------------------------------------------------------------------------
@dp.table(name="placement_insureds", comment="Placement platform insured parties (Parquet).", table_properties=TAGS("NB_PLACEMENT"))
def placement_insureds():
    return autoload("placement/insureds", "parquet")


@dp.table(name="placement_placements", comment="Placement platform placements (Parquet): line of business, carrier, inception/expiry, broker of record, GWP (reference only), commission rate or fee.",
          table_properties=TAGS("NB_PLACEMENT"))
def placement_placements():
    return autoload("placement/placements", "parquet")


# --- Harbor & Cole legacy agency management system ---------------------------------------------
@dp.table(name="hc_clients", comment="Harbor & Cole legacy AMS client master (pipe-delimited TXT). Acquired agency; heavy duplication and missing registration numbers.",
          table_properties=TAGS("HC_AMS"))
def hc_clients():
    return autoload("harbor_cole/clients", "csv", sep="|", **CSV)


@dp.table(name="hc_policies", comment="Harbor & Cole legacy AMS policy register (pipe-delimited TXT) with commission and fee income.",
          table_properties=TAGS("HC_AMS"))
def hc_policies():
    return autoload("harbor_cole/policies", "csv", sep="|", **CSV)


# --- Carrier commission statements: each carrier family sends a different layout ---------------
@dp.table(name="carrier_statements_layout_a", comment="Carrier commission statements, layout A (comma CSV, ISO dates, 'Comm Amt'). Column names kept exactly as the carrier sends them.",
          table_properties={**TAGS("CARRIER_STATEMENT"), "delta.columnMapping.mode": "name"})
def carrier_statements_layout_a():
    return autoload("carrier_statements/layout_a/*", "csv", **CSV)


@dp.table(name="carrier_statements_layout_b", comment="Carrier commission statements, layout B (quoted CSV, dd/MM/yyyy dates, thousands separators).",
          table_properties=TAGS("CARRIER_STATEMENT"))
def carrier_statements_layout_b():
    return autoload("carrier_statements/layout_b/*", "csv", **CSV)


@dp.table(name="carrier_statements_layout_c", comment="Carrier commission statements, layout C (semicolon CSV, yyyyMMdd dates, decimal comma, Lloyd's syndicate style).",
          table_properties=TAGS("CARRIER_STATEMENT"))
def carrier_statements_layout_c():
    return autoload("carrier_statements/layout_c/*", "csv", sep=";", **CSV)


# --- Reference: legal-entity registry feed ------------------------------------------------------
@dp.table(name="le_registry", comment="Third-party legal-entity registry feed (LEI-style): registration numbers with direct and ultimate parent references.",
          table_properties=TAGS("LE_REGISTRY"))
def le_registry():
    return autoload("reference/le_registry", "csv", **CSV)
