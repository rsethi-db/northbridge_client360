#!/usr/bin/env bash
# Removes every object the Northbridge Client 360 demo creates, so the next build runs from an empty catalog.
# Usage: scripts/teardown.sh [profile] [--with-groups]
# Leaves the catalog itself (shared workspace catalog) and, unless --with-groups is passed, the two demo groups.
set -uo pipefail
PROFILE="${1:-fevm-richasethi-febar}"
WITH_GROUPS="${2:-}"
CATALOG="${NB_CATALOG:-richasethi_febar_catalog}"; P="${NB_SCHEMA_PREFIX:-nb_}"; PROJECT="${NB_LAKEBASE_PROJECT:-northbridge-client360}"; GENIE_TITLE="${NB_GENIE_TITLE:-Northbridge Client 360}"   # match databricks.yml variables
DB="projects/$PROJECT/branches/production/databases/databricks-postgres"
cd "$(dirname "$0")/.."
q() { databricks experimental aitools tools query "$1" --profile "$PROFILE" >/dev/null 2>&1 && echo "  ok: $1" || echo "  skip: $1"; }

echo "1/6 Genie space"
for id in $(databricks genie list-spaces --profile "$PROFILE" -o json 2>/dev/null | jq -r --arg t "$GENIE_TITLE" '(.spaces // .)[]? | select(.title==$t) | .space_id'); do
  databricks genie trash-space "$id" --profile "$PROFILE" && echo "  trashed $id"
done

echo "2/6 Lakebase synced tables and Lakehouse Sync config"
for t in party party_source_xref client_revenue_summary placements match_review_queue; do
  databricks postgres delete-synced-table "synced_tables/$CATALOG.${P}serving.$t" --profile "$PROFILE" >/dev/null 2>&1 && echo "  deleted synced table $t"
done
databricks postgres delete-cdf-config "$DB/cdf-configs/nb_steward_decisions" --profile "$PROFILE" >/dev/null 2>&1 && echo "  deleted Lakehouse Sync config"

echo "3/6 Bundle resources (app, jobs, pipelines, Lakebase project)"
databricks bundle destroy --auto-approve --profile "$PROFILE"
APP_NAME="${NB_APP_NAME:-northbridge-client360}"
for i in $(seq 1 60); do   # app deletion is asynchronous; wait so the next deploy can reuse the name
  databricks apps get "$APP_NAME" --profile "$PROFILE" >/dev/null 2>&1 || break
  sleep 10
done

echo "4/6 Registered model, ABAC policies and schemas"
databricks registered-models delete "$CATALOG.${P}ml.party_match_model" --profile "$PROFILE" >/dev/null 2>&1 && echo "  deleted model"
for pol in nb_hide_restricted_clients nb_mask_name nb_mask_email_address nb_mask_phone_number; do
  q "DROP POLICY IF EXISTS $pol ON SCHEMA $CATALOG.${P}gold"
done
for s in serving app gold ml silver bronze raw; do q "DROP SCHEMA IF EXISTS $CATALOG.${P}$s CASCADE"; done

echo "5/6 MLflow experiment"
ME=$(databricks current-user me --profile "$PROFILE" -o json | jq -r .userName)
EXP=$(databricks experiments get-by-name "/Users/$ME/northbridge_entity_resolution" --profile "$PROFILE" -o json 2>/dev/null | jq -r '.experiment.experiment_id // empty')
[ -n "$EXP" ] && databricks experiments delete-experiment "$EXP" --profile "$PROFILE" && echo "  deleted experiment $EXP"

echo "6/6 Groups"
if [ "$WITH_GROUPS" = "--with-groups" ]; then
  for g in northbridge_restricted_clients northbridge_pii_readers northbridge_data_stewards; do
    gid=$(databricks groups list --filter "displayName eq \"$g\"" --profile "$PROFILE" -o json | jq -r '.[0].id // empty')
    [ -n "$gid" ] && databricks groups delete "$gid" --profile "$PROFILE" && echo "  deleted group $g"
  done
else
  echo "  kept (pass --with-groups to delete)"
fi
echo "teardown complete"
