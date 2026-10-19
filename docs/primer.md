# Primer: the business behind Northbridge Client 360

Read this before the demo script. It explains the world this demo lives in, in plain English, so you can tell the story in your own words and handle questions you didn't rehearse. It takes about 15 minutes to read.

---

## 1. The insurance value chain in one picture

```
  The client (the "insured")        The broker                     The insurer ("carrier")       The reinsurer
  A company that needs cover   →    Finds and negotiates the  →    Takes the risk, collects  →   Insures the insurer
  e.g. Kestrel Industries           cover, services the client     premium, pays claims          (not in this demo)
                                    e.g. Northbridge (us)          e.g. a Lloyd's syndicate
```

- **The client (insured)** is a business that needs insurance: property, liability, cyber, marine, directors' liability and so on. Big multinationals buy dozens of policies across many countries.
- **The broker** works *for the client*. It understands the client's risks, goes to the market, gets quotes from several insurers, negotiates, places the cover, and helps with claims. Marsh, Aon, WTW and Gallagher are the big real-world names. **Northbridge Risk Partners is our fictional one.**
- **The carrier (insurer)** takes the risk. It receives the premium and pays claims.
- **The reinsurer** insures the insurers. It isn't part of this story.

**Key point:** a broker **does not take risk** and **does not keep the premium**. It earns a slice.

---

## 2. How a broker makes money

| Income | What it is | Example |
|---|---|---|
| **Commission** | A percentage of the premium, paid to the broker *by the carrier* | Kestrel pays a carrier $1M premium; the carrier pays Northbridge 12%, which is $120K |
| **Fees** | Charged *to the client* directly for advice or services | A $50K annual fee for risk consulting |

So **broker revenue = fee + commission income.** That's why the demo keeps saying "revenue is fee and commission, never premium." Treating premium as the broker's revenue is the classic mistake, and it would make every number about ten times too large. Premium appears in the data only as a reference attribute, labelled **GWP (gross written premium)**.

**Why commission is messy:** carriers pay commission in bulk and send a **commission statement**, a file listing what they paid for which policy. Every carrier formats it differently. The broker has to **reconcile** each statement: match every line to the policy and client it booked, and chase anything short-paid or missing. If you can't tell which client a line belongs to, money leaks. In the demo that's **$11.3M of flagged commission on 371 placements**.

---

## 3. Vocabulary you'll hear (and should use)

| Term | Plain meaning |
|---|---|
| **Placement** | One piece of insurance the broker arranged for a client with a carrier, i.e. "we placed Kestrel's property cover with Carrier X". It's the broker's unit of work. |
| **Line of business (LOB)** | The type of cover: property, casualty / liability, marine, cyber, D&O (directors & officers), etc. |
| **Inception / expiry** | When the policy starts and ends. Most are annual, so every placement comes up for **renewal** each year. |
| **Renewal** | The moment the client decides whether to stay with the broker. It's the broker's biggest commercial risk. |
| **Broker of record** | The broker officially acting for the client on that policy. |
| **Retention** | Keeping clients at renewal. A retention rate of 95% means 5% of clients (or revenue) walked. |
| **Wallet share** | How much of a client's total insurance spend goes through *us*. Cross-selling raises it. |
| **Cross-sell** | Selling a client a line they don't buy from us yet, e.g. adding cyber to a client who only buys property from us. |
| **Account executive (AE)** | The relationship manager who owns the client and runs renewals. One of the two app users. |
| **CRM** | Customer relationship management system (e.g. Salesforce), where AEs track clients and opportunities. |
| **AMS** | Agency management system: the core system of a smaller broker or agency (policies, clients, billing). Harbor & Cole's is old. |
| **Legal entity** | A specific registered company, e.g. "Kestrel Industries GmbH" in Germany. |
| **Ultimate parent** | The top company in a corporate family. Big clients are a *tree*: parent → regional holdings → operating subsidiaries. |
| **Registration number / LEI** | The official company ID in a country's registry; the LEI is a global ID. It's the strongest clue that two records are the same company. |
| **Restricted client** | A client so sensitive (defence, government) that only an approved group may see it. |

### Data terms

| Term | Plain meaning |
|---|---|
| **Golden record** | The single, trusted version of a client, built by combining all the messy copies. |
| **Entity resolution (ER) / matching** | Working out which records across systems are the same real-world company, then merging them. |
| **MDM (master data management)** | The discipline, or the product, that maintains golden records. Many firms run long, expensive MDM or CRM consolidation programmes. |
| **Data steward** | A person in data operations who decides the tricky matches and keeps master data correct. The second app user. |
| **Lineage** | The trail showing where a number came from, back to the source file. |

### Finance terms (for the CFO)

| Term | Plain meaning |
|---|---|
| **Organic revenue growth** | Growth from the existing business, *excluding* acquisitions. It's the number analysts watch for brokers, and the one a broker CFO is judged on. Retention and cross-sell drive it. |
| **EBITDA margin** | Profit before interest, tax, depreciation and amortisation, as a % of revenue. Recovered commission is almost pure margin, because the work was already done. |
| **bps (basis points)** | Hundredths of a percent. 72 bps = 0.72%. |
| **Synergies** | The extra value promised when the acquisition was approved. The board tracks whether it shows up. |
| **SOX** | US financial-controls regulation. Revenue numbers must be controlled and auditable; that's why the revenue tables are tagged `sox_relevant`. |

---

## 4. The story: who, what happened, and why it hurts

**Northbridge Risk Partners** is a global broker with thousands of multinational corporate clients and $474.5M a year of fee and commission income (all synthetic).

**Three months ago it acquired Harbor & Cole**, a regional agency. This is very common: big brokers grow by buying smaller agencies, often dozens a year. Every acquisition brings a new client list in a new system.

**The problem: the same client now exists many times, in four systems that don't talk to each other.**

| System | Owner | What it knows about a client |
|---|---|---|
| Northbridge **CRM** | Account teams | The relationship and contacts |
| Northbridge **billing & commission** | Finance | Fees and commission booked |
| **Placement platform** | Placement / broking teams | The policies placed with carriers |
| **Harbor & Cole AMS** | The acquired agency | Its own clients, policies and revenue, in a legacy format |

**The headline example: Kestrel Industries plc.** It appears **6 times across those 4 systems**:
- "Kestrel Industries plc" and "Kestrel Industries PLC" (two CRM records)
- "Kestrel Industries Public Limited Company" (billing)
- "Kestrel Industries plc" (placement)
- "KESTREL INDUSTRIES PLC" and "KESTREL INDS PLC" (Harbor & Cole, uppercase and abbreviated)

Its subsidiaries have different names in different countries. One, **Bluewater Coatings**, has a completely different name because it was a renamed acquisition. Only the company registry links it to Kestrel.

**So nobody can answer: "What is our total relationship with Kestrel?"** Finance has one number, the placement team another, the AE a third.

**Why it hurts (the four business pains):**
1. **Renewal risk.** 75 client families are served by *both* Northbridge and Harbor & Cole ($89.8M of revenue). Two teams may pitch the same client without knowing it, or an AE renews without knowing the client's full value, and the client walks.
2. **Missed cross-sell.** 224 clients exist *only* in the Harbor & Cole book ($34.5M). Northbridge's specialists can't sell to clients they can't see.
3. **Commission leakage.** $11.3M of commission on carrier statements can't be cleanly matched to the client billed, so short payments go unchased.
4. **Compliance risk.** Defence and government clients must stay restricted. When clients are copied into every system and spreadsheet, nobody can prove who sees them.

**The usual answer, and why it's too slow:** "Migrate everything into one CRM or MDM." That's an 18–24-month programme, and the value is lost while you wait.

**Our answer:** leave the four systems where they are. Build **one governed client layer on top of them**, now. It matches the records automatically, lets people decide only the hard cases, serves the result to the business, and protects the sensitive clients.

---

## 5. The two app users: what each one does

### The account executive (reads the golden record)
Think: the person walking into Kestrel's renewal meeting next week.
- Searches "Kestrel" and sees **one** client, with a note like "unified from 6 records in 4 systems".
- Sees the **family tree** (parent and subsidiaries, including Bluewater).
- Sees **total revenue** (fee + commission) rolled up to the parent, by year, and the **placements** by line and carrier.
- Sees **where the record came from**: each source record and system.
- Can **ask Genie** a question in plain English, e.g. "what's our total revenue with Kestrel?"
- Why it matters: they go into renewal knowing the whole relationship, including what Harbor & Cole earned.

### The data steward (keeps the golden record right)
Think: a small data-operations team.
- The matching model is confident on almost everything. Only **51 of 3,661** decisions (1.4%) are uncertain, and only those reach the steward.
- For each uncertain pair the steward sees both records side by side, which fields agree, the model's confidence, and **Claude's recommendation with its reasoning**.
- They click **Approve merge**, **Keep separate** or **Split**. The decision is saved with who, when and why (the audit trail).
- That decision **flows back automatically**: the next matching run obeys it, and the golden record changes.
- Why it matters: 51 reviews instead of about 3,600, each with an AI second opinion, and no tickets.

**One line:** *the AE reads the golden record to win renewals; the steward writes to it to keep it right.*

---

## 6. What each Databricks piece does, in plain English

| Piece | Its job in this story | Analogy |
|---|---|---|
| **Unity Catalog Volume** | The drop zone where raw files from the four systems land | The inbox |
| **Lakeflow Declarative Pipelines + Auto Loader** | Pick up new files automatically, clean and standardise them, and check quality rules | The sorting room |
| **Data-quality expectations + quarantine** | Rules like "every account needs a valid country". Bad rows are set aside with the reason, not lost | Quality control with a rejects bin |
| **Lakeflow Job** | Runs the whole chain in order, end to end, in about 14 minutes | The conductor |
| **ML match model + MLflow / model registry** | Scores how likely two records are the same company; versioned and governed | The detective |
| **Claude via Foundation Model API (`ai_query`)** | Writes a plain-English recommendation for the uncertain pairs only | The expert second opinion |
| **Unity Catalog governance** | Tags, certification, lineage, and **ABAC** policies that hide restricted clients and mask contact details for everyone not allowed | The security desk and the audit trail |
| **Metric view** | One official definition of "total client revenue" that everything uses | The single source of truth for the number |
| **Lakebase** (managed Postgres) | Serves the golden record to the app in about 25 ms, and stores steward decisions | The fast front counter |
| **Lakehouse Sync** | Streams steward decisions from Lakebase back into the lakehouse in about 13 seconds | The return conveyor |
| **Genie** | Answers business questions in plain English, using the official definitions | The analyst on call |
| **Databricks App** | The screen the AE and steward use | The shop window |
| **Asset Bundle** | Deploys all of the above as code, rebuildable from scratch | The blueprint |

**ABAC** (attribute-based access control), in one sentence: *instead of writing a security rule for every table, you tag the sensitive columns once, and one policy protects every table with that tag.*

---

## 7. The numbers cheat sheet

| Number | What it means |
|---|---|
| **$474.5M** | Northbridge's FY2025 fee + commission income (synthetic) |
| **$6.9M a year** | Total value: about 1.5% of revenue |
| $1.8M | Protect renewals: 2% better retention on $89.8M of overlapping clients (75 families) |
| $1.7M | Cross-sell: 5% more wallet share on $34.5M of Harbor & Cole-only clients (224 families) |
| $3.4M | Recover 30% of the $11.3M flagged commission (371 placements) |
| **+0.7 pts / +72 bps** | The CFO's view: +0.7 points of organic growth, +72 bps of EBITDA margin |
| 6 records / 4 systems | Kestrel, before the golden record |
| $3,835,598.67 | Kestrel's FY2025 revenue: the same in the app, Genie and the metric view |
| 100% / 98.2% | Match precision (never merged wrongly) / recall (found 98% of true matches) on labelled data |
| 51 of 3,661 (1.4%) | Match decisions that need a human |
| ~25 ms / ~13 s | Lakebase read speed / steward decision back to the lakehouse |
| 51 → 0 | Restricted entities visible before and after removing someone's access |

**Precision vs recall in one breath:** *precision is "when we merged, were we right?"; recall is "of all the true duplicates, how many did we catch?"*

---

## 8. The people in the room

| Persona | What they care about | What to show them |
|---|---|---|
| **CFO** (executive sponsor) | Organic growth, EBITDA margin, synergy delivery, one revenue number the auditors accept | The value slide and the tie-out to the cent |
| **Chief Client Officer** (co-sponsor) | Retention, cross-sell, AE productivity | The AE view and Genie |
| **Head of Client Data & Governance** (domain owner) | Duplicate rate, steward workload, provable access control, lineage | The steward view, ABAC and lineage |
| **Enterprise architect** (technical) | How it's built, scale, security, integration, cost | The journey and trade-offs slides, the pipeline, Lakebase |

---

## 9. If you get a question you can't answer

These are honest, safe moves:
- **"Great question. Let me show you rather than tell you"**, then open the app, lineage or evidence.
- **"In the build that's X. In your environment we'd confirm it in week one of the pilot."** Use this for anything about their real systems.
- **"I'll come back to you on that with specifics,"** then write it down visibly. That's credible, not weak.
- **Bridge back:** *"What matters for you is…"* plus the outcome (one client view, $6.9M, six weeks).

**Don't** invent insurance specifics. If it's about real commission rates, regulations or their systems, say it's something the pilot measures.
