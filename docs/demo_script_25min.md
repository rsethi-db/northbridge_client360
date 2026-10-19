# 25-minute demo script: Northbridge Client 360

**New to broking? Read [`primer.md`](primer.md) first.** It explains how a broker makes money, the vocabulary, the story and the numbers.

This is written the way you'd actually say it. Lines in quotes are what you say; the notes in *italics* are what you do. You don't need to memorise it word for word: learn the *beats*, and say them in your own voice.

**Running order (18-slide deck):**

| Clock | What | Slides |
|---|---|---|
| 0:00 | Open and set the scene | 1 → 2 → 3 |
| 3:00 | Who wins | 4 |
| 3:45 | How it fits together | 6 *(skip 5)* |
| 4:30 | **Live demo: five moments** | 7 → app |
| 16:30 | What it's worth, and why you can trust it | 8 → 9 *(skip 10, 11)* |
| 18:30 | Trade-offs and how I built it | 12 → 13 |
| 20:30 | The pilot, what's next, the ask | 14 → 15 → 16 |
| 23:00 | Questions | 17 as backup |

---

## Before you start (10 minutes ahead)

- **App** open, and you've searched *Kestrel* once so it's warm. The header shows *Restricted segment: visible* and *Data steward*.
- **Workspace tabs, in this order:**
  1. the `nb_raw.landing` Volume
  2. the build job run
  3. the *1 Ingest* pipeline
  4. `nb_gold.dim_party` → Lineage
  5. `nb_gold` → Policies
  6. the MLflow model
  7. the Genie space
- **Backups:** `evidence/04_governance.md` and `evidence/09_steward_roundtrip.md`.
- **Deck** in Chrome: **F** for full screen, **S** for your notes. Share only the slides window.

---

## 0:00 · Open (slide 1)

> "Thanks for making the time. Before I show anything, let me tell you where we'll end up, because I think it's a number you'll care about."

*Press → to slide 2.*

## 1:00 · The outcome (slide 2)

> "On a book like Northbridge's, about four hundred and seventy-five million in fees and commission, getting a single view of your clients is worth roughly **seven million dollars a year**. That's not from new technology for its own sake. It comes from three very ordinary things: keeping clients at renewal, selling more to the clients you just acquired, and collecting commission carriers already owe you.
>
> I'll show you where each of those numbers comes from. But first, let me show you *why* it's hard today."

*Press → to slide 3.*

## 2:00 · The problem (slide 3)

> "So, three months ago you bought Harbor & Cole. Great deal. But here's what it did to your data.
>
> This is Kestrel Industries, one of your biggest clients. Today it lives in your systems **six times**. Twice in your CRM. Once in billing, spelled out in full as 'Public Limited Company'. Once in the placement platform. And twice more in Harbor & Cole's old system, in capitals, one of them abbreviated to 'KESTREL INDS'.
>
> So if I ask, 'what's our total relationship with Kestrel?', finance gives me one number, placement gives me another, and the account team gives me a third. Nobody's wrong; they just can't see each other's records.
>
> The usual fix is 'let's migrate everything into one CRM'. That's a two-year project, and you lose the value while you wait."

*Look at the sponsor:*

> "Can I ask you something before we go on? Of these, retention at renewal, cross-selling into the Harbor & Cole book, or commission leakage, which one keeps you up at night this year?"

*Listen, and remember the answer. Bring it back on the value slide.*

## 3:00 · Who wins (slide 4)

> "There are really two people this is for.
>
> For you, as CFO, it moves the two numbers you're measured on. Retention and cross-sell add about **0.7 points of organic growth**. Recovered commission is almost pure profit, so that's about **72 basis points of EBITDA margin**. And it gives you one revenue number your auditors will accept.
>
> For your head of client data, it's about workload and control: far fewer duplicates to fix by hand, and proof that sensitive clients are protected."

*Skip slide 5. Press → twice to slide 6.*

## 3:45 · How it fits together (slide 6)

> "Here's the whole thing on one page, and then I'll show it to you running.
>
> Files from your four systems land in one place. Databricks cleans them and checks their quality. A machine-learning model works out which records are really the same company, and where it's unsure, Claude explains the case to a person. Everything is governed in one catalog, with security rules that apply everywhere. The result is served to an app in milliseconds, and people can ask questions in plain English.
>
> And the bit I'm proudest of is the loop at the bottom: when a person corrects the data in the app, that correction flows back and the system *learns* it. Let's look."

*Press → to slide 7, then switch to the browser.*

---

## 4:30 · Live demo: five moments (about 2½ minutes each)

### Moment 1 · "Here's the mess, and here's it getting cleaned" (Lakeflow)

> "Let's start with the raw data, because I want you to see it's genuinely messy."

*Open the Volume `nb_raw/landing`. Click into `harbor_cole/clients/HC_CLIENT_MASTER.TXT`.*

> "This is Harbor & Cole's export: pipe-delimited, all capitals, abbreviations, and some registration numbers with digits swapped round. And here's the fun one: three carriers send their commission statements in **three different layouts**, with different columns and different date formats."

*Switch to the job run.*

> "This one job runs the whole thing end to end, from an empty catalog to the finished app, in about fourteen minutes. Nobody has to babysit it."

*Switch to the *1 Ingest* pipeline, then click `crm_accounts` → **Data quality**.*

> "As files arrive they're picked up automatically, cleaned, and checked against rules. Look: 367 CRM accounts have no registration number, so we flag that but keep them. Down here, 272 carrier lines point to a policy we've never heard of, so those get pulled out."

*Open `nb_silver.dq_quarantine`.*

> "And they're not thrown away. They land here with the rule they broke, which gives your ops team a worklist. So: new data in automatically, quality checked on every row, nothing lost silently."

### Moment 2 · "One client, one number" (account executive view)

> "Now let's be an account executive with Kestrel's renewal next week."

*Open the app → **Account executive** tab → search **Kestrel** → click **Kestrel Industries plc**.*

> "One client. And it tells me straight away: built from six records across four systems. Those are the six we just saw.
>
> Here's the family tree: the parent, the regional companies and the operating subsidiaries. See Bluewater Coatings? Completely different name. It was an acquisition that got renamed. Matching on names would never find it; we linked it through the company registry.
>
> Here's revenue, fees plus commission, never premium, rolled up across the whole family by year. This year's bar is shaded because it's year to date. Placements by line of business. And down here, exactly which source records made up this client, including what Harbor & Cole was earning that this AE has never been able to see.
>
> One more thing: look at the corner. This page loaded from Lakebase in about **twenty-five milliseconds**, the speed you'd want from an operational app."

### Moment 3 · "Ask it in plain English" (Genie)

> "Now, your CFO doesn't want to click around. They want to ask a question."

*Click **✦ Ask Genie**, then the chip "What's our total revenue with Kestrel…". It takes 10–30 seconds; keep talking while it runs.*

> "This is Genie. We taught it how a broker talks: a 'client' means the whole corporate family, 'revenue' means fees and commission, and subsidiaries roll up to the parent."

*When the answer lands, about $3.84M:*

> "There we go. And if you don't trust it, you can see exactly what it ran."

*Open **Show the SQL**.*

> "It used the official revenue definition, the same one finance uses. Let me prove that."

*Close the panel. Click **Tie out to the certified metric view**.*

> "App, Genie and finance's definition: **identical to the cent**. That's the end of three different numbers in the board pack."

*If you have time, open Genie again and ask "Which acquired Harbor & Cole clients overlap…":*

> "And that's the cross-sell list your teams can start on tomorrow."

### Moment 4 · "People make the judgement calls" (data steward view)

> "So far the machine's done the work. But some cases genuinely need a human, so let me switch hats and be a data steward."

*Click the **Data steward** tab.*

> "Out of about three thousand six hundred match decisions, the model was confident on all but **fifty-one**. That's just over one percent. Only those come to a person."

*Click a pair, ideally a MERIDIAN one.*

> "Here are both records side by side, with which fields agree and which don't, how confident the model is, and Claude's recommendation with its reasoning. Claude advises; the steward decides."

*Type "Same name and country, legacy duplicate" and click **Approve merge**.*

> "That decision is saved, with my name, the time and my reason, so it's fully auditable. Then, without anyone writing any integration code, it streams back into the lakehouse in about **thirteen seconds**."

*Click **Run entity resolution now**.*

> "This reruns the matching with my decision as a hard rule. It takes a few minutes, so here's one I ran earlier."

*Open `evidence/09_steward_roundtrip.md`.*

> "Before: two separate Meridian records. After: one client. A click in the app changed the golden record. That's the loop."

*Optional, 20 seconds, on the MLflow tab:*

> "And the model itself is versioned and governed. On test data it never merged two different companies wrongly, and it found 98% of the true duplicates."

### Moment 5 · "Governed once, enforced everywhere" (Unity Catalog)

> "Last one, and for a broker this might matter most: some of your clients are defence and government, and only certain people should ever see them."

*Search **Ironclad** in the app.*

> "I can see Ironclad, flagged restricted, because I'm in the approved group. And notice that it isn't stored in the fast app database at all. Sensitive clients never get copied out."

*Switch to `nb_gold` → **Policies**.*

> "Here's how it works. Instead of writing a security rule for every table, we tag the sensitive data once, and two policies protect every table carrying that tag. One hides restricted clients. The other masks contact names, emails and phone numbers."

*Open `evidence/04_governance.md`.*

> "To prove it, I took myself out of the group. Within a few minutes the restricted clients went from fifty-one to zero, in the app, in SQL and in Genie. Genie literally answered 'zero restricted clients'. Same rule, every tool."

*Switch to `dim_party` → **Lineage**.*

> "And for your auditors: every client traces back through each step to the original file in each of the four systems."

*Switch back to the deck and press → to slide 8.*

---

## 16:30 · What it's worth (slide 8)

> "So, what's that worth? Let me walk you through it, because I want you to be able to argue with it.
>
> First line: 75 client families are served by *both* firms, with about ninety million of revenue. If seeing the full relationship helps you keep just 2% more at renewal, that's **1.8 million**.
>
> Second line: 224 families exist only in the Harbor & Cole book, about thirty-five million. If you sell them 5% more, that's **1.7 million**.
>
> Third line: eleven million of commission that carriers short-paid or never paid. Recover 30% and that's **3.4 million**.
>
> Total: about **6.9 million a year**, or in your terms, 0.7 points of organic growth and 72 basis points of margin.
>
> Those percentages are deliberately cautious. In the pilot we replace them with your own numbers."

*Tie it to their discovery answer. If they said leakage: "and you said leakage was the big one; that's the largest line here."*

## 17:45 · Why you can trust it (slide 9)

> "And two reasons to trust it: there's one definition of revenue, enforced everywhere, and the sensitive clients are protected by policy, not by people remembering to."

*Skip slides 10 and 11. You've just shown both live. Press → three times to slide 12.*

## 18:30 · The trade-offs (slide 12), mostly for the architect

> "A few choices I made on purpose, so you don't have to ask.
>
> Restricted clients stay out of the fast database. The trade-off is that they load in about three seconds instead of milliseconds. For a handful of very sensitive clients, I think that's the right call.
>
> Security is by tag, not table by table, so a new table is protected the moment it's tagged.
>
> And the AI is only used where it adds judgement, on the uncertain one percent. That keeps it cheap and explainable."

## 19:30 · How I built it (slide 13)

> "People always ask how long this took. I built it in one working session with Claude Code and the Databricks skills. The AI wrote, tested and verified the code; I made the decisions at each checkpoint.
>
> It mattered in a few specific places. It tested the platform's limits *before* we depended on them. It checked itself against known answers, which caught a bug that was wrongly merging 830 records. And a second AI reviewed the code and found ten real defects, which we fixed. Every number you've seen today is pulled live, not typed in."

## 20:30 · The pilot (slide 14)

> "So here's how we'd do this for real, on your data, in six weeks.
>
> Weeks one and two: we connect your CRM, billing and the Harbor & Cole system. Weeks three and four: we tune the matching on your stewards' decisions and agree the revenue definition with finance. That's when your teams get their first worklists. Weeks five and six: twenty account executives using the app, and Genie in the hands of finance and placement."

## 21:30 · What's next (slide 15)

> "And beyond the pilot, three things to make the AI accountable in production. First, we score Claude's advice against what your stewards actually decide, so you can see over time whether it's earning trust. Second, we watch the model for drift and retrain it automatically when your data changes. Third, instead of one pair at a time, Claude writes up a whole corporate family for a steward to approve in one go.
>
> To be clear, those aren't built yet. But each one builds on something that's already running."

## 22:15 · The ask (slide 16)

> "So, what I'd need from you: a sponsor, a named owner for client data, read access to three systems, and two stewards for a couple of hours a week.
>
> In return, in six weeks you'll have one governed view of every client and a value case built on your own numbers. **Can we agree to start the pilot?**"

*Stop talking. Let them answer.*

## 23:00 · Questions

> "What questions do you have?"

If it's quiet, go to slide 17 and say:

> "The ones I usually get are 'we already have an MDM programme', 'what does it cost', and 'can we trust the automatic merges'. Happy to start with any of those."

**End on:**

> "One governed view of every client, about seven million a year, six weeks to prove it on your numbers. Shall we get it started?"

### If you're running late
- **Behind at 10:00:** one Genie question plus the tie-out only.
- **Behind at 15:00:** in Moment 5, show Ironclad and the toggle evidence only.
- **Behind at 20:00:** skip slides 13 and 15, and go straight to the pilot and the ask.

---

## Expected questions, with conversational answers

General tip: answer at the level they asked, then add one sentence for the other person in the room. For example: *"…and for you, [CFO], that means fewer surprises at renewal."*

### From the CFO / business side

**"What's the difference between the account executive view and the steward view?"**
> "The account executive *reads* the golden record. It's how they win renewals. The steward *writes* to it, settling the 1% of cases the model isn't sure about. Their decisions flow back automatically, so the AE always sees the corrected version."

**"What does this cost?"**
> "It runs on serverless, so you pay for what you use. The whole rebuild is about fourteen minutes of compute, and the app database switches itself off when idle. We'd size it properly on your volumes in the pilot, but it's a small fraction of even one of those value lines."

**"How quickly do we see value?"**
> "Inside six weeks. The overlap and leakage lists are usable from about week four."

**"We already have an MDM programme."**
> "Then this helps it rather than competing with it. You get a governed golden record now, and when the MDM lands, you hand it tested matching rules and clean data. You don't have to wait two years to start getting value."

**"Is the $6.9M real?"**
> "The inputs are real measurements from the data: how much overlapping revenue, how much flagged commission. The percentages are my cautious assumptions, and replacing them with your numbers is the first thing we'd do. Even the commission line alone pays for the programme."

**"What if it merges two different clients by mistake?"**
> "Three safety nets. It refuses to merge companies from different countries or with conflicting registration numbers. Anything uncertain goes to a person. And any merge can be undone with one click, with a full audit trail."

**"Will account executives actually use it?"**
> "It answers the one question they ask before every renewal, in milliseconds, and they can ask Genie in plain English. We'd measure adoption across twenty AEs in the pilot."

**"How do you protect our defence and government clients?"**
> "By policy. They're never copied into the operational database, and you saw that removing someone's access hides them everywhere within minutes, with lineage for the auditors."

**"Can finance trust Genie's numbers?"**
> "Genie uses exactly the same revenue definition as finance, and we proved it ties out to the cent. And it always shows you the query it ran."

**"Who owns this afterwards?"**
> "Your client-data owner owns the rules and the stewards. Everything's code, so your team can run and change it."

### From the architect / technical side

**"Why declarative pipelines rather than notebooks?"**
> "You describe what each table should be, and the platform handles the order, retries, incremental loading and quality reporting, all visible in the UI. Auto Loader picks up new files and copes when columns change."

**"How did you handle three carrier layouts?"**
> "Each lands as-is in its own raw table, and the cleaning step maps all three to one standard shape. I deliberately didn't use an AI agent for that: fixed mappings are cheaper and auditable for layouts you know. If carriers keep inventing new ones, an Agent Bricks extractor could slot in at the front."

**"How does the matching scale?"**
> "We never compare everything with everything. We only compare records that share something, like a registration number, a similar name in the same country, or a postcode. That gives about thirty-seven thousand pairs from four thousand records instead of millions. At much bigger scale, the scoring moves onto Spark, but the design stays the same."

**"Which model, and why not a black box?"**
> "A gradient-boosted classifier on seventeen features a person can understand: name similarity, registration number distance, address, country. It's registered in Unity Catalog through MLflow, and precision and recall are logged every run."

**"How do you stop it chaining unrelated companies together?"**
> "Rules it can't break: one country per client, no conflicting registration numbers, and a steward's 'keep separate' is respected even indirectly. Twenty-two merges were blocked by those rules in the last run."

**"What about LLM cost and hallucination?"**
> "It only sees the uncertain one percent, at most three hundred pairs a run, each cached so we never pay twice. The output is structured, not free text. And it only advises; a person decides."

**"Does data leave the platform for the LLM?"**
> "No. Claude is called through Databricks' Foundation Model API from SQL, inside the governance boundary."

**"How does the family tree get built?"**
> "From the company registry's parent references and registration numbers, joined to the matched clients. That's how a renamed subsidiary like Bluewater gets linked."

**"Why ABAC instead of row filters on each table?"**
> "Because it scales with your data, not your code. You tag a column once, and one policy covers every table with that tag."

**"Why Lakebase *and* a SQL warehouse?"**
> "Different jobs. Lakebase is for instant lookups and for saving steward decisions, like any app database. The warehouse is for analytics and for the policy-protected data, which deliberately isn't copied into Lakebase."

**"How do steward decisions get back without custom code?"**
> "Lakehouse Sync streams every change in that Postgres table into a Delta table in Unity Catalog, in about thirteen seconds. The next matching run reads the latest decision for each pair. It's in Beta, so in production I'd keep a scheduled job as a fallback."

**"Is the metric view really the single source of truth?"**
> "Yes. The app's tie-out, Genie's trusted function and finance all query the same metric view, and its definition is written into the table's description."

**"How do you keep Genie accurate?"**
> "It only sees certified gold and the metric view, never raw data. It has written instructions in broker language, trusted functions for the key questions, and five benchmark questions that we tested against known answers. All five were correct."

**"How's it deployed?"**
> "One Asset Bundle with the jobs, pipelines, app and database. One deploy and one job run rebuilds everything from an empty catalog, and there's a teardown script. I tested it from scratch."

**"What about our real systems?"**
> "Lakeflow Connect has connectors for Salesforce and SQL Server, and Auto Loader handles the carrier files. The golden record can be pushed back into your CRM too."

### Curveballs

**"What's real and what's synthetic?"**
> "Everything you saw running is real: the pipelines, model, AI calls, security policies, database sync, Genie and the app. The *data* is made up, but deliberately messy in the way broker data really is."

**"Show me where it fails."**
> "Sure." *Open `dq_quarantine`, or the steward queue.* "And the model is honest about its limits: there are fifty-one cases it won't decide alone."

**"What would you do differently?"**
> "Continuous sync rather than snapshots, the AI accountability pieces on slide 15, and retraining on steward decisions on a schedule."

**"What's in Beta?"**
> "Lakehouse Sync, the return path for steward decisions. For production I'd keep a scheduled fallback job. The rest is generally available."

**"I'm not a broker. Why should I believe the business case?"**
> "That's exactly why every assumption is on the slide in plain sight. The first thing the pilot does is replace my assumptions with your actual retention and recovery numbers."

---

## Coverage checklist: every capability from the brief, and when you show it

| Capability | Where |
|---|---|
| Synthetic broker data, 4 systems, deliberately messy | Moment 1, Moment 2 (six Kestrel records) |
| UC Volume drop zone | Moment 1 |
| Lakeflow pipeline, Auto Loader, bronze → silver → gold | Moment 1 |
| Failing expectations and quarantine | Moment 1 |
| Carrier statements in different layouts | Moment 1 |
| Lakeflow Job, rebuildable from scratch | Moment 1; "How's it deployed?" |
| Tags, certified gold, SOX, uncertified silver | Moment 5 (mention the tags on `dim_party`) |
| PII column masking | Moment 5 (Policies) |
| Restricted-client row filter, hidden from users without access | Moment 5 (Ironclad and the toggle) |
| Lineage to all four systems | Moment 5 |
| Metric view: one revenue definition | Moment 3 (tie-out) |
| Matching model, clustering, stable IDs, hierarchy | Moment 2 (result), Moment 4 (MLflow), Q&A |
| MLflow / Unity Catalog model registry | Moment 4 |
| LLM rationale for uncertain pairs | Moment 4 |
| Lakebase synced tables, low latency | Moment 2 (25 ms) |
| Steward write-back and the round trip | Moment 4 |
| Genie: instructions, trusted functions, sample questions | Moment 3 |
| App: AE view and steward view | Moments 2 and 4 |
| Genie inside the app | Moment 3 |
| Asset Bundle, teardown | Slide 6, Q&A |
| How it was built with AI | Slide 13 |
| CFO metrics (organic growth, EBITDA margin) | Slides 4 and 8 |
| Production roadmap (LLM judge, drift, action plans) | Slide 15 |
