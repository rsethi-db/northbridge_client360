# Roleplay prep — Northbridge Client 360

Two personas in one room:
- **Business:** the executive sponsor, the CFO (with the Chief Client Officer). Measured on organic revenue growth and EBITDA margin; cares about cost, risk and time to value.
- **Technical:** the head of data or enterprise architect who has to live with it. They care about architecture, data quality, security and integration.

Target: **30 minutes**. Questions will come throughout, so the agenda leaves a buffer at the end.

> New to broking? Start with [`primer.md`](primer.md).
>
> Short on time? The 25-minute word-for-word version, with the AE-vs-steward explanation, expected questions and a requirement coverage checklist, is in [`demo_script_25min.md`](demo_script_25min.md).

| Time | Segment | Slides / screen | Purpose |
|---|---|---|---|
| 0:00–3:00 | **Frame** the customer, problem and outcome | 1 → 2 → 3 | Demo setup: who Northbridge is, the Kestrel problem, the $6.9M headline, one discovery question |
| 3:00–5:00 | **Who wins and what I'll show** | 4 → 5 | Name both buyers' KPIs; announce the four moments (the first "tell") |
| 5:00–6:00 | **The journey**, one breath per box | 6 | Integrated, not stitched; the technical persona's anchor |
| 6:00–18:00 | **Demo: four moments, ~3 min each** | 7 (divider) → switch to the app | Tell-show-tell each moment (section 2) |
| 18:00–21:00 | **Land the value** | 8 → 9 → 10 | Walk the value table; one number everywhere; the operational loop |
| 21:00–24:00 | **Technical depth** for the architect | 11 → 12 → 13 | Matching quality, trade-offs, how it was built with AI; switch altitude, then bridge back |
| 24:00–26:00 | **Time to value, what's next and the ask** | 14 → 15 → 16 | Six-week pilot, success criteria, explicit ask |
| 26:00–30:00 | **Q&A buffer** | 17 (backup), 18 (appendix) | Objection bank (section 4); end by restating the ask |

If you're running long, cut the technical-depth block to slides 12 and 13 only. If you're running short, use the "with extra time" column in section 2.

## Before you start (5 minutes ahead)

- [ ] Open the app (`https://northbridge-client360-7474655101081776.aws.databricksapps.com`). Search **Kestrel** once so the warehouse and Lakebase are warm.
- [ ] Open the Genie space in a second tab and ask one question to warm it up.
- [ ] Keep `evidence/04_governance.md` and `evidence/09_steward_roundtrip.md` open as backups. The ABAC toggle takes 1–5 minutes to apply, so demo it from evidence or start it early.
- [ ] Check the header pills read *Restricted segment: visible* and *Data steward*.
- [ ] Open the deck: `open docs/deck/northbridge_client360_deck.html` in Chrome. Press **F** for full screen and **S** for the speaker window.
- [ ] Share **only the slides window** (or present the PDF if screen-sharing a single window is awkward).

## Presenting the deck

- **Slides:** `docs/deck/northbridge_client360_deck.html` in Chrome. Use → / ← (or click the right or left side) to move, **F** for full screen, Home/End to jump. The URL shows the slide number (`…deck.html#8` opens the value case directly).
- **Speaker window:** press **S**. It opens a separate window with the current slide's notes, the next slide, an elapsed timer and each slide's target time against the 30-minute agenda. Arrow keys work there too. Share only the slides window, so the notes stay private.
- **Switching to the demo:** slide 7 is the cue. Switch to the app tab and keep the deck tab on slide 7. Come back and press → to land on the value case at 18:00.
- **Fallback:** `northbridge_client360_deck.pdf` has the same 18 slides in the same order, for Preview or Keynote full screen.

## 1. Demo setup (0:00–3:00, slides 1–3) — frame before you click

> "Northbridge is a global broker. You're paid in fees and commission, not premium. Three months ago you bought Harbor & Cole. Today the same client, Kestrel Industries, sits in your systems six times, in four places, and nobody can tell you what Kestrel is worth to you. Finance has one number, placement another, the account team a third.
> In the next fifteen minutes I'll show you one governed view of every client that exists **today**, without waiting for a CRM migration, and what that's worth: about **$6.9M a year** on this book. I'll show four moments, then the plan."

Then ask the sponsor: *"Of renewal retention, cross-sell into the acquired book, or commission leakage, which matters most to you this year?"* Use their answer to weight the rest of the talk.

## 2. Tell-show-tell, four moments (6:00–18:00, ~3 minutes each)

| # | Tell (one sentence) | Show (clicks) | Tell again: land it for the business | With extra time (≈1 min) |
|---|---|---|---|---|
| 1 | "First, what an account executive sees before a renewal." | App → search *Kestrel* → **Kestrel Industries plc**. Point at the headline sentence, the 6 records / 4 systems pills, the hierarchy tree (Bluewater Coatings is a renamed acquisition linked by the registry), FY revenue with FY2026 hatched as year to date, placements by line. | "One client, one number, in milliseconds. Your AE walks into the renewal knowing the whole relationship, including what Harbor & Cole earned." | Catalog Explorer → `nb_gold.dim_party` → **Lineage** back to the four source folders; open the raw `HC_CLIENT_MASTER.TXT` to show the mess. |
| 2 | "Now the question your CFO actually asks, in plain English." | **✦ Ask Genie** → chip *"What's our total revenue with Kestrel…"* → tiles ($3.84M). Then *"Which acquired Harbor & Cole clients overlap…"*. Open *Show the SQL*. Back on the page, click **Tie out to the certified metric view** → "matches to the cent". | "Same certified definition in the app, Genie and finance. No more three answers in the board pack." | Ask a follow-up in the same Genie thread ("…and which of those have placements with more than three carriers?") to show conversation memory and trusted functions. |
| 3 | "The machine does the obvious merges; people make the judgement calls." | **Data steward** tab → header strip (51 pairs, 1.4%) → pick a MERGE pair → field-by-field agreement, model 0.6–0.8, Claude's rationale → **Approve merge** → **Run entity resolution now**. | "Your stewards review 51 cases, not 3,600, with an AI second opinion, and every decision is audited. Their click flows back into the lakehouse in ~13 seconds; no ticket queue." (Show `09_steward_roundtrip.md` for the completed before/after.) | Pipelines → *1 Ingest* → `revenue_transactions` → **Data quality** tab: failed expectations and the `dq_quarantine` worklist. |
| 4 | "Finally, the guardrail for defence and government clients." | Header: *Restricted segment: visible*. Search *Ironclad* → RESTRICTED badge, served from gold as you. Then show the toggle result in `04_governance.md` (51 → 0 restricted, Genie says "0 restricted clients"). | "Tag the data once and every tool obeys: SQL, dashboards, Genie, this app. Restricted clients are never copied into the operational database." | `nb_gold` → **Policies** tab: two tag-matched ABAC policies; show `party_contacts` with emails masked for you. |

After the demo, return to the deck at slide 8: value (8–10) at 18:00, technical depth and how it was built (11–13) at 21:00, and the pilot, roadmap and ask (14–16) at 24:00.

## 3. Reading the room — switch altitude mid-answer

Pattern: **answer at the asker's level, then bridge in one sentence to the other persona.**

- *Architect asks "how does matching work?"* → "Blocking on registration number, name plus country, phonetics and postcode keeps comparisons near-linear. A gradient-boosted model scores 17 explainable features, and cannot-link rules stop transitive chains from fusing two legal entities. Pairs between 0.30 and 0.80 go to Claude for a rationale." **Bridge:** "For you, [sponsor], that means 98% of merges happen automatically and the risky ones get a human."
- *Sponsor asks "is this accurate?"* → "On a labelled sample: 100% precision and 98% recall, and every merge shows its confidence and source records." **Bridge:** "[Architect], the evaluation runs on every build and is logged to MLflow."

## 4. Objection bank

### Business stakeholder — cost, risk, time to value

| Objection | Answer (≤30 s) |
|---|---|
| "We already have an MDM / CRM consolidation programme." | "Good: this feeds it, it doesn't compete. You get a governed golden record and steward workflow now, and publish it to your MDM or CRM when that lands. It also gives that programme clean match rules and labels." |
| "What does it cost?" | "Serverless and pay per use. The whole build, from raw files to app, runs in about 14 minutes of job time, and Lakebase scales to zero. In the pilot we size it on your volumes; it's a fraction of any one value lever on slide 8." |
| "How fast do we see value?" | "Six weeks to a pilot on your data. The overlap and leakage worklists are usable in week four, because the hard part, the matching and governance pattern, is already built." |
| "What if the model merges two clients wrongly?" | "Three safeguards: cannot-link rules (one registration number and country per entity), a steward review band, and one-click split. Every merge is reversible and audited." |
| "Your $6.9M is just assumptions." | "The inputs are measured from your book (overlap revenue, flagged commission). The rates are conservative placeholders, and the pilot replaces them with your renewal and recovery history. Even the leakage lever alone covers the programme." |
| "Will the AEs actually use it?" | "It answers the one question they ask before every renewal, in milliseconds, and Genie means they don't need SQL. The pilot rolls it out to 20 AEs, measured on usage." |
| "Regulatory / client confidentiality risk?" | "Restricted clients are governed by attribute-based policy and never copied to the operational store. I can show the policy removing access in minutes, with lineage for audit." |

### Technical stakeholder — architecture, data quality, security, integration

| Objection | Answer |
|---|---|
| "Why Lakebase *and* a SQL warehouse?" | "Lakebase serves the AE's point lookups in about 25 ms and holds steward write-back. Lakebase can't sync tables protected by row filters or ABAC, so restricted clients are queried from gold on behalf of the user (~3 s). That's a deliberate data-minimisation trade-off." |
| "How do steward decisions get back without custom code?" | "Lakehouse Sync (Beta) streams the Postgres table as CDC into a Delta history table. The next entity-resolution run applies approvals as must-links and rejects as cannot-links, including transitively." |
| "Security model?" | "ABAC: two schema-level policies match tags (`rls_filter_key` on the restriction flag, `class.*` on PII). The app's service principal reads gold only. Genie and restricted reads run as the signed-in user. Steward actions require the stewards group." |
| "Data quality?" | "Expectations at silver drop bad rows and land them in `dq_quarantine` with the rule they broke. Warn-only rules track completeness, such as missing registration numbers." |
| "Integration with real sources?" | "Lakeflow Connect for Salesforce and SQL Server sources; Auto Loader for carrier statements; the golden record can be synced back to CRM. Everything deploys as one Asset Bundle." |
| "Scale to 50k client groups and millions of records?" | "Blocking keeps pair counts manageable; featurisation moves from pandas to Spark UDFs; continuous sync replaces snapshot mode. The pipeline and model design don't change." |
| "Why not Splink / Zingg / a vendor MDM?" | "Any of those can slot into the scoring step. We chose an explainable GBM plus an LLM only for the grey zone, so stewards can see why. The governance, serving and feedback loop around it is the real asset." |
| "LLM cost and hallucination?" | "Bounded: at most 300 pairs per run, cached by pair, with structured JSON output. It only advises; a steward decides. In Genie, answers come from trusted functions and the metric view, and the SQL is always visible." |
| "Model drift / retraining?" | "The model is in the UC registry with a champion alias; steward decisions become new labels; retraining is a job parameter. Quality metrics are logged on every run." |

## 5. Close (at ~26:00, before open Q&A, and again at 30:00)

> "One governed client layer now, worth around $6.9M a year on this book, and a six-week path to prove it on your numbers. What I need is a sponsor, a named domain owner, read access to three systems and two stewards for two hours a week. Can we agree on the pilot?"
