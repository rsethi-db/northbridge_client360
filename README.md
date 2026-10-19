# Northbridge Client 360 — one governed client master for a global insurance broker

> **Business outcome.** After acquiring the Harbor & Cole agency, Northbridge Risk Partners (a global insurance broker paid in fees and commission) holds the same corporate client up to six times across four systems and cannot answer *"what is our total relationship with this client?"*. This build resolves those records into one governed golden client with its legal-entity hierarchy, serves it to account executives in milliseconds, and answers revenue questions in plain English with one certified number. **On the synthetic book ($474.5M FY2025 fee and commission income) that is worth about $6.9M a year**, from protecting 75 overlapping client relationships at renewal, cross-selling into 224 acquired-only clients, and recovering $11.3M of commission flagged on carrier statements. It also cuts steward effort to the 1.4% of match decisions that need a human.

**Deck:** [`docs/deck/northbridge_client360_deck.pdf`](docs/deck/northbridge_client360_deck.pdf) (Markdown with speaker notes: [`.md`](docs/deck/northbridge_client360_deck.md)) · **Evidence the build ran:** [`evidence/`](evidence/) (all text) · **Demo prep:** [primer](docs/primer.md), [25-min script](docs/demo_script_25min.md), [30-min roleplay prep](docs/roleplay_prep.md)

## The value case

| Lever | Measured in the build (FY2025) | Assumption | Annual value |
|---|---|---|---|
| Protect overlapping relationships at renewal | 75 client groups served by both books, $89.8M combined | +2% retention | $1.8M |
| Cross-sell Northbridge specialty lines into acquired-only clients | 224 Harbor & Cole-only groups, $34.5M | +5% wallet share | $1.7M |
| Recover commission leakage | 371 placements short-paid or missing from carrier statements, $11.3M | 30% recovered | $3.4M |
| **Revenue impact** | | | **$6.9M (≈1.5% of fee & commission income)** |
| Steward effort on duplicates | 2,405 merges automated; 51 of 3,661 match decisions need a human | 10 min per manual merge | ~400 hours per cycle |
| Compliance exposure | 51 defence & government entities ($16.4M) | | governed by policy; 0 copies in the operational store |

Measured inputs: [`evidence/10_value_inputs.md`](evidence/10_value_inputs.md). The assumptions are deliberately conservative; the pilot replaces them with Northbridge's own renewal and recovery rates.

**Who it is for.** The *executive sponsor* (Chief Client Officer / COO) is measured on organic growth, renewal retention, deal-synergy capture and one revenue number finance will sign. The *domain owner* (Head of Client Data & Governance) is measured on duplicate rate, steward throughput, provable access control and lineage.

## The story in one paragraph

**Northbridge Risk Partners**, a global insurance broker, has just acquired the regional agency **Harbor & Cole**. The same corporate client now exists as inconsistent records in four systems (Northbridge CRM, Northbridge billing and commission, the placement platform, and Harbor & Cole's legacy agency management system), so nobody can answer *"what is our total relationship with this client?"*. Brokers usually wait years for one system to win. This demo shows a different path. Lakeflow lands all four sources and enforces data quality. An ML match model, with an LLM assisting stewards on the ambiguous pairs, resolves the duplicates into one **golden party record** and a **legal-entity hierarchy**. Unity Catalog ABAC governs it once: restricted defence and government clients and contact PII are protected by tag-driven policies. The result is served to account executives through Lakebase in milliseconds and to everyone else through Genie in plain English. All of them get the same certified revenue number, to the cent. When a steward fixes a match in the app, that decision flows back through Lakebase into the lakehouse, and the golden record changes on the next run.

**Revenue is fee and commission income.** Premium (GWP) is carried on placements only as a reference attribute.

---

## The integrated journey

```
raw files (5 formats) ─▶ Lakeflow (bronze → silver, expectations, quarantine) ─▶ ML match model + Claude review assist
      ─▶ certified gold in Unity Catalog (metric view, ABAC, lineage) ─▶ Lakebase (ms serving)  ─▶ Databricks App
                                                                    └─▶ Genie (plain English)   ─┘        │
      ◀── next entity-resolution run ◀── Lakehouse Sync (CDC) ◀── Lakebase steward_decisions ◀── approve/reject/split
```

Every stage feeds the next, and the loop closes: a steward's click in the app reaches Unity Catalog in about 13 s and changes the golden record on the next run ([`evidence/09_steward_roundtrip.md`](evidence/09_steward_roundtrip.md)).

## Acceptance results (final from-scratch build, 2026-10-16)

The workspace was torn down with `scripts/teardown.sh` and rebuilt with `scripts/build.sh`. Everything below comes from that run and is committed as text in `evidence/`.

| Criterion | Result | Evidence |
|---|---|---|
| Deploy + one documented run builds everything | All 10 build-job tasks SUCCESS on serverless, exit 0 | `00_build_from_scratch.log`, `01_build_job_run.md`, `notebook_runs/*.md` (cells with outputs) |
| Bronze / silver / gold with failing expectations and quarantine | 11 expectations with failures, e.g. 272 statement lines without a policy ref, 233 transactions without a client, 100 placements expiring before inception; every dropped row in `dq_quarantine` | `02_lakeflow_data_quality.md` |
| Lineage from the golden record reaches all four systems | `dim_party` → `party_xref` → `party_source_records` → silver → bronze for all 4 systems, plus file-level provenance | `05_lineage.md` |
| Demo user without access cannot see the restricted segment | Removed from the group: parties 1,862 → 1,811, restricted 51 → 0, FY2025 revenue $474.49M → $458.05M; Genie: "0 restricted clients"; Lakebase holds 0 defence rows | `04_governance.md`, `06_lakebase.md` |
| Headline client unifies ≥5 records across all 4 systems incl. Harbor & Cole duplicates | Kestrel Industries plc = 6 records (2 CRM, billing, placement, 2 H&C, one with a transposed registration number); 8-entity hierarchy including the differently named Bluewater Coatings | `03_entity_resolution.md` |
| Entity resolution quality | Pairwise precision 100%, recall 98.2% against the labels; LLM advice checked against ground truth | `03_entity_resolution.md` |
| Five Genie questions correct; revenue ties to metric view and app to the dollar | All 5 match ground-truth SQL; Kestrel FY2025 $3,835,598.67 in Genie, the metric view and the app | `08_genie_test_results.md`, `07_app_selftest.md` |
| A steward approval changes the golden record after the next run | Approved in the app → Lakebase row → Lakehouse Sync (~13 s) → round-trip job → two duplicate records now one golden party; Lakebase refreshed | `09_steward_roundtrip.md` |
| Low-latency serving | Client family view from Lakebase ~25 ms; restricted family from gold on behalf of the user ~3 s | `07_app_selftest.md` |

## Decisions and trade-offs

| Topic | Decision | Why |
|---|---|---|
| ABAC instead of per-table row filters / masks | Two policies on `nb_gold`, matched on `rls_filter_key` (restriction flag) and `class.name` / `class.email_address` / `class.phone_number` | Govern by attribute once; new gold tables are covered by tagging. The account's tag-policy limit is reached, so existing governed keys are reused rather than new ones created. |
| Restricted clients are not synced to Lakebase | `app_*` projections exclude them; the app reads restricted clients from gold **on behalf of the user** | Lakebase rejects synced tables whose source has row filters, masks or ABAC policies ("cannot have both row/column security and online materialized views"). Restricted data never leaves the governed lakehouse. |
| Restricted = source flag **or** Defence & Government industry | Gold `party_attributes` | Found in testing: an unflagged, not-yet-linked Ironclad subsidiary reached the serving copy. The policy rule closes it. |
| Gold tables never read other gold tables | Private temporary views | Pipelines evaluate ABAC as the refreshing identity; reading a filtered gold table could persist filtered data. |
| Workspace-local groups → `is_member()` | `restricted_client_filter`, `mask_pii` | Groups created in this workspace are workspace-local; `is_account_group_member()` does not see them. |
| Cannot-link constraints in clustering | One country and no conflicting registration numbers per golden party | Without them, transitive chains through siblings sharing an office fused unrelated companies. |
| LLM endpoint `databricks-claude-sonnet-4-6` | `ai_query` with a JSON-schema response format | Claude 5.5-family endpoints are not enabled for batch `ai_query` in this workspace. |
| Lakebase notebook uses `pg8000` | Pure-Python driver | `psycopg`'s binary wheel aborts the serverless Python process. |
| Schemas prefixed `nb_` in an existing catalog | Bundle variables | No `CREATE CATALOG` on the shared metastore. |

## AI as a force multiplier: how this was built

Built in one working session with **Claude Code** (Claude Opus 5.5) in the terminal, using the Databricks plugin skills (`databricks-core`, `-pipelines`, `-dabs`, `-lakebase`, `-genie-agents`, `-metric-views`, `-apps-python`, `-app-design`) and an AI code-review agent. The human set direction at checkpoints: catalog choice, ABAC instead of per-table filters, the Lakebase serving design, UX feedback. The AI did the build, testing and evidence. Patterns that mattered:

1. **Probe before you design.** Each platform assumption was tested in the workspace before code depended on it. Several became documented constraints: no `CREATE CATALOG`, the tag-policy limit, which Claude endpoints support batch `ai_query`, Lakebase refusing policy-protected sources, and `psycopg` crashing serverless notebooks.
2. **Ground truth from the start.** The synthetic generator writes labels alongside the data, so every run measures itself. That caught a `party_id` collision bug (830 false merges → 0), transitive over-merging (fixed with cannot-link constraints), and a generator flaw where duplicate legal names in one country made the LLM look wrong.
3. **Iterate prompts against evidence, not vibes.** The first steward prompt returned "needs more info" for 91% of pairs. Version 2 encodes an experienced steward's heuristics (`src/ml/12_llm_review_assist.py`), uses a JSON-schema response format, and is scored against ground truth.
4. **Adversarial review.** An AI review pass found 10 real defects (wrong pair selected after sorting the queue, no steward authorization, a reject defeated by transitive links, an unshared Genie space, non-idempotent regenerate). All were fixed and re-verified from scratch.
5. **Evidence as a build artifact.** `scripts/collect_evidence.py` and `scripts/test_genie.py` regenerate every claim in this README from live queries, and the deck generator (`docs/deck/build_deck.py`) pulls its numbers the same way.

Conversation ID for verification: `7827e748-aa24-43a1-b76a-2107d0a95b2b`.

## Architecture (detail)

```
 UC Volume (raw drop zone)                       Lakeflow Declarative Pipelines (serverless)
 ├─ crm/            JSON      ─┐   ┌─────────────────────────────────────────────────────────────┐
 ├─ billing/        CSV        │   │ BRONZE  Auto Loader, 12 streaming tables, source columns as-is│
 ├─ placement/      Parquet    ├──▶│ SILVER  standardize + expectations (drop) + dq_quarantine     │
 ├─ harbor_cole/    pipe TXT   │   │         party_source_records = 4 systems in one schema        │
 ├─ carrier_statements/ 3 layouts  └─────────────────────────────┬───────────────────────────────┘
 └─ reference/le_registry (LEI-style)                            ▼
                                       ML / GenAI (serverless notebooks)
                                       blocking → features → GBM match model (UC registry, @champion)
                                       → constrained clustering → stable party_id → legal-entity hierarchy
                                       → review band 0.30–0.80 → ai_query(Claude) recommendation + rationale
                                                                 ▼
                                       GOLD pipeline (certified)  dim_party · party_hierarchy · fact_revenue
                                       fact_placements · client_revenue_summary · party_contacts · …
                                       + metric view client_revenue_metrics (THE revenue definition)
                                       + ABAC: row filter on rls_filter_key, masks on class.* tags
                     ┌───────────────────────────┼─────────────────────────────┐
                     ▼                           ▼                             ▼
          app_* serving projections        Genie space                 Databricks App (Dash)
          (unrestricted, PII-free)         gold + metric view           AE view + Steward view
                     │ synced tables        + trusted UC functions        │ Lakebase (SP)  │ UC + Genie
                     ▼                                                    ▼  (low latency)  ▼  (as the user)
          Lakebase Postgres  nb_serving.* ◀───────────────────────────────┘
                             steward.steward_decisions ◀── approve / reject / split
                                     │ Lakehouse Sync (CDC)
                                     ▼
          nb_app.lb_steward_decisions_history ──▶ next entity resolution run applies the overrides
```

| Capability | Where | What to show |
|---|---|---|
| **Lakeflow** | `src/pipelines/ingest`, `src/pipelines/gold`, `resources/*.yml` | Auto Loader on 5 formats; expectations dropping bad rows; `dq_quarantine`; one job builds everything |
| **Unity Catalog** | `src/setup/00_setup_catalog.py`, `src/governance/20_governance.py` | ABAC row filter + masks from tags; certified gold, uncertified silver; SOX tags; metric view; lineage to all 4 systems; app SP reads gold only |
| **ML / GenAI** | `src/ml/` | GBM pairwise model in the UC registry; constrained clustering; stable ids; hierarchy from registry + CRM links; Claude rationale for ambiguous pairs |
| **Lakebase** | `src/lakebase/30_lakebase_serving.py`, `resources/lakebase.yml` | Synced tables for the app; steward write-back table; Lakehouse Sync back to UC |
| **Genie** | `src/genie/40_genie_space.py` | Gold + metric view only; broker vocabulary; 4 trusted UC functions; example SQL; benchmarks |
| **Databricks App** | `app/`, `resources/app.yml` | AE: search, golden record, hierarchy tree, rolled-up revenue, placements, lineage, ask Genie. Steward: queue, LLM rationale, decisions, run ER |

### Unity Catalog layout (`richasethi_febar_catalog`)

The workspace user cannot create catalogs on this shared metastore, so the six schemas are prefixed `nb_`. `catalog` and `schema_prefix` are bundle variables, so the same bundle deploys to a dedicated `northbridge_demo` catalog elsewhere.

| Schema | Contents |
|---|---|
| `nb_raw` | Volume `landing` (raw drop zone) |
| `nb_bronze` | 12 Auto Loader streaming tables |
| `nb_silver` | Standardized tables, `party_source_records`, `dq_quarantine` (tagged `certified=false`) |
| `nb_ml` | candidate pairs and scores, `party_xref`, `party_hierarchy`, LLM assessments, review queue, `er_run_log`, `party_match_model` |
| `nb_gold` | Certified Client 360 tables, the metric view, the ABAC policies, trusted Genie functions |
| `nb_app` | `app_*` serving projections; `lb_steward_decisions_history` (Lakehouse Sync) |
| `nb_serving` | Lakebase synced tables (UC side) |

---

## 10-minute demo script (tell-show-tell)

**Audience:** the CIO / Head of Client Data (business) and the data platform lead (technical).

| Min | Click path | Say |
|---|---|---|
| 0:00 | Slide/whiteboard: four systems, one client | "After the Harbor & Cole deal, Kestrel Industries exists 6 times across 4 systems. Finance, placement and the AEs each give a different answer to 'what do we earn from Kestrel?'" |
| 1:00 | Catalog Explorer → `nb_raw.landing` → open `harbor_cole/clients/HC_CLIENT_MASTER.TXT` | Upper-case names, single-line addresses, a transposed registration number (`04712893` vs `04718293`). This is the real mess. |
| 2:00 | Pipelines → *Northbridge Client 360 - 1 Ingest* → graph → `revenue_transactions` → Data quality tab | Auto Loader on JSON, CSV, Parquet, pipe-delimited and three carrier layouts. Expectations drop rows with no client or non-numeric amounts; every dropped row lands in `dq_quarantine` with the rule it broke. |
| 3:00 | App → **Account executive** → search "Kestrel" → *Kestrel Industries plc* | One golden record, unified from 6 source records across all four systems (badges). Hierarchy tree: 8 legal entities including *Bluewater Coatings*, an acquired subsidiary with a different name, linked through the legal-entity registry. Revenue rolled up to the parent, fee vs commission. Served from Lakebase in ~20 ms. |
| 4:30 | Same page → **Verify vs metric view** | The app's FY2025 number equals the certified metric view to the cent. Finance, Genie and the app use one definition. |
| 5:00 | **Ask Genie** in the app, or the Genie space → "Which acquired Harbor & Cole clients overlap with existing Northbridge clients?" then "Top 10 clients by commission income this year, rolled up to parent" | Plain English, governed answers. Show the generated SQL: it uses a trusted function and the metric view, never premium. |
| 6:30 | App → **Data steward** → pick a MERGE pair | Model score 0.6–0.8, so the model asks for help. Claude's rationale: same legal name, same country, no conflicting registration, address is a former office. |
| 7:30 | **Approve merge** → **Run entity resolution now** | The decision is a row in Lakebase. Lakehouse Sync streams it into Unity Catalog within ~20 s; the round-trip job re-resolves, rebuilds gold and refreshes Lakebase. (Pre-run before the meeting: `evidence/09_steward_roundtrip.md` shows a real before/after.) |
| 8:30 | Catalog Explorer → `nb_gold.dim_party` → **Lineage** | Golden record → `party_source_records` → silver → bronze → the four source folders. Certified tag on gold; silver deliberately uncertified. |
| 9:00 | `nb_gold` → Policies tab | Two ABAC policies matched by tags, not per-table code: contact PII masked for everyone outside the PII readers group; Restricted (defence & government) clients hidden outside the restricted group. Remove the presenter from `northbridge_restricted_clients` (takes ~1 min) → Genie and gold no longer show Ironclad; the app never had it in Lakebase. |
| 9:45 | Close | "One governed client layer now, without waiting for a CRM migration to win." |

Objection handling for both personas is in [`docs/roleplay_prep.md`](docs/roleplay_prep.md).

**Technical deep-dive prompts:** blocking keys and cannot-link constraints (`src/ml/11_resolve_entities.py`); why gold tables never read gold tables (ABAC is evaluated as the pipeline owner); why restricted clients are not synced to Lakebase (see the table below).

---

## Deploy and run (from an empty catalog)

Prerequisites: a Databricks CLI profile for the workspace; serverless compute; Lakebase Autoscaling and Apps enabled.

```bash
./scripts/build.sh fevm-richasethi-febar
```

which runs:

```bash
databricks bundle deploy                         # 2 pipelines, 2 jobs, Lakebase project, Databricks App
databricks bundle run nb_client360_app           # deploy + start the app (creates its service principal)
databricks bundle run nb_client360_build         # setup → generate → ingest → train → resolve → LLM → gold
                                                 # → governance (ABAC, tags, metric view, grants) → Genie → Lakebase
```

`nb_client360_build` is idempotent. Data generation skips if data exists (`regenerate=true` forces it), and training skips if a champion model exists (`retrain=true`).

To apply steward decisions: **Data steward → Run entity resolution now** in the app, or `databricks bundle run nb_steward_roundtrip`.

Teardown: `./scripts/teardown.sh fevm-richasethi-febar [--with-groups]` removes the Genie space, synced tables, Lakehouse Sync config, bundle resources (purging the Lakebase project), the model, the ABAC policies, all seven schemas, and the MLflow experiment.

Evidence: `python scripts/collect_evidence.py fevm-richasethi-febar --with-toggle --with-roundtrip` regenerates everything in `evidence/`.

---

## What is real vs synthetic

| Real (running in the workspace) | Synthetic |
|---|---|
| Every pipeline, job, model, policy, table, synced table, Genie space and the app, deployed by the bundle on serverless | All companies, people, registration numbers, addresses, carriers and amounts. Generated deterministically by `src/setup/01_generate_source_data.py` (fixed seed). No customer data. |
| Lakeflow expectations and quarantine on genuinely dirty rows | The "mess" is injected on purpose: name variants, legal-suffix spellings, typos, stale addresses, transposed/missing registration numbers, in-system duplicates, same-name-different-company true negatives |
| GBM match model trained and registered in UC; Claude Sonnet 4.6 calls via `ai_query` | Training labels: `_labels/er_ground_truth.csv` stands in for a steward-labelled match history |
| ABAC policies, masks, tags, certification, lineage, metric view | FX rates are fixed "planning rates"; fiscal year = calendar year |
| Lakebase synced tables, steward write-back, Lakehouse Sync (Beta) CDC back to Delta | Carrier names (Albion Mutual, Harbourline Re, …) are fictional |

**Data volumes (one build):** ~2,060 legal entities in 452 corporate families, rendered as ~4,250 source party records; 34K revenue transactions; 17K placements; 4K Harbor & Cole policies; 14.5K carrier statement lines.

---

## Repository map

```
databricks.yml                 bundle + variables
resources/                     pipelines, build job, steward round-trip job, Lakebase project, app
src/setup/                     00 catalog/schemas/groups/functions · 01 synthetic data generator
src/pipelines/ingest/          bronze (Auto Loader) + silver (standardize, expectations, quarantine)
src/ml/                        er_features · 10 train · 11 resolve + hierarchy · 12 LLM review assist
src/pipelines/gold/            certified gold + app serving projections
src/governance/                20 tags, ABAC policies, column comments, metric view, grants
src/genie/                     40 trusted functions + Genie space definition
src/lakebase/                  30 synced tables, steward table, Lakehouse Sync, app grants
app/                           Dash app (backend.py: Lakebase as SP; UC + Genie on behalf of the user)
scripts/                       build.sh · teardown.sh · collect_evidence.py · test_genie.py · pg.py
docs/deck/                     business deck (PDF + Markdown with speaker notes) and its generator
docs/primer.md                 plain-English primer: broking, vocabulary, story, numbers
docs/demo_script_25min.md      conversational 25-minute demo script and expected questions
docs/roleplay_prep.md          tell-show-tell talk track and objection bank
evidence/                      text-readable execution evidence from the from-scratch build
```

