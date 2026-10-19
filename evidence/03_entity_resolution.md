_Collected 2026-10-16 21:47:51 UTC by `scripts/collect_evidence.py` as `richa.sethi@databricks.com` on https://fevm-richasethi-febar.cloud.databricks.com_

# Entity resolution, match model and GenAI assist

### Entity resolution run log
```sql
SELECT * FROM richasethi_febar_catalog.nb_ml.er_run_log ORDER BY run_ts DESC
```
| auto_match_pairs | candidate_pairs | golden_parties | merges_blocked_by_constraints | model_name | model_version | multi_record_parties | multi_system_parties | pairwise_precision | pairwise_recall | records_merged | records_reassigned_vs_previous_run | review_band_pairs | run_id | run_ts | source_records | steward_decisions_applied |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3610 | 36687 | 1862 | 22 | richasethi_febar_catalog.nb_ml.party_match_model | 1 | 1375 | 1346 | 1.0 | 0.9821 | 2405 | 0 | 51 | 68b61fd9-8e53-4a2a-87af-172d07b685d7 | 2026-10-16T21:37:49.675Z | 4267 | 0 |
### Headline client: every source record unified into Kestrel Industries plc
```sql
SELECT x.party_id, x.source_system, x.source_record_id, x.source_name, x.match_method, x.match_confidence
FROM richasethi_febar_catalog.nb_ml.party_xref x WHERE x.party_id = (SELECT party_id FROM richasethi_febar_catalog.nb_gold.dim_party WHERE party_name = 'Kestrel Industries plc')
ORDER BY x.source_system
```
| party_id | source_system | source_record_id | source_name | match_method | match_confidence |
|---|---|---|---|---|---|
| NBP-DC5888FFA7 | HC_AMS | KESTR03 | KESTREL INDUSTRIES PLC | model | 0.9999 |
| NBP-DC5888FFA7 | HC_AMS | KESTR04 | KESTREL INDS PLC | model | 0.9999 |
| NBP-DC5888FFA7 | NB_BILLING | BL-001085 | Kestrel Industries Public Limited Company | model | 0.9999 |
| NBP-DC5888FFA7 | NB_CRM | 001NB0001358 | Kestrel Industries plc | model | 0.9999 |
| NBP-DC5888FFA7 | NB_CRM | 001NB0001359 | Kestrel Industries PLC | model | 0.9999 |
| NBP-DC5888FFA7 | NB_PLACEMENT | INS0001378 | Kestrel Industries plc | model | 0.9999 |
### Kestrel legal-entity hierarchy
```sql
SELECT party_id, party_name, country_iso, hierarchy_level, parent_party_name, parent_link_source, source_record_count, source_systems
FROM richasethi_febar_catalog.nb_gold.dim_party WHERE ultimate_parent_name = 'Kestrel Industries plc' ORDER BY hierarchy_level, party_name
```
| party_id | party_name | country_iso | hierarchy_level | parent_party_name | parent_link_source | source_record_count | source_systems |
|---|---|---|---|---|---|---|---|
| NBP-DC5888FFA7 | Kestrel Industries plc | GB | 0 |  |  | 6 | ["HC_AMS","NB_BILLING","NB_CRM","NB_PLACEMENT"] |
| NBP-E6BCB7E4BC | Kestrel Industries (Singapore) Pte. Ltd. | SG | 1 | Kestrel Industries plc | LE_REGISTRY | 3 | ["NB_BILLING","NB_CRM","NB_PLACEMENT"] |
| NBP-DD9ACBC4F2 | Kestrel Industries Europe B.V. | NL | 1 | Kestrel Industries plc | LE_REGISTRY | 2 | ["NB_CRM","NB_PLACEMENT"] |
| NBP-2802C93E77 | Kestrel Industries Holdings Inc. | US | 1 | Kestrel Industries plc | LE_REGISTRY | 3 | ["NB_BILLING","NB_CRM","NB_PLACEMENT"] |
| NBP-0227B98FE5 | Kestrel Marine Services Limited | GB | 1 | Kestrel Industries plc | LE_REGISTRY | 4 | ["HC_AMS","NB_BILLING","NB_CRM","NB_PLACEMENT"] |
| NBP-A1523F84E1 | Bluewater Coatings Inc. | US | 2 | Kestrel Industries Holdings Inc. | LE_REGISTRY | 2 | ["NB_BILLING","NB_PLACEMENT"] |
| NBP-5C43D9E3CD | Kestrel Industries GmbH | DE | 2 | Kestrel Industries Europe B.V. | LE_REGISTRY | 1 | ["NB_CRM"] |
| NBP-C03CB4D566 | Kestrel Logistics LLC | US | 2 | Kestrel Industries Holdings Inc. | LE_REGISTRY | 3 | ["NB_BILLING","NB_CRM","NB_PLACEMENT"] |
### True negative: same trading name, different company - kept separate
```sql
SELECT party_id, party_name, country_iso, registration_number, ultimate_parent_name FROM richasethi_febar_catalog.nb_gold.dim_party
WHERE party_name LIKE 'Kestrel%' AND ultimate_parent_name <> 'Kestrel Industries plc'
```
| party_id | party_name | country_iso | registration_number | ultimate_parent_name |
|---|---|---|---|---|
| NBP-89968B7E24 | Kestrel Systems K.K. | JP | 4914109525409 | Yarrow Engineering Corporation |
| NBP-E547CA951A | Kestrel Solutions LLC | US | 93-8319663 | Meridian North Aerospace Group LLC |
| NBP-437503BA43 | Kestrel Industries Pty Ltd | AU | 692 764 148 | Kestrel Industries Pty Ltd |
| NBP-82AE17BB00 | Kestrel Foods Limited | GB | 03775603 | Kestrel Foods Limited |
| NBP-365F0AD444 | Kestrel Systems LLC | US |  | Kestrel Systems LLC |
### Match score distribution
```sql
SELECT match_band, count(*) AS pairs, round(min(match_score), 3) AS min_score, round(max(match_score), 3) AS max_score FROM richasethi_febar_catalog.nb_ml.match_candidates_scored GROUP BY 1 ORDER BY 2 DESC
```
| match_band | pairs | min_score | max_score |
|---|---|---|---|
| no_match | 33026 | 0.0 | 0.298 |
| auto_match | 3610 | 0.813 | 1.0 |
| review | 51 | 0.311 | 0.796 |
### LLM assessments of review-band pairs
```sql
SELECT llm_endpoint, llm_recommendation, llm_confidence, count(*) AS pairs FROM richasethi_febar_catalog.nb_ml.match_review_queue GROUP BY ALL ORDER BY pairs DESC
```
| llm_endpoint | llm_recommendation | llm_confidence | pairs |
|---|---|---|---|
| databricks-claude-sonnet-4-6 | MERGE | medium | 25 |
| databricks-claude-sonnet-4-6 | NEEDS_MORE_INFO | medium | 17 |
| databricks-claude-sonnet-4-6 | KEEP_SEPARATE | high | 5 |
| databricks-claude-sonnet-4-6 | MERGE | high | 2 |
| databricks-claude-sonnet-4-6 | KEEP_SEPARATE | medium | 2 |
### Sample LLM rationales (stored for stewards)
```sql
SELECT left_name, right_name, match_score, llm_recommendation, llm_rationale FROM richasethi_febar_catalog.nb_ml.match_review_queue ORDER BY pair_id LIMIT 6
```
| left_name | right_name | match_score | llm_recommendation | llm_rationale |
|---|---|---|---|---|
| Bramwell Global Stores Services Limited | Bramwell Global Stores Svcs DAC | 0.347 | NEEDS_MORE_INFO | Both IE entities share "Bramwell Global Stores" core name; "Services Limited" vs "Svcs DAC" could be same entity or a distinct DAC subsidiary. Different legal forms (Ltd vs DAC) and addresses warrant confirmation. |
| RADCLIFFE ROYAL DIGITAL DAC | Radcliffe Royal Digital Limited | 0.4055 | NEEDS_MORE_INFO | Same country IE, similar core name, but legal suffix differs: "DAC" (Designated Activity Company) vs "Limited" — these are distinct Irish legal forms. No registration on B to confirm. Suffix difference may indicate separate entities. |
| Tamworth North Resources Trading S.R.L. | Tamworth North Resources Trading Srl | 0.575 | MERGE | Names are identical after normalising case and suffix (S.R.L.=Srl); same country (IT). No conflicting registration (A has none). Differing addresses consistent with branch/legacy systems. |
| BELMONT COATINGS NV | Belmont Coatings B.V. | 0.6133 | KEEP_SEPARATE | Same name and country, but NV and B.V. are distinct legal entity types under Dutch law — different registrations, different legal structures. These are separate legal entities. |
| Umbra Minerals Asia Pacific Hold. Ltd | Umbra Minerals Asia Pacific Holdings LIMITED | 0.7724 | MERGE | Names are identical after expanding "Hold." to "Holdings" and normalising suffix. Same country (HK). No conflicting registration (B missing). Differing addresses consistent with legacy/branch systems. |
| ATLAS TECHNOLOGIES ASIA PCAIFIC HOLD. LIMITED | Atlas Technologies Asia Pacific Holdings Liimted | 0.3579 | MERGE | Same entity: both HK, names match after fixing typos ("PCAIFIC"→"Pacific", "Liimted"→"Limited"). Registrations 22941748 vs 22947148 differ by one transposed digit (4↔7 in positions 5–6). Addresses are legacy/branch variants. |
### Unity Catalog registered model `nb_ml.party_match_model`
| version | status | aliases | comment |
|---|---|---|---|
| 1 | READY |  | AUC 0.9998, precision@0.8 0.982, recall@0.8 0.974 |

### MLflow training runs
| run_id | metric | value |
|---|---|---|
| 470617282b7b | auc | 0.9998 |
| 470617282b7b | avg_precision | 0.9982 |
| 470617282b7b | f1_at_0_5 | 0.9818 |
| 470617282b7b | precision_at_0_8 | 0.9822 |
| 470617282b7b | recall_at_0_8 | 0.9744 |
| 470617282b7b | review_band_share | 0.0018 |
| 470617282b7b | test_pairs | 10310.0 |
| 470617282b7b | train_pairs | 26377.0 |
