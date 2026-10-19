_Collected 2026-10-16 21:51:28 UTC by `scripts/collect_evidence.py` as `richa.sethi@databricks.com` on https://fevm-richasethi-febar.cloud.databricks.com_

# Lineage (system.access.table_lineage)

Upstream of the golden party record `nb_gold.dim_party`:

- nb_gold.dim_party
  - nb_ml.party_hierarchy
    - nb_ml.party_xref
      - nb_silver.party_source_records
        - nb_silver.billing_clients
          - nb_bronze.billing_clients
        - nb_silver.crm_accounts
          - nb_bronze.crm_accounts
        - nb_silver.hc_clients
          - nb_bronze.hc_clients
        - nb_silver.placement_insureds
          - nb_bronze.placement_insureds
    - nb_silver.le_registry
      - nb_bronze.le_registry

File-level provenance (bronze `_source_file`, captured by Auto Loader from the UC Volume):

| bronze table | file in /Volumes/.../nb_raw/landing | rows |
|---|---|---|
| crm_accounts | crm/accounts/accounts_extract_02.json | 453 |
| crm_accounts | crm/accounts/accounts_extract_01.json | 456 |
| crm_accounts | crm/accounts/accounts_extract_00.json | 456 |
| billing_clients | billing/clients/billing_clients.csv | 1085 |
| placement_insureds | placement/insureds/insureds.parquet | 1380 |
| hc_clients | harbor_cole/clients/HC_CLIENT_MASTER.TXT | 460 |
| le_registry | reference/le_registry/legal_entity_registry.csv | 1805 |

Source systems reached from the golden record: **4 of 4** - ['Harbor & Cole AMS', 'Northbridge CRM', 'Northbridge billing & commission', 'Placement platform']

Genie answers trace to `nb_gold` tables and the metric view; see `08_genie_test_results.md`.
