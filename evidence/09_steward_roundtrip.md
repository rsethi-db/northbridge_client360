_Collected 2026-10-16 22:00:42 UTC by `scripts/collect_evidence.py` as `richa.sethi@databricks.com` on https://fevm-richasethi-febar.cloud.databricks.com_

# Steward round trip: app -> Lakebase -> Lakehouse Sync -> entity resolution -> gold -> Lakebase

**Pair approved:** `MERIDIAN NORTH ENG. GERMANY AG` (HC_AMS:MERID14) + `MERIDIAN NORTH ENG. GERMANY AG` (HC_AMS:MERID15), model score 0.7882, LLM: MERGE - Identical names and country (DE); no conflicting registration (A has none). Address difference is consistent with legacy/branch system. Rule 1 applies: merge at medium confidence.

### Before
| record_key | party_id | party_name | source_record_count | source_systems |
|---|---|---|---|---|
| HC_AMS:MERID15 | NBP-212B6002AB | MERIDIAN NORTH ENG. GERMANY AG | 1 | ["HC_AMS"] |
| HC_AMS:MERID14 | NBP-D39E8AACE5 | MERIDIAN NORTH ENG. GERMANY AG | 1 | ["HC_AMS"] |

### 1. Approved in the app (Dash callback, HTTP 200)
```
{"multi":true,"response":{"decision-msg":{"children":{"props":{"children":"Recorded 'approve merge' for MERIDIAN NORTH ENG. GERMANY AG \u002f MERIDIAN NORTH ENG. GERMANY AG (decision f5f83eee). It's in Lakebase now and reaches Unity Catalog within seconds; run entity resolution to apply it.","className":"py-2","color":"success","dismissable":true},"type":"Alert","namespace":"dash_bootstrap_components"}}}}
```
### 2. Row written to Lakebase `steward.steward_decisions`
| decision_id | pair_id | decision | steward | decided_at |
|---|---|---|---|---|
| f5f83eee-367d-4db5-aa0a-b5578b356002 | 98ed43760737b4d9 | approve_merge | richa.sethi@databricks.com | 2026-10-16 21:52:03.108274+00:00 |

### 3. Lakehouse Sync landed it in Unity Catalog after ~13s (`nb_app.lb_steward_decisions_history`)
| decision_id | decision | steward | _pg_change_type | _timestamp |
|---|---|---|---|---|
| f5f83eee-367d-4db5-aa0a-b5578b356002 | approve_merge | richa.sethi@databricks.com | insert | 2026-10-16T21:52:03.678 |

### 4. Round-trip job run 285676953593398: SUCCESS
https://fevm-richasethi-febar.cloud.databricks.com/?o=7474655101081776#job/136708587905263/run/285676953593398

### After: both records now resolve to one golden party
| record_key | party_id | party_name | source_record_count | source_systems |
|---|---|---|---|---|
| HC_AMS:MERID15 | NBP-D39E8AACE5 | MERIDIAN NORTH ENG. GERMANY AG | 2 | ["HC_AMS"] |
| HC_AMS:MERID14 | NBP-D39E8AACE5 | MERIDIAN NORTH ENG. GERMANY AG | 2 | ["HC_AMS"] |

### Lakebase serving copy refreshed
| party_id | party_name | source_record_count |
|---|---|---|
| NBP-D39E8AACE5 | MERIDIAN NORTH ENG. GERMANY AG | 2 |
