_Collected 2026-10-16 21:47:45 UTC by `scripts/collect_evidence.py` as `richa.sethi@databricks.com` on https://fevm-richasethi-febar.cloud.databricks.com_

# Lakeflow Declarative Pipeline: data quality

### Expectation results from the pipeline event log (latest update)
```sql
WITH ev AS (SELECT origin.update_id, origin.flow_name, details:flow_progress.data_quality.expectations AS e, timestamp
            FROM event_log('26ffcefa-3d12-4525-9b24-1ddc0638f6dd') WHERE event_type = 'flow_progress' AND details:flow_progress.data_quality.expectations IS NOT NULL),
latest AS (SELECT update_id FROM ev ORDER BY timestamp DESC LIMIT 1)
SELECT split_part(flow_name, '.', 3) AS dataset, x.name AS expectation, sum(x.passed_records) AS passed, sum(x.failed_records) AS failed
FROM ev LATERAL VIEW explode(from_json(e, 'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) t AS x
WHERE update_id = (SELECT update_id FROM latest)
GROUP BY ALL ORDER BY failed DESC, dataset
```
| dataset | expectation | passed | failed |
|---|---|---|---|
| crm_accounts | has_registration_number | 998 | 367 |
| carrier_statement_lines | valid_policy_ref | 14265 | 272 |
| revenue_transactions | valid_billing_client_ref | 33074 | 233 |
| hc_clients | has_registration_number | 286 | 174 |
| placements | valid_policy_period | 16648 | 100 |
| revenue_transactions | valid_amount | 33208 | 99 |
| crm_contacts | plausible_email | 2284 | 64 |
| placements | commission_rate_is_ratio | 16698 | 50 |
| crm_accounts | valid_country | 1352 | 13 |
| crm_accounts | valid_account_name | 1359 | 6 |
| hc_clients | valid_client_name | 456 | 4 |
| billing_clients | valid_country | 1085 | 0 |
| billing_clients | valid_billing_client_id | 1085 | 0 |
| carrier_statement_lines | valid_commission_amount | 14537 | 0 |
| crm_accounts | valid_account_id | 1365 | 0 |
| crm_contacts | valid_account_ref | 2348 | 0 |
| hc_clients | valid_country | 460 | 0 |
| hc_policies | valid_client_ref | 4037 | 0 |
| hc_policies | valid_effective_date | 4037 | 0 |
| le_registry | valid_registration_number | 1805 | 0 |
| placement_insureds | valid_insured_id | 1380 | 0 |
| revenue_transactions | known_currency | 33307 | 0 |
| revenue_transactions | valid_transaction_date | 33307 | 0 |
### Quarantined rows by rule (nb_silver.dq_quarantine)
```sql
SELECT silver_table, failed_rule, rule_definition, count(*) AS rows FROM richasethi_febar_catalog.nb_silver.dq_quarantine GROUP BY ALL ORDER BY rows DESC
```
| silver_table | failed_rule | rule_definition | rows |
|---|---|---|---|
| carrier_statement_lines | valid_policy_ref | policy_ref IS NOT NULL | 272 |
| revenue_transactions | valid_billing_client_ref | billing_client_id IS NOT NULL | 233 |
| placements | valid_policy_period | expiry_date > inception_date | 100 |
| revenue_transactions | valid_amount | amount IS NOT NULL | 99 |
| placements | commission_rate_is_ratio | commission_rate BETWEEN 0 AND 0.5 | 50 |
| crm_accounts | valid_country | country_iso IN ('AE','AU','BR','CA','CH','DE','ES','FR','GB','HK','IE','IN','IT','JP','MX','NL','SE','SG','US','ZA') | 13 |
| crm_accounts | valid_account_name | account_name IS NOT NULL | 6 |
| hc_clients | valid_client_name | client_name IS NOT NULL | 4 |
### Sample quarantined records
```sql
SELECT silver_table, failed_rule, record_key, left(record, 180) AS record FROM richasethi_febar_catalog.nb_silver.dq_quarantine ORDER BY silver_table LIMIT 8
```
| silver_table | failed_rule | record_key | record |
|---|---|---|---|
| carrier_statement_lines | valid_policy_ref | Timberline Mutual/RADCLIFFE ROYAL DIGITAL PLC/2026-03-28 | {"carrier_name":"Timberline Mutual","statement_period":"2026-03-28","insured_name":"RADCLIFFE ROYAL DIGITAL PLC","line_of_business":"Technology E&O","commission_amount":71992.96,"c |
| carrier_statement_lines | valid_policy_ref | Timberline Mutual/Vantage First Pharma PTE. LTD./2026-01-28 | {"carrier_name":"Timberline Mutual","statement_period":"2026-01-28","insured_name":"Vantage First Pharma PTE. LTD.","line_of_business":"Product Liability","commission_amount":11227 |
| carrier_statement_lines | valid_policy_ref | Crestline Specialty/Newhaven Coatings FZE/2026-01-28 | {"carrier_name":"Crestline Specialty","statement_period":"2026-01-28","insured_name":"Newhaven Coatings FZE","line_of_business":"D&O","commission_amount":483616.32,"currency":"AED" |
| carrier_statement_lines | valid_policy_ref | Albion Mutual Insurance/Davenport Pharma Singapore Pte. Ltd./2026-01-28 | {"carrier_name":"Albion Mutual Insurance","statement_period":"2026-01-28","insured_name":"Davenport Pharma Singapore Pte. Ltd.","line_of_business":"Cyber","commission_amount":23530 |
| carrier_statement_lines | valid_policy_ref | Albion Mutual Insurance/Jarrow North Agri DAC/2026-02-28 | {"carrier_name":"Albion Mutual Insurance","statement_period":"2026-02-28","insured_name":"Jarrow North Agri DAC","line_of_business":"Marine Cargo","commission_amount":30212.22,"cur |
| carrier_statement_lines | valid_policy_ref | Albion Mutual Insurance/Tidewater North Bancorp International LIMITED/2026-09-28 | {"carrier_name":"Albion Mutual Insurance","statement_period":"2026-09-28","insured_name":"Tidewater North Bancorp International LIMITED","line_of_business":"D&O","commission_amount |
| carrier_statement_lines | valid_policy_ref | Crestline Specialty/Coldharbour Shipping Services GmbH/2026-08-28 | {"carrier_name":"Crestline Specialty","statement_period":"2026-08-28","insured_name":"Coldharbour Shipping Services GmbH","line_of_business":"Property","commission_amount":144647.6 |
| carrier_statement_lines | valid_policy_ref | Crestline Specialty/Quinton Components LLC/2026-09-28 | {"carrier_name":"Crestline Specialty","statement_period":"2026-09-28","insured_name":"Quinton Components LLC","line_of_business":"D&O","commission_amount":58628.98,"currency":"USD" |
### Row counts by layer
| layer | table | rows |
|---|---|---|
| bronze | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_billing_clients_1 | 1085 |
| bronze | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_billing_revenue_transactions_1 | 33307 |
| bronze | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_carrier_statements_layout_a_1 | 6266 |
| bronze | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_carrier_statements_layout_b_1 | 4107 |
| bronze | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_carrier_statements_layout_c_1 | 4164 |
| bronze | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_crm_accounts_1 | 1365 |
| bronze | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_crm_contacts_1 | 2348 |
| bronze | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_hc_clients_1 | 460 |
| bronze | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_hc_policies_1 | 4037 |
| bronze | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_le_registry_1 | 1805 |
| bronze | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_placement_insureds_1 | 1380 |
| bronze | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_placement_placements_1 | 16748 |
| bronze | billing_clients | 1085 |
| bronze | billing_revenue_transactions | 33307 |
| bronze | carrier_statements_layout_a | 6266 |
| bronze | carrier_statements_layout_b | 4107 |
| bronze | carrier_statements_layout_c | 4164 |
| bronze | crm_accounts | 1365 |
| bronze | crm_contacts | 2348 |
| bronze | hc_clients | 460 |
| bronze | hc_policies | 4037 |
| bronze | le_registry | 1805 |
| bronze | placement_insureds | 1380 |
| bronze | placement_placements | 16748 |
| silver | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_billing_clients_1 | 1085 |
| silver | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_carrier_statement_lines_1 | 14265 |
| silver | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_crm_accounts_1 | 1346 |
| silver | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_crm_contacts_1 | 2348 |
| silver | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_dq_quarantine_1 | 777 |
| silver | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_hc_clients_1 | 456 |
| silver | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_hc_policies_1 | 4037 |
| silver | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_le_registry_1 | 1805 |
| silver | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_party_source_records_1 | 4267 |
| silver | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_placement_insureds_1 | 1380 |
| silver | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_placements_1 | 16599 |
| silver | __materialization_mat_26ffcefa_3d12_4525_9b24_1ddc0638f6dd_revenue_transactions_1 | 32975 |
| silver | billing_clients | 1085 |
| silver | carrier_statement_lines | 14265 |
| silver | crm_accounts | 1346 |
| silver | crm_contacts | 2348 |
| silver | dq_quarantine | 777 |
| silver | hc_clients | 456 |
| silver | hc_policies | 4037 |
| silver | le_registry | 1805 |
| silver | party_source_records | 4267 |
| silver | placement_insureds | 1380 |
| silver | placements | 16599 |
| silver | revenue_transactions | 32975 |
| gold | __materialization_mat_84a8160e_b9cf_42ff_97df_d35d047b1cf5_client_revenue_summary_1 | 6763 |
| gold | __materialization_mat_84a8160e_b9cf_42ff_97df_d35d047b1cf5_commission_reconciliation_1 | 12721 |
| gold | __materialization_mat_84a8160e_b9cf_42ff_97df_d35d047b1cf5_dim_party_1 | 1862 |
| gold | __materialization_mat_84a8160e_b9cf_42ff_97df_d35d047b1cf5_er_run_history_1 | 1 |
| gold | __materialization_mat_84a8160e_b9cf_42ff_97df_d35d047b1cf5_fact_placements_1 | 20611 |
| gold | __materialization_mat_84a8160e_b9cf_42ff_97df_d35d047b1cf5_fact_revenue_1 | 38956 |
| gold | __materialization_mat_84a8160e_b9cf_42ff_97df_d35d047b1cf5_party_contacts_1 | 2320 |
| gold | __materialization_mat_84a8160e_b9cf_42ff_97df_d35d047b1cf5_party_hierarchy_1 | 1862 |
| gold | __materialization_mat_84a8160e_b9cf_42ff_97df_d35d047b1cf5_party_source_xref_1 | 4267 |
| gold | client_revenue_metrics | 38956 |
| gold | client_revenue_summary | 6763 |
| gold | commission_reconciliation | 12721 |
| gold | dim_party | 1862 |
| gold | er_run_history | 1 |
| gold | fact_placements | 20611 |
| gold | fact_revenue | 38956 |
| gold | party_contacts | 2320 |
| gold | party_hierarchy | 1862 |
| gold | party_source_xref | 4267 |
| app | __materialization_mat_84a8160e_b9cf_42ff_97df_d35d047b1cf5_app_client_revenue_summary_1 | 6558 |
| app | __materialization_mat_84a8160e_b9cf_42ff_97df_d35d047b1cf5_app_match_review_queue_1 | 50 |
| app | __materialization_mat_84a8160e_b9cf_42ff_97df_d35d047b1cf5_app_party_1 | 1811 |
| app | __materialization_mat_84a8160e_b9cf_42ff_97df_d35d047b1cf5_app_party_source_xref_1 | 4139 |
| app | __materialization_mat_84a8160e_b9cf_42ff_97df_d35d047b1cf5_app_placements_1 | 19933 |
| app | app_client_revenue_summary | 6558 |
| app | app_config | 1 |
| app | app_match_review_queue | 50 |
| app | app_party | 1811 |
| app | app_party_source_xref | 4139 |
| app | app_placements | 19933 |
| app | lb_steward_decisions_history | 0 |
