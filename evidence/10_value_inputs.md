_Collected 2026-10-16 22:02:40 UTC by `scripts/collect_evidence.py` as `richa.sethi@databricks.com` on https://fevm-richasethi-febar.cloud.databricks.com_

# Business value inputs, computed from the built data

All figures are for the synthetic Northbridge book (452 corporate families). The README scales them with stated assumptions.

### 1. Harbor & Cole overlap: client groups served by both books before the acquisition (FY2025)
```sql
WITH overlap AS (SELECT DISTINCT ultimate_parent_party_id FROM richasethi_febar_catalog.nb_gold.dim_party WHERE client_origin = 'Both')
SELECT count(DISTINCT o.ultimate_parent_party_id) AS overlapping_client_groups,
       round(sum(CASE WHEN r.source_system = 'NB_BILLING' THEN r.amount_usd END)) AS northbridge_revenue_usd,
       round(sum(CASE WHEN r.source_system = 'HC_AMS' THEN r.amount_usd END)) AS harbor_cole_revenue_usd,
       round(sum(r.amount_usd)) AS combined_relationship_usd
FROM overlap o LEFT JOIN richasethi_febar_catalog.nb_gold.fact_revenue r ON r.ultimate_parent_party_id = o.ultimate_parent_party_id AND r.fiscal_year = 2025
```
| overlapping_client_groups | northbridge_revenue_usd | harbor_cole_revenue_usd | combined_relationship_usd |
|---|---|---|---|
| 75 | 63853128 | 25948931 | 89802058 |
### 2. Harbor & Cole-only client groups (cross-sell targets for Northbridge specialty lines)
```sql
SELECT count(*) AS hc_only_client_groups, round(sum(rev)) AS hc_revenue_fy2025_usd FROM (
  SELECT d.ultimate_parent_party_id, sum(r.amount_usd) AS rev FROM richasethi_febar_catalog.nb_gold.dim_party d
  LEFT JOIN richasethi_febar_catalog.nb_gold.fact_revenue r ON r.party_id = d.party_id AND r.fiscal_year = 2025
  GROUP BY 1 HAVING bool_and(d.client_origin = 'Harbor & Cole'))
```
| hc_only_client_groups | hc_revenue_fy2025_usd |
|---|---|
| 224 | 34506733 |
### 3. Commission leakage: carrier statements vs booked commission (all years, USD)
```sql
SELECT c.reconciliation_status, count(*) AS placements,
       round(sum(abs(c.variance_local) * f.fx_rate_to_usd)) AS abs_variance_usd,
       round(sum(c.booked_commission * f.fx_rate_to_usd)) AS booked_commission_usd
FROM richasethi_febar_catalog.nb_gold.commission_reconciliation c JOIN richasethi_febar_catalog.nb_silver.placements p USING (placement_id) JOIN (SELECT DISTINCT currency, fx_rate_to_usd FROM richasethi_febar_catalog.nb_silver.revenue_transactions WHERE fx_rate_to_usd IS NOT NULL) f ON f.currency = p.currency
GROUP BY 1 ORDER BY 1
```
| reconciliation_status | placements | abs_variance_usd | booked_commission_usd |
|---|---|---|---|
| Missing from statement | 311 | 2.2824063E7 | 2.1068856E7 |
| Reconciled | 10415 | 18.0 | 1.06432605E9 |
| Variance | 1995 | 6.5644764E7 | 1.49203496E8 |
### 4. Duplicate-resolution effort: what the model decided vs what needed a human
```sql
SELECT source_records, golden_parties, records_merged, auto_match_pairs, review_band_pairs, candidate_pairs,
       round(100 * review_band_pairs / (auto_match_pairs + review_band_pairs), 1) AS pct_of_match_decisions_needing_a_human
FROM richasethi_febar_catalog.nb_ml.er_run_log ORDER BY run_ts DESC LIMIT 1
```
| source_records | golden_parties | records_merged | auto_match_pairs | review_band_pairs | candidate_pairs | pct_of_match_decisions_needing_a_human |
|---|---|---|---|---|---|---|
| 4267 | 1861 | 2406 | 3610 | 51 | 36687 | 1.4 |
### 5. Restricted-segment exposure governed by policy
```sql
SELECT count(DISTINCT ultimate_parent_party_id) AS restricted_client_groups, count(*) AS restricted_entities,
       round((SELECT sum(amount_usd) FROM richasethi_febar_catalog.nb_gold.fact_revenue WHERE is_restricted AND fiscal_year = 2025)) AS restricted_revenue_fy2025_usd
FROM richasethi_febar_catalog.nb_gold.dim_party WHERE is_restricted
```
| restricted_client_groups | restricted_entities | restricted_revenue_fy2025_usd |
|---|---|---|
| 28 | 51 | 16444247 |
### 6. Book size
```sql
SELECT count(DISTINCT ultimate_parent_party_id) AS client_groups, count(*) AS legal_entities,
       round((SELECT sum(amount_usd) FROM richasethi_febar_catalog.nb_gold.fact_revenue WHERE fiscal_year = 2025)) AS revenue_fy2025_usd FROM richasethi_febar_catalog.nb_gold.dim_party
```
| client_groups | legal_entities | revenue_fy2025_usd |
|---|---|---|
| 829 | 1861 | 474490038 |
