_Collected 2026-10-16 22:02:34 UTC by `scripts/collect_evidence.py` as `richa.sethi@databricks.com` on https://fevm-richasethi-febar.cloud.databricks.com_

# Databricks App selftest (`/api/selftest`, called as the signed-in user)

Exercises Lakebase search + client view, the on-behalf-of-user restricted path, the metric-view tie-out, the steward queue and Genie lookup.

```json
{
  "Kestrel Industries plc": {
    "client_view": {
      "hierarchy": [
        {
          "country_iso": "GB",
          "hierarchy_level": 0,
          "parent_party_id": null,
          "party_id": "NBP-DC5888FFA7",
          "party_name": "Kestrel Industries plc"
        },
        {
          "country_iso": "SG",
          "hierarchy_level": 1,
          "parent_party_id": "NBP-DC5888FFA7",
          "party_id": "NBP-E6BCB7E4BC",
          "party_name": "Kestrel Industries (Singapore) Pte. Ltd."
        },
        {
          "country_iso": "NL",
          "hierarchy_level": 1,
          "parent_party_id": "NBP-DC5888FFA7",
          "party_id": "NBP-DD9ACBC4F2",
          "party_name": "Kestrel Industries Europe B.V."
        },
        {
          "country_iso": "US",
          "hierarchy_level": 1,
          "parent_party_id": "NBP-DC5888FFA7",
          "party_id": "NBP-2802C93E77",
          "party_name": "Kestrel Industries Holdings Inc."
        },
        {
          "country_iso": "GB",
          "hierarchy_level": 1,
          "parent_party_id": "NBP-DC5888FFA7",
          "party_id": "NBP-0227B98FE5",
          "party_name": "Kestrel Marine Services Limited"
        },
        {
          "country_iso": "US",
          "hierarchy_level": 2,
          "parent_party_id": "NBP-2802C93E77",
          "party_id": "NBP-A1523F84E1",
          "party_name": "Bluewater Coatings Inc."
        },
        {
          "country_iso": "DE",
          "hierarchy_level": 2,
          "parent_party_id": "NBP-DD9ACBC4F2",
          "party_id": "NBP-5C43D9E3CD",
          "party_name": "Kestrel Industries GmbH"
        },
        {
          "country_iso": "US",
          "hierarchy_level": 2,
          "parent_party_id": "NBP-2802C93E77",
          "party_id": "NBP-C03CB4D566",
          "party_name": "Kestrel Logistics LLC"
        }
      ],
      "legal_entities": 8,
      "ms": 25,
      "placements": 120,
      "revenue_by_fiscal_year_usd": {
        "2021": 394925.27,
        "2022": 2244281.79,
        "2023": 4570630.06,
        "2024": 4190500.06,
        "2025": 3835598.67,
        "2026": 4282453.92
      },
      "source": "Lakebase",
      "source_records": 24,
      "source_systems": [
        "HC_AMS",
        "NB_BILLING",
        "NB_CRM",
        "NB_PLACEMENT"
      ]
    },
    "entitlements": {
      "pii": false,
      "restricted": true,
      "steward": true,
      "user": "richa.sethi@databricks.com"
    },
    "genie_space_url": "https://fevm-richasethi-febar.cloud.databricks.com/genie/rooms/01f1c9aa68f11c799fc6b7334d1d2027",
    "metric_view_check": {
      "app_usd": 3835598.67,
      "fiscal_year": 2025,
      "matches_to_the_cent": true,
      "metric_view_usd": 3835598.67
    },
    "recent_decisions": 1,
    "search": {
      "hits": 8,
      "ms": 1106,
      "query": "Kestrel Industries plc",
      "restricted_hits": 0,
      "top": [
        {
          "country_iso": "GB",
          "hierarchy_level": 0,
          "is_restricted": false,
          "party_id": "NBP-DC5888FFA7",
          "party_name": "Kestrel Industries plc"
        },
        {
          "country_iso": "SG",
          "hierarchy_level": 1,
          "is_restricted": false,
          "party_id": "NBP-E6BCB7E4BC",
          "party_name": "Kestrel Industries (Singapore) Pte. Ltd."
        },
        {
          "country_iso": "NL",
          "hierarchy_level": 1,
          "is_restricted": false,
          "party_id": "NBP-DD9ACBC4F2",
          "party_name": "Kestrel Industries Europe B.V."
        },
        {
          "country_iso": "US",
          "hierarchy_level": 1,
          "is_restricted": false,
          "party_id": "NBP-2802C93E77",
          "party_name": "Kestrel Industries Holdings Inc."
        },
        {
          "country_iso": "GB",
          "hierarchy_level": 1,
          "is_restricted": false,
          "party_id": "NBP-0227B98FE5",
          "party_name": "Kestrel Marine Services Limited"
        }
      ]
    },
    "steward_queue": {
      "by_llm_recommendation": {
        "KEEP_SEPARATE": 7,
        "MERGE": 25,
        "NEEDS_MORE_INFO": 17
      },
      "pending_pairs": 49
    }
  },
  "Ironclad Security plc": {
    "client_view": {
      "hierarchy": [
        {
          "country_iso": "GB",
          "hierarchy_level": 0,
          "parent_party_id": null,
          "party_id": "NBP-EF30E3CF74",
          "party_name": "Ironclad Security plc"
        },
        {
          "country_iso": "HK",
          "hierarchy_level": 1,
          "parent_party_id": "NBP-EF30E3CF74",
          "party_id": "NBP-420675BCEB",
          "party_name": "Ironclad Security Asia Pacific Holdings Limited"
        },
        {
          "country_iso": "IE",
          "hierarchy_level": 1,
          "parent_party_id": "NBP-EF30E3CF74",
          "party_id": "NBP-27E90B96E1",
          "party_name": "Ironclad Security Europe Holdings DAC"
        },
        {
          "country_iso": "US",
          "hierarchy_level": 1,
          "parent_party_id": "NBP-EF30E3CF74",
          "party_id": "NBP-AE53DA3685",
          "party_name": "Ironclad Security Services LLC"
        },
        {
          "country_iso": "BR",
          "hierarchy_level": 2,
          "parent_party_id": "NBP-420675BCEB",
          "party_id": "NBP-8B14EFD3A7",
          "party_name": "Ironclad Security Brazil Ltda."
        },
        {
          "country_iso": "HK",
          "hierarchy_level": 2,
          "parent_party_id": "NBP-420675BCEB",
          "party_id": "NBP-8444BE92E2",
          "party_name": "Ironclad Security Limited"
        }
      ],
      "legal_entities": 6,
      "ms": 2926,
      "placements": 72,
      "revenue_by_fiscal_year_usd": {
        "2022": 1153314.11,
        "2023": 2661393.28,
        "2024": 3067553.61,
        "2025": 3342099.41,
        "2026": 2628785.05
      },
      "source": "UC gold (on behalf of user)",
      "source_records": 15,
      "source_systems": [
        "HC_AMS",
        "NB_BILLING",
        "NB_CRM",
        "NB_PLACEMENT"
      ]
    },
    "entitlements": {
      "pii": false,
      "restricted": true,
      "steward": true,
      "user": "richa.sethi@databricks.com"
    },
    "genie_space_url": "https://fevm-richasethi-febar.cloud.databricks.com/genie/rooms/01f1c9aa68f11c799fc6b7334d1d2027",
    "metric_view_check": {
      "app_usd": 3342099.41,
      "fiscal_year": 2025,
      "matches_to_the_cent": true,
      "metric_view_usd": 3342099.41
    },
    "recent_decisions": 1,
    "search": {
      "hits": 6,
      "ms": 942,
      "query": "Ironclad Security plc",
      "restricted_hits": 6,
      "top": [
        {
          "country_iso": "GB",
          "hierarchy_level": 0,
          "is_restricted": true,
          "party_id": "NBP-EF30E3CF74",
          "party_name": "Ironclad Security plc"
        },
        {
          "country_iso": "HK",
          "hierarchy_level": 1,
          "is_restricted": true,
          "party_id": "NBP-420675BCEB",
          "party_name": "Ironclad Security Asia Pacific Holdings Limited"
        },
        {
          "country_iso": "IE",
          "hierarchy_level": 1,
          "is_restricted": true,
          "party_id": "NBP-27E90B96E1",
          "party_name": "Ironclad Security Europe Holdings DAC"
        },
        {
          "country_iso": "US",
          "hierarchy_level": 1,
          "is_restricted": true,
          "party_id": "NBP-AE53DA3685",
          "party_name": "Ironclad Security Services LLC"
        },
        {
          "country_iso": "BR",
          "hierarchy_level": 2,
          "is_restricted": true,
          "party_id": "NBP-8B14EFD3A7",
          "party_name": "Ironclad Security Brazil Ltda."
        }
      ]
    },
    "steward_queue": {
      "by_llm_recommendation": {
        "KEEP_SEPARATE": 7,
        "MERGE": 25,
        "NEEDS_MORE_INFO": 17
      },
      "pending_pairs": 49
    }
  }
}
```
