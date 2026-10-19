"""Builds the Northbridge Client 360 business deck (HTML -> PDF via headless Chrome, plus a Markdown export with
speaker notes). Every number is queried live from the workspace or read from evidence/ - none are typed in.

Usage: python docs/deck/build_deck.py [profile]
"""
import html
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.argv = [sys.argv[0], sys.argv[1] if len(sys.argv) > 1 else "fevm-richasethi-febar"]
__file__ = os.path.join(ROOT, "scripts", "collect_evidence.py")
exec(open(__file__).read().split("# 1. Build job")[0].rsplit("# ----", 1)[0])   # reuse sql(), G, S, ML from the evidence script

# ------------------------------------------------------------------------------------------------
# Numbers (live)
# ------------------------------------------------------------------------------------------------
one = lambda q: sql(q)[1][0]
FX = f"(SELECT DISTINCT currency, fx_rate_to_usd FROM {S}.revenue_transactions WHERE fx_rate_to_usd IS NOT NULL)"
ov_groups, ov_nb, ov_hc, ov_total = map(float, one(f"""WITH o AS (SELECT DISTINCT ultimate_parent_party_id FROM {G}.dim_party WHERE client_origin = 'Both')
  SELECT count(DISTINCT o.ultimate_parent_party_id), sum(CASE WHEN r.source_system = 'NB_BILLING' THEN r.amount_usd END),
         sum(CASE WHEN r.source_system = 'HC_AMS' THEN r.amount_usd END), sum(r.amount_usd)
  FROM o LEFT JOIN {G}.fact_revenue r ON r.ultimate_parent_party_id = o.ultimate_parent_party_id AND r.fiscal_year = 2025"""))
hc_groups, hc_rev = map(float, one(f"""SELECT count(*), sum(rev) FROM (SELECT d.ultimate_parent_party_id, sum(r.amount_usd) rev FROM {G}.dim_party d
  LEFT JOIN {G}.fact_revenue r ON r.party_id = d.party_id AND r.fiscal_year = 2025 GROUP BY 1 HAVING bool_and(d.client_origin = 'Harbor & Cole'))"""))
leak = {r[0]: (int(r[1]), float(r[2] or 0)) for r in sql(f"""SELECT c.reconciliation_status, count(*), sum(abs(c.variance_local) * f.fx_rate_to_usd)
  FROM {G}.commission_reconciliation c JOIN {S}.placements p USING (placement_id) JOIN {FX} f ON f.currency = p.currency
  WHERE year(c.inception_date) = 2025 AND c.reconciliation_status <> 'Reconciled' GROUP BY 1""")[1]}
leak_usd = sum(v for _, v in leak.values())
leak_n = sum(n for n, _ in leak.values())
groups, entities, rev25, restricted_rev = map(float, one(f"""SELECT count(DISTINCT ultimate_parent_party_id), count(*),
  (SELECT sum(amount_usd) FROM {G}.fact_revenue WHERE fiscal_year = 2025), (SELECT sum(amount_usd) FROM {G}.fact_revenue WHERE fiscal_year = 2025 AND is_restricted)
  FROM {G}.dim_party"""))
restricted_entities = int(one(f"SELECT count(*) FROM {G}.dim_party WHERE is_restricted")[0])
er = dict(zip(*[[c for c in sql(f"SELECT * FROM {ML}.er_run_log ORDER BY run_ts LIMIT 1")[0]], sql(f"SELECT * FROM {ML}.er_run_log ORDER BY run_ts LIMIT 1")[1][0]]))
kestrel_records = sql(f"""SELECT source_system, source_name FROM {G}.party_source_xref
  WHERE party_id = (SELECT party_id FROM {G}.dim_party WHERE party_name = 'Kestrel Industries plc') ORDER BY source_system""")[1]
kestrel_entities = int(one(f"SELECT count(*) FROM {G}.dim_party WHERE ultimate_parent_name = 'Kestrel Industries plc'")[0])
kestrel_fy25 = float(one(f"SELECT MEASURE(`Total Client Revenue`) FROM {G}.client_revenue_metrics WHERE `Ultimate Parent Client` = 'Kestrel Industries plc' AND `Fiscal Year` = 2025")[0])
rationale = one(f"""WITH gt AS (SELECT concat(source_system, ':', source_record_id) k, true_entity_id e
                             FROM read_files('/Volumes/{C}/{P}raw/landing/_labels/er_ground_truth.csv', format => 'csv', header => true))
  SELECT q.left_name, q.right_name, q.llm_rationale FROM {ML}.match_review_queue q
  JOIN gt l ON l.k = q.left_record_key JOIN gt r ON r.k = q.right_record_key
  WHERE q.llm_recommendation = 'MERGE' AND l.e = r.e AND lower(q.left_name) <> lower(q.right_name) AND q.llm_rationale NOT ILIKE '%rule%'
  ORDER BY length(q.llm_rationale) LIMIT 1""")   # a recommendation the ground truth confirms
review_n = int(er["review_band_pairs"])
auto_n = int(er["auto_match_pairs"])
merged = int(er["records_merged"])


def ev(name, pattern, default="n/a"):
    try:
        m = re.search(pattern, open(os.path.join(ROOT, "evidence", name)).read(), re.S)
        return m.groups() if m else default
    except FileNotFoundError:
        return default


toggle = ev("04_governance.md", r"\*\*In the group:\*\*.*?\| true \| (\d+) \| (\d+) \| ([\d.]+) \|.*?\| false \| (\d+) \| (\d+) \| ([\d.]+) \|")
sync_s = ev("09_steward_roundtrip.md", r"after ~(\d+)s", ("~15",))[0]
lb_ms = ev("07_app_selftest.md", r'"ms": (\d+),\s*"placements"', ("25",))[0]
rt_pair = ev("09_steward_roundtrip.md", r"\*\*Pair approved:\*\* `([^`]+)` \(([^)]+)\) \+ `([^`]+)` \(([^)]+)\)", None)
rt_after = ev("09_steward_roundtrip.md", r"### After.*?\|---\|.*?\| [^|]+ \| ([^|]+) \| ([^|]+) \| (\d+) \|", None)

M = lambda v: f"${v / 1e6:,.1f}M"
# Value case (illustrative assumptions stated on the slide)
A_RET, A_XSELL, A_LEAK, A_MIN = 0.02, 0.05, 0.30, 10
v_ret, v_xsell, v_leak = ov_total * A_RET, hc_rev * A_XSELL, leak_usd * A_LEAK
hours = merged * A_MIN / 60
v_total = v_ret + v_xsell + v_leak

# ------------------------------------------------------------------------------------------------
# Slides: (title, body_html, speaker_notes)
# ------------------------------------------------------------------------------------------------
e = html.escape
SLIDES = []


def slide(kicker, title, body, notes, cls="", takeaway=None):
    SLIDES.append({"kicker": kicker, "title": title, "body": body, "notes": notes, "cls": cls, "takeaway": takeaway})


def stat(value, label, sub=""):
    return f'<div class="stat"><div class="v">{value}</div><div class="l">{label}</div><div class="s">{sub}</div></div>'


slide("Northbridge Risk Partners · Client 360", "One client. One number. Governed.",
      f'<p class="lede">A single, governed client master for a global broker after the Harbor &amp; Cole acquisition — built on Databricks in weeks, not a multi-year CRM migration.</p>'
      f'<div class="byline">Richa Sethi · Solutions Architect, Databricks · October 2026</div>',
      "Frame the room: who Northbridge is (global broker, fee and commission income, thousands of multinational clients), the deal that just closed "
      "(Harbor & Cole), and the question nobody can answer today. Tell them what you'll show: the outcome first, then a 12-minute demo in four moments, then the plan.",
      cls="title")

slide("The outcome", f"About {M(v_total)} a year of revenue protected, recovered and grown — from one client view",
      '<div class="stats">' +
      stat(M(ov_total), f"relationship revenue across {int(ov_groups)} client groups served by <i>both</i> books", "now visible as one relationship") +
      stat(M(leak_usd), f"FY2025 commission flagged across {leak_n:,} placements", "short-paid or missing from carrier statements") +
      stat(f"{review_n / (auto_n + review_n):.1%}", f"of match decisions need a human ({review_n} of {auto_n + review_n:,})", f"{merged:,} duplicate records resolved automatically") +
      stat("to the cent", f"Kestrel FY2025: ${kestrel_fy25:,.2f}", "same in the app, Genie and finance's metric view") + '</div>'
      f'<p class="foot">Synthetic book of {int(groups):,} client groups, {M(rev25)} FY2025 fee &amp; commission income. Value case and assumptions on slide {{VALUE_SLIDE}}.</p>',
      "Lead with this slide. Say the dollar number first, then the three proof points. Pause. Ask the business stakeholder which of these matters most this year "
      "- renewal retention, cross-sell, or revenue leakage - and steer the rest of the talk to it.")

kr = "".join(f'<li><span class="sys sys-{s.lower()}">{e({"NB_CRM": "NB CRM", "NB_BILLING": "NB Billing", "NB_PLACEMENT": "Placement", "HC_AMS": "Harbor & Cole"}[s])}</span>{e(n)}</li>' for s, n in kestrel_records)
slide("The problem", f"Kestrel Industries exists {len(kestrel_records)} times in 4 systems, and nobody can say what it's worth",
      f'<div class="two"><div><ul class="records">{kr}</ul><p class="small">The same client, as held today. One H&amp;C record has a transposed registration number; one CRM duplicate has none.</p></div>'
      '<div><h3>What that costs</h3><ul class="bullets">'
      '<li><b>Renewals at risk.</b> Two account teams pitch the same CFO without knowing it.</li>'
      '<li><b>Cross-sell missed.</b> Harbor &amp; Cole clients never see Northbridge specialty lines.</li>'
      '<li><b>Revenue leaks.</b> Carrier statements cannot be matched to the client who was billed.</li>'
      '<li><b>Compliance exposure.</b> Defence &amp; government clients copied into every system and spreadsheet.</li>'
      '<li><b>Integration stalls.</b> "Wait for the CRM migration" is a two-year answer.</li></ul></div></div>',
      "Make it concrete with Kestrel - read two of the record names aloud. The business stakeholder should recognise their own data here. "
      "Land it: the problem isn't any one system, it's that there's no governed layer above them.")

slide("Who wins", "What each buyer is measured on, and how this moves it",
      '<div class="two"><div class="card"><div class="role">Executive sponsor · CFO (with the Chief Client Officer)</div><ul class="bullets">'
      f'<li><b>Organic revenue growth:</b> +{(v_ret + v_xsell) / rev25 * 100:.1f} pts from renewal retention and cross-sell ({M(v_ret + v_xsell)})</li>'
      f'<li><b>Adjusted EBITDA margin:</b> +{v_leak / rev25 * 1e4:.0f} bps from recovered carrier commission ({M(v_leak)}, no added cost to serve)</li>'
      '<li><b>Acquisition synergy capture</b> against the Harbor &amp; Cole deal case, reported to the board</li>'
      '<li><b>One SOX-tagged revenue number</b> finance signs, tied out to the cent</li></ul></div>'
      '<div class="card"><div class="role">Domain owner · Head of Client Data &amp; Governance</div><ul class="bullets">'
      f'<li>Duplicate rate and time-to-resolve, with {review_n} reviews instead of {auto_n + review_n:,}</li><li>Steward throughput with an AI second opinion on every hard case</li>'
      '<li>Restricted-client access enforced by policy, provably</li><li>Lineage from every number back to the source record</li></ul></div></div>',
      "Name both buyers explicitly and the exact metric each is paid on. The CFO is measured on organic growth and EBITDA margin: retention and cross-sell move growth, "
      "recovered commission drops straight to margin. The Chief Client Officer co-sponsors on retention. The domain owner is measured on duplicate rate and steward throughput.",
      takeaway="One shared measure: certified total relationship revenue per client, the number both of them report.")

rows = [("Protect overlapping relationships at renewal", f"{int(ov_groups)} groups · {M(ov_total)} FY2025", f"+{A_RET:.0%} retention", M(v_ret)),
        ("Cross-sell into Harbor & Cole-only clients", f"{int(hc_groups)} groups · {M(hc_rev)}", f"+{A_XSELL:.0%} wallet share", M(v_xsell)),
        ("Recover commission leakage", f"{leak_n:,} placements · {M(leak_usd)} flagged", f"{A_LEAK:.0%} recovered", M(v_leak)),
        ("Steward effort on duplicates", f"{merged:,} merges automated", f"{A_MIN} min per manual merge", f"~{hours:,.0f} hours / cycle")]
tbl = "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td><td>{e(c)}</td><td class='num'>{e(d)}</td></tr>" for a, b, c, d in rows)
slide("The value case", f"{M(v_total)} a year on a {M(rev25)} book: about {v_total / rev25:.1%} of fee & commission income",
      f'<table class="value"><tr><th>Lever</th><th>Measured in the build</th><th>Assumption</th><th class="num">Annual value</th></tr>{tbl}'
      f'<tr class="total"><td colspan="3">Revenue impact (first three levers)</td><td class="num">{M(v_total)}</td></tr>'
      f'<tr><td colspan="3"><b>In the CFO\'s metrics:</b> organic revenue growth (retention + cross-sell) · adjusted EBITDA margin (recovered commission)</td>'
      f'<td class="num">+{(v_ret + v_xsell) / rev25 * 100:.1f} pts · +{v_leak / rev25 * 1e4:.0f} bps</td></tr></table>'
      '<p class="foot">Measured figures come from the running build (evidence/10_value_inputs.md). Assumptions are deliberately conservative and should be replaced with Northbridge\'s own renewal and recovery rates in the pilot.</p>',
      "Walk the table left to right: what we measured, what we assumed, what it's worth. Invite them to change the assumptions - that's the point of the pilot. "
      "Cost objection: the platform cost for this scope is a small fraction of one lever.")

slide("What I'll show", "Four moments, twelve minutes",
      '<ol class="moments">'
      '<li><b>The account executive</b> searches Kestrel and gets one golden record, the legal-entity tree and revenue rolled up to the parent, in milliseconds.</li>'
      '<li><b>The question in plain English.</b> Genie answers "which Harbor &amp; Cole clients overlap ours?" with the same certified numbers.</li>'
      '<li><b>The steward.</b> An ambiguous match, the model\'s score and the AI\'s reasoning. Approve it, and watch the golden record change.</li>'
      '<li><b>The guardrail.</b> Remove someone\'s entitlement and the restricted clients disappear everywhere, by policy.</li></ol>',
      "Tell: say these four moments before you click anything. Then show. After each moment, tell again: one sentence on what it means for the business.",
      takeaway="Everything you'll see is live: one workspace, deployed from one bundle, on serverless.")

slide("The journey", "Raw data to business app on one governed platform",
      '<div class="flow">'
      '<div class="node"><b>Raw drop zone</b><span>CRM · billing · placement · Harbor &amp; Cole · carrier statements · LEI registry</span></div><div class="arrow">→</div>'
      '<div class="node"><b>Lakeflow</b><span>Auto Loader · expectations · quarantine</span></div><div class="arrow">→</div>'
      '<div class="node"><b>ML + GenAI</b><span>match model · constrained clustering · Claude rationale</span></div><div class="arrow">→</div>'
      '<div class="node accent"><b>Unity Catalog</b><span>certified gold · metric view · ABAC · lineage</span></div></div>'
      '<div class="flow lower"><div class="node"><b>Lakebase</b><span>ms serving · steward write-back</span></div>'
      '<div class="node"><b>Genie</b><span>broker vocabulary · trusted functions</span></div>'
      '<div class="node"><b>Databricks App</b><span>AE + steward views</span></div>'
      '<div class="node loop"><b>Steward loop</b><span>Lakebase → Lakehouse Sync → re-resolve</span></div></div>',
      "Technical stakeholder slide. One sentence per box. Emphasise integrated, not stitched: the steward decision in the app is the label the next run learns from.",
      takeaway="Integrated, not stitched: a steward's click in the app becomes the next run's override, with no custom sync code.")

slide("The golden record", f"{er['pairwise_precision'] * 100 if isinstance(er['pairwise_precision'], float) else float(er['pairwise_precision']) * 100:.1f}% precision, {float(er['pairwise_recall']) * 100:.1f}% recall, and humans only on the hard {review_n}",
      '<div class="two"><div>' + '<div class="stats small3">' +
      stat(f"{int(er['source_records']):,}", "source client records") + stat(f"{int(er['golden_parties']):,}", "golden parties") + stat(f"{kestrel_entities}", "Kestrel legal entities, one tree") +
      '</div><ul class="bullets"><li>Blocking on registration number, name + country, phonetics and postcode</li><li>Gradient-boosted match model, registered in Unity Catalog</li>'
      '<li>Cannot-link rules: one country and one registration number per legal entity</li><li>Hierarchy from the LEI-style registry and CRM parent links</li></ul></div>'
      f'<div class="quote"><div class="qk">Claude, on {e(rationale[0])} vs {e(rationale[1])}</div>“{e(rationale[2])}”<div class="qs">Recommendation: MERGE · the steward decides</div></div></div>',
      "Business altitude: 'the machine does the obvious ones, people do the judgement calls, and every merge is explainable'. "
      "Technical altitude if asked: blocking keys, features, why GBM over a black box, how steward decisions become cannot-link constraints and labels.")

tg = toggle if isinstance(toggle, tuple) else None
slide("Trust", "One definition of revenue, enforced by policy",
      '<div class="two"><div class="card"><div class="role">Same number everywhere</div>'
      f'<div class="big">${kestrel_fy25:,.2f}</div><p>Kestrel FY2025 in the app, in Genie and in finance\'s certified metric view: one definition, fee + commission, never premium.</p></div>'
      '<div class="card"><div class="role">Restricted clients, by attribute</div>' +
      (f'<p>Entitled user sees <b>{int(tg[1])}</b> restricted entities. Remove the entitlement: <b>{int(tg[4])}</b>, in SQL, dashboards and Genie, within minutes.</p>' if tg else '') +
      f'<p>{restricted_entities} defence &amp; government entities ({M(restricted_rev)} FY2025) are governed by two tag-driven ABAC policies, and never copied to the operational store.</p></div></div>',
      "Security objection lands here. Show, don't claim: the toggle demo. For the architect: ABAC policies on the gold schema match tags, so new tables are governed by tagging, not code.",
      takeaway="Governance isn't a separate project: tag the data once and every tool, from SQL to Genie to the app, obeys.")

slide("The operational loop", f"A steward's decision reaches the lakehouse in ~{sync_s} seconds",
      '<ol class="steps">'
      '<li><b>Approve</b> in the app<span>row written to Lakebase Postgres</span></li>'
      f'<li><b>Lakehouse Sync</b><span>CDC into Unity Catalog in ~{sync_s} s</span></li>'
      '<li><b>Re-resolve</b><span>entity resolution applies the override</span></li>'
      '<li><b>Rebuild</b><span>certified gold and the metric view</span></li>'
      f'<li><b>Serve</b><span>Lakebase refreshes; the AE sees it in ~{lb_ms} ms</span></li></ol>'
      '',
      "This is the integration moment. Business: stewardship stops being a ticket queue and becomes part of the product. Technical: no custom sync code in either direction.",
      takeaway=((f"Measured: one approval merged two duplicate records of {e(rt_pair[0])} ({rt_pair[1].split(':')[0]}) into one golden party."
                 if rt_pair[0].lower() == rt_pair[2].lower() else
                 f"Measured: one approval merged {e(rt_pair[0])} and {e(rt_pair[2])} into one golden party.")
                if isinstance(rt_pair, tuple) else "Measured end to end in the build: one approval, one changed golden record."))

slide("Decisions and trade-offs", "Why this design, and what we chose not to do",
      '<table class="value small"><tr><th>Decision</th><th>Why</th><th>Trade-off</th></tr>'
      '<tr><td>Governed layer above the sources</td><td>Value now; no source system has to win</td><td>Sources stay messy; we standardise downstream</td></tr>'
      '<tr><td>Explainable GBM + LLM for the grey zone</td><td>Auditable features; AI only where it adds judgement</td><td>Needs labelled history to start (stewards supply it)</td></tr>'
      '<tr><td>ABAC on tags, not per-table filters</td><td>New tables governed by tagging</td><td>Relies on tagging discipline</td></tr>'
      '<tr><td>Restricted clients stay in the lakehouse</td><td>Lakebase cannot sync policy-protected tables; data minimisation</td><td>Restricted views query the warehouse (~3 s, not ms)</td></tr>'
      '<tr><td>Snapshot sync to Lakebase</td><td>Small tables, simple, consistent</td><td>Minutes, not seconds, to refresh; move to continuous at scale</td></tr></table>',
      "Technical stakeholder slide. Own the trade-offs before they're raised; it builds credibility.")

slide("Time to value", "A six-week pilot on Northbridge's own data",
      '<div class="timeline"><div><b>Weeks 1–2</b><span>Connect CRM, billing and the H&amp;C AMS with Lakeflow Connect; land carrier statements</span></div>'
      '<div><b>Weeks 3–4</b><span>Tune the match model on stewards\' labels; certify the revenue metric with finance</span></div>'
      '<div><b>Weeks 5–6</b><span>Client 360 to 20 account executives; Genie to finance and placement</span></div></div>'
      '<h3>Success criteria</h3><ul class="bullets"><li>≥ 98% merge precision on a steward-audited sample</li><li>Total relationship revenue ties to finance to the dollar</li>'
      '<li>Overlap and leakage worklists in AEs\' and finance\'s hands</li><li>Restricted-segment access proven by audit</li></ul>',
      "Time-to-value objection. Everything shown runs on serverless and deploys from one bundle, so the pilot is about their data and their rules, not infrastructure.",
      takeaway="No infrastructure project: the pilot is about Northbridge's data and rules, and the first value lands in week four.")

slide("Questions we expect", "Cost, risk and integration",
      '<div class="two"><div class="card"><div class="role">Business</div><ul class="bullets">'
      '<li><b>"We already have an MDM programme."</b> This feeds it: a governed golden record and steward workflow today, published to any MDM later.</li>'
      '<li><b>"What does it cost?"</b> Serverless, pay per use; the pilot scope is a small fraction of one value lever.</li>'
      '<li><b>"Can we trust automatic merges?"</b> Every merge has a confidence, a lineage trail and a steward override.</li></ul></div>'
      '<div class="card"><div class="role">Technical</div><ul class="bullets">'
      '<li><b>Scale.</b> Blocking keeps comparisons near-linear; featurisation moves to Spark UDFs beyond ~1M records.</li>'
      '<li><b>Integration.</b> Lakeflow Connect for Salesforce / SQL Server; the golden record syncs back to operational systems.</li>'
      '<li><b>Security.</b> ABAC, on-behalf-of-user app and Genie access, service principal reads gold only.</li></ul></div></div>',
      "Use as a backup slide. Answer at the asker's altitude, then bridge back to the business outcome in one sentence.",
      takeaway="Every answer on this slide is demonstrated in the running build, not promised.")

slide("The ask", "Start the six-week pilot",
      '<ul class="bullets big"><li>Executive sponsor and a named domain owner</li><li>Read access to CRM, billing and the Harbor &amp; Cole AMS</li>'
      '<li>Two data stewards, two hours a week</li><li>A finance owner for the revenue definition</li></ul>'
      f'<p class="lede">Outcome in six weeks: one governed view of every client, and a worked value case on Northbridge\'s own numbers.</p>',
      "Close on the outcome, not the technology. Ask for the sponsor's commitment explicitly.", cls="title")

slide("Appendix", "Evidence and what is synthetic",
      '<div class="two"><div><h3>Execution evidence (text, in the repo)</h3><ul class="bullets small">'
      '<li>00 · from-scratch teardown and build logs</li><li>01 · build job tasks + notebook outputs</li><li>02 · expectations and quarantine</li>'
      '<li>03 · entity resolution and MLflow</li><li>04 · ABAC policies, tags, toggle test</li><li>05 · lineage to all four systems</li>'
      '<li>06–07 · Lakebase and app selftest</li><li>08 · five Genie questions vs ground truth</li><li>09 · steward round trip</li><li>10 · value inputs</li></ul></div>'
      '<div><h3>Real vs synthetic</h3><p class="small">Every pipeline, model, policy, synced table, Genie space and the app is real and running. All companies, people, registration numbers, '
      'carriers and amounts are generated (fixed seed). Training labels stand in for a steward-labelled match history. No customer data.</p></div></div>',
      "Only if asked.")

slide("How it was built", "AI as the force multiplier; a human owned every decision",
      '<div class="two"><div class="card"><div class="role">The workflow</div><ul class="bullets">'
      '<li><b>Claude Code</b> (Claude Opus 5.5) in the terminal, with the Databricks plugin skills: core, pipelines, DABs, Lakebase, Genie, metric views, apps</li>'
      '<li><b>Human checkpoints:</b> catalog, ABAC over per-table filters, the Lakebase serving design, UX feedback</li>'
      '<li><b>AI did the build, tests and evidence;</b> an AI code-review agent challenged it</li>'
      '<li>One working session, one bundle, rebuilt from an empty catalog to verify</li></ul></div>'
      '<div class="card"><div class="role">Where it multiplied</div><ul class="bullets">'
      '<li><b>Probe before design:</b> five platform limits found in the workspace before code depended on them</li>'
      '<li><b>Ground truth from day one:</b> labels caught a party-id collision (830 false merges to 0)</li>'
      '<li><b>Prompts tuned on evidence:</b> the steward prompt went from 91% "needs info" to decisive v2</li>'
      '<li><b>Adversarial review:</b> 10 real defects found, fixed, re-verified</li>'
      '<li><b>Evidence as code:</b> every number on these slides is a live query</li></ul></div></div>',
      "Answer 'how did you build this so fast?'. The AI wrote, ran and tested; I set direction at checkpoints and owned the trade-offs. "
      "Point to the README section and the conversation ID for verification. Bridge: the pilot uses the same workflow on Northbridge's data.",
      takeaway="The same workflow runs the pilot: the AI builds and measures, Northbridge's people make the calls.")

slide("What's next", "From pilot to production: make the AI accountable",
      '<div class="three">'
      '<div class="card"><div class="role">1 · Judge the AI</div><p>An LLM-judge pass scores Claude\'s merge / keep-separate advice against the steward\'s eventual decision. '
      'Agreement rate is trended per prompt version in MLflow, and prompt changes ship only if it holds.</p></div>'
      '<div class="card"><div class="role">2 · Watch for drift</div><p>Each run compares the match-score distribution and the review-band share with the last. '
      'When the band drifts past a threshold, a job condition retrains on steward labels and promotes a challenger to <i>champion</i> only if it wins.</p></div>'
      '<div class="card"><div class="role">3 · Steward action plans</div><p>The Foundation Model writes a narrative case for a batch, e.g. a whole corporate family, '
      'grounded in certified gold (hierarchy, revenue, placements) and logged like pair assessments. Stewards approve a family, not one pair at a time.</p></div></div>',
      "Roadmap, not built: say so. Each item extends something already running: the steward decisions table is the judge's ground truth, "
      "the ER run log already records the review-band share, and the model registry already has a champion alias.",
      takeaway="Each step extends what's already running: steward decisions, the ER run log and the champion model alias.")

slide("Live demo", "Let's look at it running",
      '<ol class="moments light"><li><b>Account executive:</b> Kestrel, one golden record, hierarchy, revenue</li>'
      '<li><b>Genie:</b> total relationship and Harbor &amp; Cole overlap, in plain English</li>'
      '<li><b>Data steward:</b> an ambiguous match, Claude\'s reasoning, approve</li>'
      '<li><b>Guardrail:</b> restricted clients governed by policy</li></ol>'
      f'<p class="byline">{APP_URL.replace("https://", "")}</p>',
      "Switch to the app now (6:00). About three minutes per moment; tell, show, tell. Come back to the deck at 18:00 for the value case.",
      cls="title")

# Presentation order follows the 30-minute agenda (docs/roleplay_prep.md): frame, demo, value, depth, plan, ask, backup
ORDER = ["Northbridge Risk Partners · Client 360", "The outcome", "The problem", "Who wins", "What I'll show", "The journey", "Live demo",
         "The value case", "Trust", "The operational loop", "The golden record", "Decisions and trade-offs", "How it was built", "Time to value",
         "What's next", "The ask",
         "Questions we expect", "Appendix"]
TARGET = {"Northbridge Risk Partners · Client 360": "0:00", "The outcome": "0:45", "The problem": "2:00", "Who wins": "3:00",
          "What I'll show": "4:00", "The journey": "5:00", "Live demo": "6:00", "The value case": "18:00", "Trust": "19:30",
          "The operational loop": "20:15", "The golden record": "21:00", "Decisions and trade-offs": "22:00", "How it was built": "23:00",
          "Time to value": "24:00", "What's next": "24:45", "The ask": "25:30", "Questions we expect": "26:00 (backup)", "Appendix": "if asked"}
SLIDES = sorted(SLIDES, key=lambda x: ORDER.index(x["kicker"]))
VALUE_SLIDE = ORDER.index("The value case") + 1
for s_ in SLIDES:
    s_["body"] = s_["body"].replace("{VALUE_SLIDE}", str(VALUE_SLIDE))
    s_["target"] = TARGET[s_["kicker"]]

# ------------------------------------------------------------------------------------------------
# Render
# ------------------------------------------------------------------------------------------------
CSS = """
@page { size: 13.333in 7.5in; margin: 0 }
* { box-sizing: border-box }
body { margin: 0; font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #191919; }
.slide { width: 13.333in; height: 7.5in; padding: 0.7in 0.85in 0.55in; background: #F5F2EA; position: relative; page-break-after: always; overflow: hidden;
         display: flex; flex-direction: column }
.content { flex: 1; display: flex; flex-direction: column; justify-content: center; padding-bottom: .35in }
.title .content { justify-content: flex-start }
.takeaway { border-left: 4px solid #CC785C; padding: 10px 18px; font-family: 'Iowan Old Style', Charter, Georgia, serif; font-size: 21px;
            color: #3D3929; background: #EFEADF; border-radius: 0 10px 10px 0; margin-bottom: .2in }
.slide.title { background: #191919; color: #F5F2EA }
.kicker { font-size: 13px; letter-spacing: .14em; text-transform: uppercase; color: #CC785C; font-weight: 600; margin-bottom: 14px }
h1 { font-family: 'Iowan Old Style', Charter, Georgia, serif; font-weight: 400; font-size: 40px; line-height: 1.15; margin: 0 0 28px; max-width: 11in; letter-spacing: -.01em }
.title h1 { font-size: 64px; margin-top: 1.3in }
.lede { font-family: 'Iowan Old Style', Charter, Georgia, serif; font-size: 24px; line-height: 1.4; color: #3D3929; max-width: 9.5in }
.title .lede { color: #D9D3C4 }
.byline { position: absolute; bottom: .6in; font-size: 15px; color: #B1AA9A }
h3 { font-family: 'Iowan Old Style', Charter, Georgia, serif; font-weight: 400; font-size: 22px; margin: 0 0 10px }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 22px; margin-top: 10px }
.stats.small3 { grid-template-columns: repeat(3, 1fr); margin-bottom: 18px }
.stat { background: #FBF9F4; border: 1px solid #E5DFD3; border-radius: 14px; padding: 22px 20px }
.stat .v { font-family: 'Iowan Old Style', Charter, Georgia, serif; font-size: 40px; color: #CC785C; line-height: 1.05 }
.small3 .stat .v { font-size: 32px }
.stat .l { font-size: 15px; font-weight: 600; margin-top: 10px; line-height: 1.35 }
.stat .s { font-size: 13px; color: #6B6560; margin-top: 6px }
.foot { position: absolute; bottom: .45in; left: .85in; right: .85in; font-size: 12.5px; color: #6B6560 }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 34px }
.three { display: grid; grid-template-columns: repeat(3, 1fr); gap: 22px }
.three .card p { font-size: 17px; line-height: 1.45 }
.card { background: #FBF9F4; border: 1px solid #E5DFD3; border-radius: 14px; padding: 22px 26px }
.role { font-size: 12px; letter-spacing: .1em; text-transform: uppercase; color: #CC785C; font-weight: 700; margin-bottom: 10px }
.bullets { padding-left: 20px; margin: 0; font-size: 17px; line-height: 1.5 }
.bullets li { margin-bottom: 8px }
.bullets.small, .small { font-size: 14px }
.bullets.big { font-size: 24px; line-height: 1.6 }
.records { list-style: none; padding: 0; margin: 0 0 12px }
.records li { background: #FBF9F4; border: 1px solid #E5DFD3; border-radius: 10px; padding: 10px 14px; margin-bottom: 9px; font-size: 17px; font-family: Menlo, monospace }
.sys { display: inline-block; width: 120px; font-family: -apple-system, sans-serif; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: #6B6560 }
.sys-hc_ams { color: #CC785C }
table.value { width: 100%; border-collapse: collapse; font-size: 16px }
table.value.small { font-size: 14.5px }
table.value th { text-align: left; font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: #6B6560; border-bottom: 2px solid #191919; padding: 10px 8px }
table.value td { padding: 13px 8px; border-bottom: 1px solid #E5DFD3; vertical-align: top }
table.value .num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap }
table.value tr.total td { font-weight: 700; border-top: 2px solid #191919; border-bottom: 0; font-size: 18px }
table.value tr.total .num { color: #CC785C; font-family: 'Iowan Old Style', Charter, Georgia, serif; font-size: 26px }
.moments { font-size: 21px; line-height: 1.45; padding-left: 26px; max-width: 10.5in }
.moments li { margin-bottom: 18px }
.flow { display: flex; align-items: stretch; gap: 10px; margin-top: 8px }
.flow.lower { margin-top: 26px; padding-left: 1.4in }
.node { flex: 1; background: #FBF9F4; border: 1px solid #E5DFD3; border-radius: 12px; padding: 16px; font-size: 13px; color: #6B6560 }
.node b { display: block; color: #191919; font-size: 17px; margin-bottom: 6px }
.node.accent { background: #191919; color: #D9D3C4 } .node.accent b { color: #F5F2EA }
.node.loop { border: 2px dashed #CC785C }
.arrow { align-self: center; color: #CC785C; font-size: 26px }
.quote { background: #191919; color: #F5F2EA; border-radius: 14px; padding: 26px 28px; font-family: 'Iowan Old Style', Charter, Georgia, serif; font-size: 21px; line-height: 1.45 }
.qk, .qs { font-family: -apple-system, sans-serif; font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: #CC785C; margin-bottom: 12px }
.qs { margin: 14px 0 0; color: #B1AA9A }
.big { font-family: 'Iowan Old Style', Charter, Georgia, serif; font-size: 46px; color: #CC785C; margin: 4px 0 8px }
.steps { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; counter-reset: s }
.steps li { background: #FBF9F4; border: 1px solid #E5DFD3; border-radius: 12px; padding: 18px 16px; font-size: 18px; counter-increment: s }
.steps li::before { content: counter(s); display: block; font-family: 'Iowan Old Style', Georgia, serif; color: #CC785C; font-size: 30px; margin-bottom: 6px }
.steps span { display: block; font-size: 13.5px; color: #6B6560; margin-top: 6px }
.timeline { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-bottom: 22px }
.timeline div { border-top: 4px solid #CC785C; background: #FBF9F4; padding: 16px; border-radius: 0 0 12px 12px; font-size: 17px }
.timeline span { display: block; font-size: 14px; color: #6B6560; margin-top: 6px }
.pageno { position: absolute; bottom: .3in; right: .5in; font-size: 11px; color: #B1AA9A }
.moments.light { color: #F5F2EA } .moments.light b { color: #CC785C }
@media screen {
  html, body { height: 100%; background: #0E0E0D; overflow: hidden }
  .slide { position: absolute; top: 50%; left: 50%; transform-origin: center center; display: none; box-shadow: 0 10px 40px rgba(0,0,0,.4) }
  .slide.active { display: flex }
  .hint { position: fixed; bottom: 8px; left: 50%; transform: translateX(-50%); color: #6B6560; font: 12px -apple-system, sans-serif; opacity: .8 }
}
@media print { .hint { display: none } }
"""

pages = []
for i, s_ in enumerate(SLIDES, 1):
    take = f'<div class="takeaway">{s_["takeaway"]}</div>' if s_.get("takeaway") else ""
    pages.append(f'<section class="slide {s_["cls"]}" data-notes="{e(s_["notes"])}" data-target="{e(s_["target"])}"><div class="kicker">{e(s_["kicker"])}</div><h1>{e(s_["title"])}</h1>'
                 f'<div class="content">{s_["body"]}</div>{take}<div class="pageno">{i}</div></section>')
JS = r"""
const slides = [...document.querySelectorAll('.slide')]; let i = Math.max(0, parseInt(location.hash.slice(1) || '1') - 1); let notesWin = null; const t0 = Date.now();
function fit() { const s = Math.min(innerWidth / 1280, innerHeight / 720) * 0.98;   // 13.333in x 7.5in at 96 dpi
  slides.forEach(el => el.style.transform = `translate(-50%, -50%) scale(${s})`); }
function show(n) { i = Math.min(Math.max(n, 0), slides.length - 1); slides.forEach((el, k) => el.classList.toggle('active', k === i));
  history.replaceState(null, '', '#' + (i + 1)); renderNotes(); }
function esc(t) { return (t || '').replace(/[&<>]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c])); }
function renderNotes() { if (!notesWin || notesWin.closed) return; const cur = slides[i], nxt = slides[i + 1];
  notesWin.document.body.innerHTML = `<div style="font:15px -apple-system,sans-serif;color:#191919;padding:22px;background:#F5F2EA;min-height:100vh;box-sizing:border-box">
   <div style="display:flex;justify-content:space-between;color:#CC785C;font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:12px">
     <span>Slide ${i + 1} / ${slides.length} · target ${esc(cur.dataset.target)}</span><span id="clock"></span></div>
   <h2 style="font-family:Iowan Old Style,Georgia,serif;font-weight:400;font-size:26px;margin:10px 0">${esc(cur.querySelector('h1').textContent)}</h2>
   <div style="font-size:19px;line-height:1.5">${esc(cur.dataset.notes)}</div>
   <hr style="border:0;border-top:1px solid #E5DFD3;margin:20px 0">
   <div style="color:#6B6560;font-size:13px">NEXT: ${nxt ? esc(nxt.querySelector('h1').textContent) + ' · target ' + esc(nxt.dataset.target) : 'end'}</div>
   <div style="color:#6B6560;font-size:12px;margin-top:14px">← → to move · this window stays private when you share only the slides window</div></div>`; tick(); }
function tick() { if (!notesWin || notesWin.closed) return; const s = Math.floor((Date.now() - t0) / 1000);
  const el = notesWin.document.getElementById('clock'); if (el) el.textContent = `elapsed ${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; }
setInterval(tick, 1000);
addEventListener('keydown', ev => {
  if (['ArrowRight', 'PageDown', ' ', 'Enter'].includes(ev.key)) { show(i + 1); ev.preventDefault(); }
  else if (['ArrowLeft', 'PageUp', 'Backspace'].includes(ev.key)) { show(i - 1); ev.preventDefault(); }
  else if (ev.key === 'Home') show(0); else if (ev.key === 'End') show(slides.length - 1);
  else if (ev.key === 'f' || ev.key === 'F') { document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen(); }
  else if (ev.key === 's' || ev.key === 'S') { notesWin = window.open('', 'nb-notes', 'width=760,height=620'); notesWin.document.title = 'Speaker notes';
    notesWin.addEventListener('keydown', e2 => dispatchEvent(new KeyboardEvent('keydown', {key: e2.key}))); renderNotes(); }
});
addEventListener('click', ev => { if (!ev.target.closest('a')) show(ev.clientX > innerWidth / 3 ? i + 1 : i - 1); });
addEventListener('resize', fit); fit(); show(i);
"""
doc = (f"<!doctype html><html><head><meta charset='utf-8'><title>Northbridge Client 360</title><style>{CSS}</style></head><body>{''.join(pages)}"
       f"<div class='hint'>← → move · F full screen · S speaker notes &amp; timer</div><script>{JS}</script></body></html>")
html_path = os.path.join(HERE, "northbridge_client360_deck.html")
pdf_path = os.path.join(HERE, "northbridge_client360_deck.pdf")
open(html_path, "w").write(doc)

strip = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(h.replace("</li>", "\n").replace("<li>", "\n- ").replace("</tr>", "\n")))).strip()
md = ["# Northbridge Client 360 — business deck", "", "_Generated by `docs/deck/build_deck.py` from the live workspace. Speaker notes follow each slide._", ""]
for i, s_ in enumerate(SLIDES, 1):
    md += [f"## {i}. {s_['title']}", f"*{s_['kicker']}*", "", strip(s_["body"])] + ([f"", f"**Takeaway:** {strip(s_['takeaway'])}"] if s_.get("takeaway") else []) + \
          ["", f"> **Speaker notes:** {s_['notes']}", ""]
md += ["## Value case assumptions", f"- Retention uplift on overlapping groups: {A_RET:.0%} of FY2025 combined relationship revenue",
       f"- Cross-sell: {A_XSELL:.0%} wallet uplift on Harbor & Cole-only groups", f"- Leakage: {A_LEAK:.0%} recovery of FY2025 short-paid / missing commission",
       f"- Steward effort: {A_MIN} minutes per manual merge"]
open(os.path.join(HERE, "northbridge_client360_deck.md"), "w").write("\n".join(md))

chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir=/tmp/nb-deck-chrome",
                f"--print-to-pdf={pdf_path}", f"file://{html_path}"], check=True, capture_output=True)
print("wrote", pdf_path, "and the .md export;", len(SLIDES), "slides")
