# Genie acceptance test - space `01f1c9aa68f11c799fc6b7334d1d2027`
Run at 2026-10-16 21:44 UTC as `richa.sethi@databricks.com`

## What's our total revenue with Kestrel Industries plc across all entities?

**Genie answer:** (no text)

**Genie SQL:**
```sql
SELECT * FROM `richasethi_febar_catalog`.`nb_gold`.`client_total_revenue`(p_client_name => 'Kestrel Industries plc', p_fiscal_year => NULL)
```
**Genie result:**

| ultimate_parent_client | ultimate_parent_party_id | fiscal_year | total_client_revenue_usd | commission_income_usd | fee_income_usd | billed_entity_count |
|---|---|---|---|---|---|---|
| Kestrel Industries plc | NBP-DC5888FFA7 | 2025 | 3835598.67 | 2914133.17 | 921465.50 | 6 |
| Kestrel Industries plc | NBP-DC5888FFA7 | 2021 | 394925.27 | 379050.27 | 15875.00 | 2 |
| Kestrel Industries plc | NBP-DC5888FFA7 | 2022 | 2244281.79 | 1815147.29 | 429134.50 | 6 |
| Kestrel Industries plc | NBP-DC5888FFA7 | 2023 | 4570630.06 | 3419585.06 | 1151045.00 | 6 |
| Kestrel Industries plc | NBP-DC5888FFA7 | 2024 | 4190500.06 | 3181623.56 | 1008876.50 | 6 |
| Kestrel Industries plc | NBP-DC5888FFA7 | 2026 | 4282453.92 | 3391167.42 | 891286.50 | 6 |

**Ground truth (certified SQL):**
```sql
SELECT `Fiscal Year`, round(MEASURE(`Total Client Revenue`), 2) AS total FROM richasethi_febar_catalog.nb_gold.client_revenue_metrics WHERE `Ultimate Parent Client` = 'Kestrel Industries plc' GROUP BY ALL ORDER BY 1
```
| Fiscal Year | total |
|---|---|
| 2021 | 394925.27 |
| 2022 | 2244281.79 |
| 2023 | 4570630.06 |
| 2024 | 4190500.06 |
| 2025 | 3835598.67 |
| 2026 | 4282453.92 |

---

## Which acquired Harbor & Cole clients overlap with existing Northbridge clients?

**Genie answer:** (no text)

**Genie SQL:**
```sql
SELECT * FROM `richasethi_febar_catalog`.`nb_gold`.`harbor_cole_overlap_clients`()
```
**Genie result:**

| ultimate_parent_client | ultimate_parent_party_id | overlapping_entity | party_id | country_iso | source_systems | northbridge_revenue_prior_fy_usd | harbor_cole_revenue_prior_fy_usd |
|---|---|---|---|---|---|---|---|
| Fairhaven Royal Telecom Group GmbH | NBP-126405EE7D | Fairhaven Royal Telecom Asia Pacific Holdings Limited | NBP-067B31AF1F | HK | ["HC_AMS","NB_CRM"] | 0.00 | 488486.00 |
| Carrick Royal Engineering Ltd. | NBP-61F6F988D2 | Carrick Royal Engineering GmbH | NBP-B4BD47075A | DE | ["HC_AMS","NB_CRM","NB_PLACEMENT"] | 0.00 | 94353.96 |
| Brightwater North Energy plc | NBP-9B1156654B | Brightwater North Energy Trading K.K. | NBP-372EF353E1 | JP | ["HC_AMS","NB_CRM"] | 0.00 | 127389.31 |
| Yarrow First Retail Group Pte. Ltd. | NBP-5774381FEC | Lancaster Systems Limited | NBP-DDD94C4C8F | HK | ["HC_AMS","NB_BILLING","NB_CRM","NB_PLACEMENT"] | 373651.00 | 119093.79 |
| Osgood Global Maritime Corporation | NBP-D119ABD5A6 | Osgood Global Maritime Hong Kong Limited | NBP-9AD850C556 | HK | ["HC_AMS","NB_BILLING","NB_CRM","NB_PLACEMENT"] | 121634.14 | 29794.44 |
| Upland First Minerals N.V. | NBP-CC59EA2D61 | Upland First Minerals Germany AG | NBP-5AFA69CC3A | DE | ["HC_AMS","NB_BILLING","NB_CRM","NB_PLACEMENT"] | 28501.05 | 30009.67 |
| Quayside Global Engineering Inc. | NBP-CB3CFDEEFE | Quayside Global Engineering Ltd. | NBP-39F3423C1E | CA | ["HC_AMS","NB_BILLING","NB_CRM","NB_PLACEMENT"] | 124626.97 | 38526.17 |
| Carrick Royal Engineering Ltd. | NBP-61F6F988D2 | Carrick Royal Engineering Japan K.K. | NBP-C22949C411 | JP | ["HC_AMS","NB_BILLING","NB_PLACEMENT"] | 283472.80 | 131612.57 |
| Beaumont Logistics plc | NBP-1FA4CE3F77 | Greystone Solutions AG | NBP-A54F60EB23 | DE | ["HC_AMS","NB_CRM"] | 0.00 | 128028.41 |
| Lancaster Security Group Pte. Ltd. | NBP-A5CAFA42AA | Lancaster Security Asia Pacific Holdings Limited | NBP-41690A695E | HK | ["HC_AMS","NB_BILLING","NB_CRM","NB_PLACEMENT"] | 166993.71 | 155299.22 |
| Kingsway Global Agri Group Pte. Ltd. | NBP-0852F6B59B | Kingsway Global Agri United States Inc. | NBP-F2F324E914 | US | ["HC_AMS","NB_CRM","NB_PLACEMENT"] | 0.00 | 33229.64 |
| Halcyon Royal Properties plc | NBP-CF574B6EDA | Halcyon Royal Properties Germany GmbH | NBP-054F234161 | DE | ["HC_AMS","NB_BILLING","NB_CRM","NB_PLACEMENT"] | 43928.35 | 365845.22 |
| ... 140 more rows |

**Ground truth (certified SQL):**
```sql
SELECT count(*) AS overlapping_entities, count(DISTINCT ultimate_parent_party_id) AS client_groups FROM richasethi_febar_catalog.nb_gold.dim_party WHERE client_origin = 'Both'
```
| overlapping_entities | client_groups |
|---|---|
| 152 | 75 |

---

## Top 10 clients by commission income this year, rolled up to parent

**Genie answer:** Here are the **top 10 ultimate parent clients by commission income this year**. Commission income ranges from **$5,588,657.11** at the top to **$3,555,153.80** in 10th place, and in all 10 cases total client revenue is higher than commission income.

Some of the top values are:
- **Granite Global Industries LLC** — **$5,588,657.11** commission income; **$6,645,674.61** total client revenue
- **Kingsway Global Agri Group Pte. Ltd.** — **$4,948,459.85** commission income; **$5,713,413.65** total client revenue
- **Atlas Technologies B.V.** — **$4,640,182.63** commission income; **$5,065,882.93** total client revenue
- **Beaumont Logistics plc** — **$4,149,185.56** commission income; **$4,772,102.56** total client revenue
- **Brightwater Royal Properties Corporation** — **$4,080,500.34** commission income; **$4,442,107.84** total client revenue

**Genie SQL:**
```sql
SELECT `Ultimate Parent Client`, MEASURE(`Commission Income`) AS `commission_income_usd`, MEASURE(`Total Client Revenue`) AS `total_client_revenue_usd`
FROM `richasethi_febar_catalog`.`nb_gold`.`client_revenue_metrics`
WHERE `Fiscal Year` = year(current_date())
GROUP BY ALL
ORDER BY `commission_income_usd` DESC
LIMIT 10
```
**Genie result:**

| Ultimate Parent Client | commission_income_usd | total_client_revenue_usd |
|---|---|---|
| Granite Global Industries LLC | 5588657.11 | 6645674.61 |
| Kingsway Global Agri Group Pte. Ltd. | 4948459.85 | 5713413.65 |
| Atlas Technologies B.V. | 4640182.63 | 5065882.93 |
| Beaumont Logistics plc | 4149185.56 | 4772102.56 |
| Brightwater Royal Properties Corporation | 4080500.34 | 4442107.84 |
| Radcliffe Royal Digital plc | 4056820.71 | 4523435.55 |
| Osgood Industries SAS | 4036265.66 | 5213184.42 |
| Dunmore Global Resources Group plc | 3976071.43 | 5326460.83 |
| Brightwater Biosciences GmbH | 3808858.31 | 4581533.31 |
| Greystone United Farms Pte. Ltd. | 3555153.80 | 4218351.56 |

**Ground truth (certified SQL):**
```sql
SELECT `Ultimate Parent Client`, round(MEASURE(`Commission Income`), 2) AS commission FROM richasethi_febar_catalog.nb_gold.client_revenue_metrics WHERE `Fiscal Year` = year(current_date()) GROUP BY ALL ORDER BY commission DESC LIMIT 10
```
| Ultimate Parent Client | commission |
|---|---|
| Granite Global Industries LLC | 5588657.11 |
| Kingsway Global Agri Group Pte. Ltd. | 4948459.85 |
| Atlas Technologies B.V. | 4640182.63 |
| Beaumont Logistics plc | 4149185.56 |
| Brightwater Royal Properties Corporation | 4080500.34 |
| Radcliffe Royal Digital plc | 4056820.71 |
| Osgood Industries SAS | 4036265.66 |
| Dunmore Global Resources Group plc | 3976071.43 |
| Brightwater Biosciences GmbH | 3808858.31 |
| Greystone United Farms Pte. Ltd. | 3555153.80 |

---

## Which clients have placements with more than three carriers?

**Genie answer:** (no text)

**Genie SQL:**
```sql
SELECT * FROM `richasethi_febar_catalog`.`nb_gold`.`clients_by_carrier_count`(p_min_carriers => 4)
```
**Genie result:**

| ultimate_parent_client | ultimate_parent_party_id | carrier_count | in_force_placements | carriers |
|---|---|---|---|---|
| Islington First Industries Private Limited | NBP-C2B435DADD | 5 | 7 | ["Albion Mutual Insurance","Corsair Specialty Lines","Greatlake Casualty","Northsea Underwriting","Timberline Mutual"] |
| Whitcombe Royal Bancorp Group LLC | NBP-D60F9C6162 | 4 | 4 | ["Albion Mutual Insurance","Harbourline Re","Northsea Underwriting","Silverbirch Insurance AG"] |
| Osgood Global Maritime Corporation | NBP-D119ABD5A6 | 13 | 35 | ["Albion Mutual Insurance","Aurora Global Assurance","Beacon Hill Indemnity","Corsair Specialty Lines","Crestline Specialty","Greatlake Casualty","Harbourline Re","Knightsbridge Marine","Meridian Specialty Syndicate 4471","Northsea Underwriting","Pacific Rim Assurance","Timberline Mutual","Valora Seguros"] |
| Caldera North Industries Group Pty Ltd | NBP-6A2C003655 | 9 | 14 | ["Albion Mutual Insurance","Aurora Global Assurance","Beacon Hill Indemnity","Crestline Specialty","Harbourline Re","Knightsbridge Marine","Meridian Specialty Syndicate 4471","Silverbirch Insurance AG","Timberline Mutual"] |
| Northcote Digital Group plc | NBP-73D267876E | 4 | 4 | ["Beacon Hill Indemnity","Greatlake Casualty","Knightsbridge Marine","Valora Seguros"] |
| Upland First Minerals N.V. | NBP-CC59EA2D61 | 10 | 12 | ["Albion Mutual Insurance","Aurora Global Assurance","Beacon Hill Indemnity","Crestline Specialty","Knightsbridge Marine","Meridian Specialty Syndicate 4471","Northsea Underwriting","Silverbirch Insurance AG","Silverbirch Insurance Ag","Valora Seguros"] |
| Selwyn Technologies plc | NBP-E678696067 | 14 | 35 | ["Albion Mutual Insurance","Aurora Global Assurance","Corsair Specialty Lines","Crestline Specialty","Greatlake Casualty","Harbourline Re","Knightsbridge Marine","Meridian Specialty Syndicate 4471","Northsea Underwriting","Pacific Rim Assurance","Silverbirch Insurance AG","Silverbirch Insurance Ag","Timberline Mutual","Valora Seguros"] |
| Upland Metals Inc. | NBP-21898C7744 | 4 | 4 | ["Corsair Specialty Lines","Crestline Specialty","Greatlake Casualty","Valora Seguros"] |
| Holloway Global Leisure Group LLC | NBP-CF188236FB | 11 | 18 | ["Albion Mutual Insurance","Aurora Global Assurance","Beacon Hill Indemnity","Corsair Specialty Lines","Crestline Specialty","Knightsbridge Marine","Meridian Specialty Syndicate 4471","Northsea Underwriting","Pacific Rim Assurance","Silverbirch Insurance AG","Valora Seguros"] |
| Orion Brands Group Ltd. | NBP-4B503C09AE | 8 | 12 | ["Albion Mutual Insurance","Beacon Hill Indemnity","Crestline Specialty","Greatlake Casualty","Knightsbridge Marine","Meridian Specialty Syndicate 4471","Pacific Rim Assurance","Silverbirch Insurance AG"] |
| Alder Dynaimcs LIMITED | NBP-9FC18153EE | 4 | 4 | ["Beacon Hill Indemnity","Crestline Specialty","Northsea Underwriting","Silverbirch Insurance AG"] |
| Lowther First Leisure Inc. | NBP-D5963D6AD4 | 9 | 15 | ["Albion Mutual Insurance","Aurora Global Assurance","Corsair Specialty Lines","Harbourline Re","Knightsbridge Marine","Meridian Specialty Syndicate 4471","Northsea Underwriting","Silverbirch Insurance AG","Timberline Mutual"] |
| ... 352 more rows |

**Ground truth (certified SQL):**
```sql
SELECT count(*) AS clients FROM richasethi_febar_catalog.nb_gold.clients_by_carrier_count(4)
```
| clients |
|---|
| 364 |

---

## How many party records were merged by the entity resolution model last run?

**Genie answer:** (no text)

**Genie SQL:**
```sql
SELECT * FROM `richasethi_febar_catalog`.`nb_gold`.`latest_entity_resolution_run`()
```
**Genie result:**

| run_ts | source_records | golden_parties | records_merged | multi_system_parties | auto_match_pairs | review_band_pairs | steward_decisions_applied | model_version | pairwise_precision | pairwise_recall |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-16T21:37:49.675Z | 4267 | 1862 | 2405 | 1346 | 3610 | 51 | 0 | 1 | 1.0 | 0.9821 |

**Ground truth (certified SQL):**
```sql
SELECT records_merged, source_records, golden_parties FROM richasethi_febar_catalog.nb_gold.er_run_history WHERE is_latest_run
```
| records_merged | source_records | golden_parties |
|---|---|---|
| 2405 | 4267 | 1862 |

---
