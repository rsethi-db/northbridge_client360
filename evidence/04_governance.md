_Collected 2026-10-16 21:51:18 UTC by `scripts/collect_evidence.py` as `richa.sethi@databricks.com` on https://fevm-richasethi-febar.cloud.databricks.com_

# Unity Catalog governance

### ABAC policies on the gold schema
| policy | type | to | match columns | comment |
|---|---|---|---|---|
| nb_hide_restricted_clients | POLICY_TYPE_ROW_FILTER | account users | has_tag('rls_filter_key') | Restricted client segment (defence, sovereign & government) is visible only to the restricted-clients group. Applies to every gold table whose restriction flag is tagged rls_filter_key. |
| nb_mask_email_address | POLICY_TYPE_COLUMN_MASK | account users | has_tag('class.email_address') | Client contact PII (class.email_address) is masked for everyone outside the PII readers group. |
| nb_mask_name | POLICY_TYPE_COLUMN_MASK | account users | has_tag('class.name') | Client contact PII (class.name) is masked for everyone outside the PII readers group. |
| nb_mask_phone_number | POLICY_TYPE_COLUMN_MASK | account users | has_tag('class.phone_number') | Client contact PII (class.phone_number) is masked for everyone outside the PII readers group. |

### Table tags (certified gold, uncertified silver, SOX, confidentiality)
```sql
SELECT schema_name, table_name, collect_list(concat(tag_name, '=', coalesce(tag_value, ''))) AS tags FROM richasethi_febar_catalog.information_schema.table_tags
WHERE schema_name IN ('nb_silver', 'nb_gold') GROUP BY ALL ORDER BY 1, 2
```
| schema_name | table_name | tags |
|---|---|---|
| nb_gold | client_revenue_metrics | ["system.certification_status=certified","certified=true","sox_relevant=true","confidentiality=confidential"] |
| nb_gold | client_revenue_summary | ["system.certification_status=certified","layer=gold","certified=true","sox_relevant=true","confidentiality=confidential"] |
| nb_gold | commission_reconciliation | ["confidentiality=confidential","system.certification_status=certified","certified=true","layer=gold","sox_relevant=true"] |
| nb_gold | dim_party | ["system.certification_status=certified","certified=true","confidentiality=confidential","layer=gold"] |
| nb_gold | er_run_history | ["system.certification_status=certified","layer=gold","certified=true","confidentiality=internal"] |
| nb_gold | fact_placements | ["certified=true","confidentiality=confidential","layer=gold","system.certification_status=certified"] |
| nb_gold | fact_revenue | ["system.certification_status=certified","layer=gold","sox_relevant=true","certified=true","confidentiality=confidential"] |
| nb_gold | party_contacts | ["confidentiality=restricted","system.certification_status=certified","layer=gold","certified=true"] |
| nb_gold | party_hierarchy | ["certified=true","layer=gold","system.certification_status=certified","confidentiality=confidential"] |
| nb_gold | party_source_xref | ["confidentiality=confidential","certified=true","system.certification_status=certified","layer=gold"] |
| nb_silver | billing_clients | ["layer=silver","confidentiality=confidential","certified=false"] |
| nb_silver | carrier_statement_lines | ["certified=false","confidentiality=internal","layer=silver"] |
| nb_silver | crm_accounts | ["confidentiality=confidential","layer=silver","certified=false"] |
| nb_silver | crm_contacts | ["confidentiality=restricted","layer=silver","certified=false"] |
| nb_silver | dq_quarantine | ["layer=silver","confidentiality=internal","certified=false"] |
| nb_silver | hc_clients | ["confidentiality=confidential","certified=false","layer=silver"] |
| nb_silver | hc_policies | ["layer=silver","certified=false","sox_relevant=true","confidentiality=confidential"] |
| nb_silver | le_registry | ["confidentiality=internal","certified=false","layer=silver"] |
| nb_silver | party_source_records | ["certified=false","confidentiality=confidential","layer=silver"] |
| nb_silver | placement_insureds | ["confidentiality=confidential","certified=false","layer=silver"] |
| nb_silver | placements | ["certified=false","confidentiality=confidential","layer=silver"] |
| nb_silver | revenue_transactions | ["certified=false","confidentiality=confidential","layer=silver","sox_relevant=true"] |
### Column tags driving ABAC (rls_filter_key, class.*)
```sql
SELECT schema_name, table_name, column_name, tag_name, tag_value FROM richasethi_febar_catalog.information_schema.column_tags
WHERE schema_name = 'nb_gold' ORDER BY table_name, column_name
```
| schema_name | table_name | column_name | tag_name | tag_value |
|---|---|---|---|---|
| nb_gold | client_revenue_summary | is_restricted | rls_filter_key |  |
| nb_gold | commission_reconciliation | is_restricted | rls_filter_key |  |
| nb_gold | dim_party | address_line1 | class.street_address |  |
| nb_gold | dim_party | address_line1 | pii | address |
| nb_gold | dim_party | is_restricted | rls_filter_key |  |
| nb_gold | fact_placements | is_restricted | rls_filter_key |  |
| nb_gold | fact_revenue | is_restricted | rls_filter_key |  |
| nb_gold | party_contacts | contact_name | class.name |  |
| nb_gold | party_contacts | email | class.email_address |  |
| nb_gold | party_contacts | is_restricted | rls_filter_key |  |
| nb_gold | party_contacts | phone | class.phone_number |  |
| nb_gold | party_hierarchy | is_restricted | rls_filter_key |  |
| nb_gold | party_source_xref | is_restricted | rls_filter_key |  |
### Masking in effect for the current user (not in northbridge_pii_readers)
```sql
SELECT contact_id, contact_name, title, email, phone FROM richasethi_febar_catalog.nb_gold.party_contacts LIMIT 5
```
| contact_id | contact_name | title | email | phone |
|---|---|---|---|---|
| 003NB0001571 | *** REDACTED *** | Group Risk Manager | ***@fairhaven.com | *** REDACTED *** |
| 003NB0000247 | *** REDACTED *** | Head of Insurance | ***@atlas.co.uk | *** REDACTED *** |
| 003NB0001702 | *** REDACTED *** | Risk & Insurance Director | ***@brightwater.de | *** REDACTED *** |
| 003NB0000883 | *** REDACTED *** | Head of Insurance | ***@fenwick.net | *** REDACTED *** |
| 003NB0000591 | *** REDACTED *** | Finance Director | ***@brightwater.co.uk | *** REDACTED *** |
### Revenue ties to the dollar: metric view vs fact vs app serving table
```sql
SELECT (SELECT MEASURE(`Total Client Revenue`) FROM richasethi_febar_catalog.nb_gold.client_revenue_metrics WHERE `Fiscal Year` = 2025) AS metric_view_fy2025,
       (SELECT sum(amount_usd) FROM richasethi_febar_catalog.nb_gold.fact_revenue WHERE fiscal_year = 2025) AS fact_revenue_fy2025,
       (SELECT sum(total_revenue_usd) FROM richasethi_febar_catalog.nb_gold.client_revenue_summary WHERE fiscal_year = 2025) AS revenue_summary_fy2025
```
| metric_view_fy2025 | fact_revenue_fy2025 | revenue_summary_fy2025 |
|---|---|---|
| 474490037.86 | 474490037.86 | 474490037.86 |
### Metric view definition
```sql
SELECT table_name, comment FROM richasethi_febar_catalog.information_schema.tables WHERE table_schema = 'nb_gold' AND table_name = 'client_revenue_metrics'
```
| table_name | comment |
|---|---|
| client_revenue_metrics | Certified definition of Northbridge client revenue. Total Client Revenue = SUM of fee and commission income in USD (net of commission adjustments) from gold.fact_revenue, across Northbridge billing and the Harbor & Cole AMS. Premium is never revenue. Subsidiaries roll up to the Ultimate Parent Client. Fiscal year = calendar year. Finance, placement, the Client 360 app and Genie all use this definition. |
### ABAC row filter toggle: richa.sethi@databricks.com removed from `northbridge_restricted_clients`, then re-added
**In the group:**
| in_restricted_group | parties_visible | restricted_parties_visible | fy2025_revenue_visible |
|---|---|---|---|
| true | 1862 | 51 | 474490037.86 |

**Removed from the group** (policy took effect after 199s):
| in_restricted_group | parties_visible | restricted_parties_visible | fy2025_revenue_visible |
|---|---|---|---|
| false | 1811 | 0 | 458045791.19 |

**Genie, asked while outside the group:** There are **0 restricted clients** in the visible data, and total 2025 revenue for restricted clients is **USD 0.00**. In this result, restricted client count and 2025 revenue are both **zero**.

Membership restored afterwards.
