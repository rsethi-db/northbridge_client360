# 25-minute demo script: Northbridge Client 360

This is a word-for-word script: what to say, what to click and how long each part takes. It touches every capability the brief asks for; the coverage checklist at the end maps each requirement to the minute where you show it. Questions you should expect are in section 4.

---

## 1. First: what the two app views are for

The app has two tabs because two different people use the golden record for two different jobs.

### Account executive (AE) view: *consume* the golden record

**Who:** the account executive, or relationship manager, who owns a client and walks into renewal meetings.

**Their question:** *"What is our total relationship with this client, across every entity and every system, including what we inherited from Harbor & Cole?"*

**What the tab gives them:**
- **Search** by client, subsidiary, registration number or party id.
- **The golden record:** one name, plus how many source records and systems were unified into it. For Kestrel that's 6 records across 4 systems.
- **Legal-entity hierarchy** as a tree: parent → regional holding companies → operating subsidiaries. Bluewater Coatings is a renamed acquisition linked through the registry.
- **Revenue** (fee and commission, never premium) rolled up to the parent, by fiscal year.
- **Placements** by line of business and carrier.
- **"Where this record came from":** the lineage summary showing which source records from which systems made it.
- **Ask Genie:** a follow-up question in plain English.

**Where the data comes from:**
- Ordinary clients are read from the **Lakebase** serving copy, in about 25 ms.
- Restricted clients are read from **gold on behalf of the user**, so ABAC decides whether they appear at all.

**Business value:** fewer surprises at renewal, cross-sell into the acquired book, and one number that matches finance.

### Data steward view: *maintain* the golden record

**Who:** a data steward in client data operations, a small team.

**Their job:** *"The model merged 98% of records on its own. For the uncertain 1.4%, decide whether two records are the same company, and make that decision stick."*

**What the tab gives them:**
- **A review queue** of only the ambiguous pairs, with match probability between 0.30 and 0.80. Today that's 51 pairs out of 3,661 decisions.
- **For each pair:**
  - both source records side by side, with field-by-field agreement;
  - the model's probability;
  - **Claude's recommendation and rationale**;
  - a free-text rationale box for the steward.
- **Actions:** **Approve merge**, **Keep separate** (reject) and **Split record B out**. Each one writes a row to **Lakebase** (`steward.steward_decisions`) recording who decided, when and why.
- **Recent decisions** (the audit trail) and **Run entity resolution now**, which applies the decisions.
  - **Lakehouse Sync** streams the decision into Unity Catalog in about 13 seconds.
  - Entity resolution then treats approvals as must-link and rejects as cannot-link.
  - Gold rebuilds and Lakebase refreshes.
- Only members of `northbridge_data_stewards` can act. The header pill shows *Data steward*.

**Business value:** steward effort drops from about 3,600 decisions to 51. Every call is audited, and the fix lands in the lakehouse without a ticket or custom ETL.

### One-line version for the room

> "The AE view **reads** the golden record to win renewals; the steward view **writes** to it to keep it right. Lakebase sits in the middle: fast reads for the AE, transactional writes for the steward, synced both ways with the lakehouse."

---

## 2. Setup (do this 10 minutes before)

- [ ] **App** open and warm: search **Kestrel** once.
  - Header pills read *Restricted segment: visible* and *Data steward*.
  - Tabs to open: `https://northbridge-client360-7474655101081776.aws.databricksapps.com`
- [ ] **Workspace tabs, already open:**
  1. **Catalog Explorer** → `richasethi_febar_catalog.nb_raw.landing` (Volume)
  2. **Jobs** → *Northbridge Client 360 build* (latest successful run, DAG view)
  3. **Pipelines** → *1 Ingest*, graph showing bronze → silver
  4. **Catalog Explorer** → `nb_gold.dim_party` → **Lineage** tab
  5. **Catalog Explorer** → `nb_gold` schema → **Policies** tab
  6. **MLflow** → model `nb_ml.party_match_model` (champion alias)
  7. **Genie space** *Northbridge Client 360* → **Instructions** panel
- [ ] **Evidence backups:** `evidence/04_governance.md` (ABAC toggle) and `evidence/09_steward_roundtrip.md` (completed round trip).
- [ ] **Deck:** `docs/deck/northbridge_client360_deck.html` in Chrome. Press **F**, then **S** for speaker notes. Share the slides window only.

> **Note:** The deck's speaker timer targets the 30-minute plan. In this 25-minute version, follow the clock below and skip the slides marked *skip*.

---

## 3. The script

**Timing:** 25:00 total, with a built-in 1:30 buffer for interruptions.

| Clock | Block | Slides / screen |
|---|---|---|
| 0:00–2:30 | Frame | Deck 1 → 2 → 3 |
| 2:30–3:30 | Journey | Deck 6 (skip 4, 5) |
| 3:30–17:30 | **Live demo, five moments** | Deck 7 → workspace and app |
| 17:30–20:30 | Value and trust | Deck 8 → 9 → 10 |
| 20:30–22:00 | Trade-offs | Deck 12 (skip 11 unless asked) |
| 22:00–23:30 | Pilot and ask | Deck 13 → 14 |
| 23:30–25:00 | Buffer / first question / close | Deck 15 |

### 0:00–2:30 · Frame (slides 1–3)

**Slide 1:**
> "Thanks for the time. I'm going to show you how Northbridge gets one governed view of every client *now*, without waiting for a CRM migration."

**Slide 2 (outcome):**
> "Here's the punchline first: about **$6.9 million a year** on a $474 million book. That comes from three things: protecting overlapping relationships at renewal, cross-selling into the Harbor & Cole book, and recovering commission that carriers short-paid. I'll show you where every number comes from."

**Slide 3 (problem):**
> "Three months ago you bought Harbor & Cole. Today Kestrel Industries, one of your biggest clients, exists **six times in four systems**: your CRM twice, billing, the placement platform, and twice in Harbor & Cole's legacy AMS. Finance, placement and the account team each have a different number for what Kestrel is worth."

**Discovery question to the sponsor:**
> "Of renewal retention, cross-sell into the acquired book, or commission leakage, which matters most to you this year?"

Note the answer and weight the value section toward it.

### 2:30–3:30 · Journey (slide 6)

> "One platform, one flow. Raw files from four systems land in a governed volume. Lakeflow cleans them. A match model plus Claude resolves them into golden records. Unity Catalog governs it all. Lakebase serves it to the app. Genie answers questions on the same certified numbers. **One bundle deploys all of it.** Let me show you it running."

Press → to **slide 7** and switch to the browser.

### 3:30–17:30 · Live demo: five moments, about 2:45 each

Each moment follows **tell → show → tell again**.

#### Moment 1 (3:30–6:00): the data lands and gets cleaned (Lakeflow)

**Tell:**
> "First, how the mess gets in and gets cleaned, with no hand-built ETL."

**Show:**
1. **Volume** `nb_raw/landing`: open folders `crm/`, `billing/`, `placement/`, `harbor_cole/`, `carrier_statements/`. Click `HC_CLIENT_MASTER.TXT`.
   > "This is the acquired agency's system: pipe-delimited, uppercase, abbreviations, transposed registration digits. And carrier statements come in **three different column layouts**."
2. **Jobs** → build run DAG.
   > "One Lakeflow Job runs everything end to end, from scratch, in about 14 minutes on serverless: generate, ingest, train, resolve, LLM review, gold, governance, Genie and Lakebase."
3. **Pipeline** *1 Ingest* → graph:
   > "Auto Loader picks up new files into bronze. Silver standardises names, countries and currencies, and normalises the three carrier layouts into one schema."
4. Click `crm_accounts` → **Data quality** tab:
   > "Expectations run on every row. 367 CRM accounts are missing a registration number, which warns but keeps the row. 272 carrier lines reference a policy we don't have; those get dropped."
5. Open `nb_silver.dq_quarantine`:
   > "Dropped rows aren't lost. They land here with the rule they broke: a worklist for data ops."

**Tell again:**
> "Every new file is picked up automatically, quality is measured on every row, and bad data is quarantined, not silently lost."

#### Moment 2 (6:00–8:45): one client, one number (AE view, Lakebase, ML)

**Tell:**
> "Now what your account executive sees before a renewal."

**Show:** the app → **Account executive** tab → search *Kestrel* → **Kestrel Industries plc**.
1. Headline sentence and pills:
   > "Six source records, four systems, unified into one golden client."
2. **Hierarchy tree:**
   > "Parent, regional holdcos, operating subsidiaries. Bluewater Coatings has a completely different name, a renamed acquisition. The model linked it from the legal-entity registry, not from the name."
3. **Revenue chart:**
   > "Fee and commission income, never premium, rolled up to the parent. FY2026 is hatched because it's year to date."
4. **Placements by line**, then **"Where this record came from":**
   > "Every source record, its system, how it was matched and the confidence. The AE can see Harbor & Cole revenue they've never had visibility into."
5. Point at the provenance footnote:
   > "This page came from **Lakebase**, our managed Postgres, in about 25 milliseconds. That's app-grade latency on lakehouse data."

**Tell again:**
> "One client, one number, in milliseconds, including what you inherited with Harbor & Cole."

#### Moment 3 (8:45–11:30): ask in plain English, same number (Genie, metric view)

**Tell:**
> "Now the question your CFO actually asks, in plain English."

**Show:**
1. **✦ Ask Genie** → chip *"What's our total revenue with Kestrel…"* Wait 10–30 s; the answer is **$3.84M**.
2. Expand **Show the SQL**:
   > "No black box. It used a trusted function over the certified **metric view**: one definition of Total Client Revenue."
3. Ask the follow-up chip *"Which acquired Harbor & Cole clients overlap…"*:
   > "Same conversation; it remembers context."
4. Close the panel and click **Tie out to the certified metric view**:
   > "App, Genie and the metric view **match to the cent**."
5. *(optional, 20 s)* Genie space tab → **Instructions**:
   > "We taught it broker vocabulary: a client is a corporate family, revenue means fee plus commission, and subsidiaries roll up to the parent by default. It's tested against five benchmark questions."

**Tell again:**
> "Same certified definition in the app, Genie and finance. No more three answers in the board pack."

#### Moment 4 (11:30–14:30): people make the judgement calls (steward view, LLM, Lakebase write-back)

**Tell:**
> "The machine does the obvious merges; people make the judgement calls."

**Show:** **Data steward** tab.
1. Header strip:
   > "Out of about 3,600 match decisions, the model was confident on all but **51**, which is 1.4%. Only those reach a human."
2. Pick a MERGE pair (a MERIDIAN pair works well):
   > "Both records side by side, which fields agree, the model's probability, and **Claude's recommendation with its reasoning**. Claude advises; the steward decides."
3. Type a short rationale and click **Approve merge**:
   > "That decision just went into **Lakebase** as a transaction: who, when, why. That's the audit trail."
4. Point at **Recent steward decisions**, then click **Run entity resolution now**:
   > "**Lakehouse Sync** streams that Postgres row into Unity Catalog in about 13 seconds. Entity resolution treats it as a hard rule, rebuilds gold and refreshes Lakebase. No ticket, no custom pipeline."
5. Switch to `evidence/09_steward_roundtrip.md` (the run takes a few minutes):
   > "Here's that exact loop completed earlier: two MERIDIAN records became one golden party."
6. *(optional, 20 s)* MLflow model tab:
   > "The match model is a gradient-boosted classifier, registered in Unity Catalog with a champion alias. On labelled data it scores 100% precision and 98% recall. Steward decisions become new training labels."

**Tell again:**
> "Your stewards review 51 cases, not 3,600, with an AI second opinion, and every decision is audited and flows back automatically."

#### Moment 5 (14:30–17:30): governed once, enforced everywhere (Unity Catalog)

**Tell:**
> "Finally, the guardrails, because this is client data, some of it defence and government."

**Show:**
1. App: search *Ironclad* → **RESTRICTED** badge:
   > "I'm in the restricted-clients group, so I see it. It's read from gold *as me*, never from the operational copy. Restricted clients are never copied to Lakebase."
2. **`nb_gold` → Policies** tab:
   > "Two **attribute-based** policies, not per-table rules. Any column tagged with the restriction flag is row-filtered. Any column classified as name, email or phone is masked unless you're a PII reader. Tag a new table and it's protected automatically."
3. Open `party_contacts` sample data:
   > "Emails are masked for me, because I'm not a PII reader."
4. `evidence/04_governance.md`:
   > "I removed myself from the group. Within minutes the app went from 1,862 clients to 1,811, restricted clients from 51 to 0, and Genie answered '0 restricted clients'. Same policy, every tool."
5. **Table tags** (`dim_party` → Details):
   > "Gold is tagged *certified*, revenue tables are tagged *SOX-relevant*, and silver is deliberately uncertified, so the badge means something. Comments on every column feed Genie and search."
6. **`dim_party` → Lineage** graph:
   > "The golden record traces back to **all four source systems**, down to the file. And Genie's answer traces to gold."

**Tell again:**
> "Tag the data once and every tool obeys it: SQL, Genie, the app. Lineage gives audit the full chain."

Switch back to the deck and press → to **slide 8**.

### 17:30–20:30 · Value and trust (slides 8–10)

**Slide 8 (value):**
> "So what's it worth? Here are three levers, each from measured inputs:
> - **75** client families exist in both books, with **$89.8M** of revenue at renewal risk. Protecting 2% is **$1.8M**.
> - **224** acquired-only clients with **$34.5M**. Cross-selling 5% is **$1.7M**.
> - **371** placements short-paid or missing on carrier statements, **$11.3M** flagged. Recovering 30% is **$3.4M**.
>
> That's about **$6.9M a year**, 1.5% of revenue. The rates are conservative placeholders; the pilot replaces them with your history."

Weight this toward the lever the sponsor picked in the discovery question.

**Slide 9 (trust):**
> "Accurate: 100% precision and 98% recall. Governed: ABAC and lineage. Explainable: every merge shows its evidence."

**Slide 10 (operational loop):**
> "And it stays right: steward to Lakebase to lakehouse to golden record, in minutes."

### 20:30–22:00 · Trade-offs (slide 12), aimed at the architect

> "Three choices I made deliberately:
> - **Restricted clients aren't synced to Lakebase.** Lakebase can't sync policy-protected tables, and I'd rather not copy them anyway. Those few clients are read from gold as the user, in about 3 s instead of 25 ms.
> - **ABAC over per-table filters,** so new tables are protected by tagging.
> - **An explainable model plus an LLM only for the grey zone,** so cost stays bounded and stewards can see *why*."

**Bridge to the sponsor:**
> "For you, that means the sensitive clients stay in the most governed place."

### 22:00–23:30 · Pilot and ask (slides 13–14)

**Slide 13:**
> "Six weeks on your data. Weeks 1–2: connect three systems with Lakeflow Connect. Weeks 3–4: matching and governance on your book, with overlap and leakage worklists usable in week four. Weeks 5–6: twenty AEs on the app, measured on usage and recovered commission."

**Slide 14:**
> "What I need: a sponsor, a named domain owner, read access to three systems and two stewards for two hours a week. Can we agree on the pilot?"

### 23:30–25:00 · Buffer and close

Take the first question (section 4). If there are none, go to slide 15 and say:
> "The questions I usually get are on cost, MDM and accuracy. Happy to start with any of those."

**Final line:**
> "One governed client layer now, about $6.9M a year, six weeks to prove it. Can we agree on the pilot?"

### If you're running late

- **Behind at 10:00:** shorten Moment 3 to one Genie question plus the tie-out.
- **Behind at 15:00:** in Moment 5, show only Ironclad, the Policies tab and the toggle evidence.
- **Behind at 20:00:** skip slide 12 and go straight to slide 13.

---

## 4. Expected questions and answers

Answer at the asker's level, then **bridge** in one sentence to the other persona.

### Business sponsor (COO / Chief Client Officer)

| Question | Answer |
|---|---|
| What's the AE view vs the steward view? | "The AE **reads** the golden record to win renewals: one client, one number, in milliseconds. The steward **writes** to it, deciding the 1.4% of matches the model isn't sure about. Their decisions flow back automatically." |
| What does this cost? | "Serverless, pay per use. The full rebuild is about 14 minutes of job time, and Lakebase scales to zero when idle. We size it on your volumes in the pilot; it's a fraction of any single value lever." |
| How fast do we see value? | "Six weeks to a pilot on your data. The overlap and leakage worklists are usable from week four." |
| We already have an MDM / CRM consolidation programme. | "This feeds it rather than competing with it. You get a governed golden record now and publish it to the MDM or CRM when that lands. It also hands that programme tested match rules and labels." |
| Is the $6.9M real? | "The inputs are measured: overlap revenue, acquired-only revenue, flagged commission. The rates are conservative placeholders. Even the leakage lever alone covers the programme." |
| What if it merges two clients wrongly? | "Cannot-link rules stop it merging different countries or registration numbers. Uncertain pairs go to a steward. Any merge can be split in one click, and every decision is audited." |
| Will AEs adopt it? | "It answers the one question they ask before every renewal, in milliseconds, and Genie means no SQL. The pilot measures usage across 20 AEs." |
| Confidentiality: defence and government clients? | "Policy-based. Restricted clients are never copied to the operational database. Removing someone from the group hides them across the app, SQL and Genie within minutes, with lineage for audit." |
| Can finance trust Genie's numbers? | "Genie uses the same certified metric view as finance, and it ties out to the cent. The SQL is always visible." |
| Who owns this after the pilot? | "A data domain owner on your side owns the rules and stewards. Everything is code in one bundle, so your team can run and change it." |

### Architect / head of data

| Question | Answer |
|---|---|
| **Lakeflow:** why declarative pipelines, not notebooks? | "Declarative: dependencies, retries, incremental processing and data quality come for free and show up in the UI. Auto Loader handles new files and schema drift." |
| **Lakeflow:** how do you handle the three carrier layouts? | "Each layout lands in its own bronze table. Silver maps each to one schema and unions them, with a layout tag kept for traceability. I deliberately didn't build the optional statement-normalisation agent; deterministic mappings are cheaper and auditable for known layouts. If carriers keep adding layouts, an Agent Bricks extractor slots in at bronze." |
| **Lakeflow:** what happens to bad rows? | "`expect_all_or_drop` at silver. A quarantine view keeps the dropped rows and names the rule each one broke. Warn-only rules track completeness, like missing registration numbers." |
| **ML:** how does matching scale? | "Blocking on registration number, name plus country, phonetic key and postcode gives about 37K candidate pairs from 4.3K records. That's near-linear, not n². At larger scale, featurisation moves to Spark UDFs; the design doesn't change." |
| **ML:** which model, and why? | "A gradient-boosted classifier on 17 explainable features (name similarity variants, registration distance, address, country). It's registered in Unity Catalog with MLflow under a champion alias, and precision and recall are logged every run." |
| **ML:** how do you stop over-merging? | "Union-find clustering with cannot-link constraints: one country per party, no conflicting registration numbers, and steward rejects applied transitively. 22 merges were blocked in the last run." |
| **ML:** are party IDs stable? | "Yes. Clusters inherit the previous run's ID, and new IDs are salted so they never collide. The last run reassigned 0 records." |
| **GenAI:** LLM cost and hallucination? | "Bounded: only pairs in the 0.30–0.80 band, at most 300 per run, cached per pair, with JSON-schema output. It only advises; a human decides." |
| **GenAI:** which model? | "Claude Sonnet via the Databricks Foundation Model API, called from SQL with `ai_query`. No data leaves the platform's governance boundary." |
| **Hierarchy:** how is it derived? | "From the legal-entity registry's parent references and registration numbers, joined to the resolved parties. That's how a renamed subsidiary links up." |
| **UC:** why ABAC? | "Two policies at schema level match tags, not tables. New gold tables are protected by tagging. Row filter on the restriction flag; masks on columns classified as name, email or phone." |
| **UC:** service principal grants? | "The app's SP has read on gold and the serving projections only. Genie and restricted reads run on behalf of the user, so policies apply to the person." |
| **UC:** is the metric view really the single source? | "Yes. The app tie-out, Genie's trusted function and finance all query `client_revenue_metrics`. The definition is in the table comment and YAML." |
| **Lakebase:** why Lakebase *and* a warehouse? | "Lakebase handles point lookups in about 25 ms and transactional steward writes. The warehouse handles analytics and policy-protected reads. Lakebase can't sync policy-protected tables, so restricted clients stay in gold." |
| **Lakebase:** how does write-back work? | "The steward row goes into a Postgres table. Lakehouse Sync (Beta) streams changes as CDC into a Delta history table in about 13 seconds. Entity resolution reads the latest decision per pair. No custom code." |
| **Lakebase:** sync mode? | "Snapshot sync after each gold build. Triggered or continuous sync with CDF is the production option." |
| **Genie:** how do you keep answers correct? | "Curated to gold and the metric view only, never bronze or silver. Instructions carry broker vocabulary. Trusted functions back the key questions, and there are five benchmark questions, all tested correct." |
| **Genie:** does it respect security? | "It runs as the user. With my access removed, it answered '0 restricted clients'." |
| **App:** why Dash? Can it be React? | "Dash was the most robust for a Python-native team. The backend is separable, so a React/AppKit front end can reuse it." |
| **DevOps:** how is it deployed? | "One Asset Bundle with jobs, pipelines, app and the Lakebase project. `bundle deploy` plus one job run rebuilds from an empty catalog. There's a teardown script, and it was tested from scratch." |
| **Integration:** what about real sources? | "Lakeflow Connect for Salesforce and SQL Server, Auto Loader for carrier files. The golden record can be pushed back to the CRM via reverse ETL." |
| What's real vs synthetic? | "The platform, model, LLM calls, policies and sync are all real and running. The data is synthetic but broker-realistic: name variants, duplicates, missing registrations and true negatives." |

### Curveballs

| Question | Answer |
|---|---|
| "Show me it fail." | Open the `dq_quarantine` table or a reject-pair decision. Or: "The model is honest about its limits: 51 pairs it won't decide alone." |
| "What would you do differently?" | "Continuous Lakebase sync, a carrier-statement extraction agent for new layouts, and active learning from steward decisions on a schedule." |
| "What's in Beta?" | "Lakehouse Sync is Beta, so for production I'd also keep a scheduled job fallback. Everything else is GA." |
| "Where did AI help you build it?" | "Claude Code wrote and tested most of the code. I owned the design decisions and verification; it's documented in the README." |

---

## 5. Coverage checklist: every requirement and when you show it

| Requirement from the brief | Where in the script |
|---|---|
| Synthetic broker data, 4 systems, mess injected | M1 (Volume, `HC_CLIENT_MASTER.TXT`), M2 (6 Kestrel variants) |
| UC Volume raw drop zone | M1 |
| Lakeflow pipeline, Auto Loader, bronze → silver → gold | M1 |
| Failing expectations and quarantine | M1 (Data quality tab, `dq_quarantine`) |
| Carrier statements in inconsistent layouts, normalised | M1 (three layouts → one schema) |
| Lakeflow Job, re-runnable from scratch | M1 (job DAG), Q&A (bundle) |
| Tags: pii / confidentiality / sox_relevant / certified; uncertified silver | M5 (table tags) |
| Column masking on PII | M5 (`party_contacts`, Policies tab) |
| Row filter on restricted segment | M5 (Ironclad, toggle evidence) |
| Lineage to all 4 systems; Genie → gold | M5 (Lineage graph) |
| Metric view for total client revenue | M3 (SQL, tie-out) |
| Table and column comments | M3 (Genie instructions), M5 |
| SP / Genie grants on gold only | Trade-offs, Q&A |
| Blocking, pairwise model, clustering, stable party_id | M2 (the result), Q&A ML |
| Legal-entity hierarchy | M2 (tree, Bluewater) |
| MLflow / UC model registry | M4 (MLflow tab) |
| LLM rationale for ambiguous pairs | M4 (Claude rationale) |
| Lakebase synced tables, low latency | M2 (25 ms footnote) |
| Steward write-back tables in Lakebase | M4 (Approve → Recent decisions) |
| Round trip back to the lakehouse | M4 (Lakehouse Sync, `09_steward_roundtrip.md`) |
| Genie space over gold and metric view only | M3 |
| Instructions, sample questions, trusted assets | M3 (Instructions, chips, Show the SQL) |
| 5 sample questions correct | M3 (two live), Q&A (benchmarks; `evidence/08_genie_test_results.md`) |
| App: AE view (search, golden record, tree, revenue, placements, lineage) | M2 |
| App: steward view (queue, score, LLM rationale, approve/reject/split → Lakebase) | M4 |
| Genie embedded in the app | M3 (✦ Ask Genie panel) |
| Restricted segment hidden for user without access (app and Genie) | M5 (toggle evidence) |
| Asset Bundle, teardown | Journey slide, Q&A |
| Revenue = fee + commission, never premium | M2 |
