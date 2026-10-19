_Collected 2026-10-16 22:02:26 UTC by `scripts/collect_evidence.py` as `richa.sethi@databricks.com` on https://fevm-richasethi-febar.cloud.databricks.com_

# Lakebase operational serving

### Synced tables (UC -> Lakebase, snapshot mode)
| synced table | source projection | state | last sync |
|---|---|---|---|
| nb_serving.party | nb_app.app_party | SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE |  |
| nb_serving.party_source_xref | nb_app.app_party_source_xref | SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE |  |
| nb_serving.client_revenue_summary | nb_app.app_client_revenue_summary | SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE |  |
| nb_serving.placements | nb_app.app_placements | SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE |  |
| nb_serving.match_review_queue | nb_app.app_match_review_queue | SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE |  |

### Postgres row counts
| t | count |
|---|---|
| party | 1810 |
| placements | 19933 |
| match_review_queue | 50 |
| steward_decisions | 1 |

### Restricted segment is never copied to Lakebase
| defence_rows | rows |
|---|---|
| 0 | 1810 |

### Lakehouse Sync (Lakebase -> UC) configs
```json
{
  "cdf_configs": [
    {
      "name": "projects/northbridge-client360/branches/production/databases/databricks-postgres/cdf-configs/nb_steward_decisions",
      "catalog": "richasethi_febar_catalog",
      "schema": "nb_app",
      "create_time": "2026-10-16T21:43:10.144Z",
      "cdf_config_id": "nb_steward_decisions",
      "postgres_schema": "steward"
    }
  ]
}
```
