#!/usr/bin/env bash
# Builds the whole Northbridge Client 360 demo from an empty catalog.
# Usage: scripts/build.sh [profile]
set -euo pipefail
PROFILE="${1:-fevm-richasethi-febar}"
cd "$(dirname "$0")/.."
mkdir -p evidence
databricks bundle validate --strict --profile "$PROFILE"
databricks bundle deploy --auto-approve --profile "$PROFILE"                 # pipelines, jobs, Lakebase project, app
databricks bundle run nb_client360_app --profile "$PROFILE"                  # deploy + start the app (creates its service principal)
databricks bundle run nb_client360_build --profile "$PROFILE" | tee evidence/build_job_run.log
