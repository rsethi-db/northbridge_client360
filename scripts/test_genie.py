"""Ask the five acceptance questions through the Genie Conversation API and check each answer against
ground-truth SQL on the certified tables. Writes evidence/08_genie_test_results.md.

Usage: python scripts/test_genie.py [profile]
"""
import os
import sys
from datetime import datetime, timezone

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

PROFILE = sys.argv[1] if len(sys.argv) > 1 else "fevm-richasethi-febar"
G = "richasethi_febar_catalog.nb_gold"
WAREHOUSE = "f4edbf03911f5f8e"
w = WorkspaceClient(profile=PROFILE)
space = next(s.space_id for s in w.genie.list_spaces().spaces if s.title == "Northbridge Client 360")

CASES = [
    ("What's our total revenue with Kestrel Industries plc across all entities?",
     f"SELECT `Fiscal Year`, round(MEASURE(`Total Client Revenue`), 2) AS total FROM {G}.client_revenue_metrics "
     f"WHERE `Ultimate Parent Client` = 'Kestrel Industries plc' GROUP BY ALL ORDER BY 1"),
    ("Which acquired Harbor & Cole clients overlap with existing Northbridge clients?",
     f"SELECT count(*) AS overlapping_entities, count(DISTINCT ultimate_parent_party_id) AS client_groups FROM {G}.dim_party WHERE client_origin = 'Both'"),
    ("Top 10 clients by commission income this year, rolled up to parent",
     f"SELECT `Ultimate Parent Client`, round(MEASURE(`Commission Income`), 2) AS commission FROM {G}.client_revenue_metrics "
     f"WHERE `Fiscal Year` = year(current_date()) GROUP BY ALL ORDER BY commission DESC LIMIT 10"),
    ("Which clients have placements with more than three carriers?",
     f"SELECT count(*) AS clients FROM {G}.clients_by_carrier_count(4)"),
    ("How many party records were merged by the entity resolution model last run?",
     f"SELECT records_merged, source_records, golden_parties FROM {G}.er_run_history WHERE is_latest_run"),
]


def run_sql(q):
    r = w.statement_execution.execute_statement(warehouse_id=WAREHOUSE, statement=q, wait_timeout="50s")
    assert r.status.state == StatementState.SUCCEEDED, r.status
    cols = [c.name for c in r.manifest.schema.columns]
    return cols, r.result.data_array or []


def table_md(cols, rows, n=12):
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join("" if v is None else str(v) for v in row) + " |" for row in rows[:n]]
    if len(rows) > n:
        out.append(f"| ... {len(rows) - n} more rows |")
    return "\n".join(out)


lines = [f"# Genie acceptance test - space `{space}`", f"Run at {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} as `{w.current_user.me().user_name}`", ""]
for q, truth in CASES:
    print("Q:", q)
    msg = w.genie.start_conversation_and_wait(space, q)
    text, sql, cols, rows = None, None, [], []
    for att in msg.attachments or []:
        if att.text and att.text.content:
            text = att.text.content
        if att.query:
            sql = att.query.query
            text = text or att.query.description
            res = w.genie.get_message_attachment_query_result(space, msg.conversation_id, msg.message_id, att.attachment_id)
            sr = res.statement_response
            if sr and sr.manifest:
                cols = [c.name for c in sr.manifest.schema.columns]
                rows = (sr.result.data_array if sr.result else None) or []
    tcols, trows = run_sql(truth)
    lines += [f"## {q}", "", f"**Genie answer:** {text or '(no text)'}", "", "**Genie SQL:**", "```sql", sql or "(none)", "```",
              "**Genie result:**", "", table_md(cols, rows) if cols else "(no table)", "",
              "**Ground truth (certified SQL):**", "```sql", truth, "```", table_md(tcols, trows), "", "---", ""]
    print("  rows:", len(rows), "| first:", rows[:1], "| truth:", trows[:1])

os.makedirs("evidence", exist_ok=True)
open("evidence/08_genie_test_results.md", "w").write("\n".join(lines))
print("wrote evidence/08_genie_test_results.md")
