"""Northbridge Client 360 - Databricks App (Dash).

Account executive: search any client, see the resolved golden record, the legal-entity hierarchy, fee & commission
revenue rolled up to the ultimate parent, placements by line and carrier, and which source systems contributed.
Data steward: review ambiguous matches with the model score and LLM rationale; approve / reject / split decisions are
written to Lakebase and applied by entity resolution on the next run.

Design notes (IBCS-style reporting):
  * every headline states its message; every KPI carries unit, period, comparison and source/freshness;
  * actual = solid navy, prior year = light slate, partial (year-to-date) periods are hatched and labelled;
  * colour encodes meaning only (source system, good/bad variance, LLM recommendation), never decoration;
  * every panel has loading, empty and error states.
"""
import json
import os
import re
from datetime import date, datetime, timezone

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, ctx, dash_table, dcc, html, no_update

import backend as be

# ------------------------------------------------------------------------------------------------
# Visual language
# ------------------------------------------------------------------------------------------------
INK, NAVY, SLATE, MIST = "#1B2733", "#0B2545", "#9AA9BC", "#EEF2F6"
GOOD, BAD, WARN, ACCENT = "#1E7F5C", "#B03A2E", "#B7791F", "#13A89E"
SYSTEM_LABEL = {"NB_CRM": "NB CRM", "NB_BILLING": "NB Billing", "NB_PLACEMENT": "Placement", "HC_AMS": "Harbor & Cole"}
SYSTEM_COLOR = {"NB_CRM": "#2F5D8A", "NB_BILLING": "#5B8DB8", "NB_PLACEMENT": "#6C7A89", "HC_AMS": "#B7791F"}   # H&C = the acquisition
REC_COLOR = {"MERGE": GOOD, "KEEP_SEPARATE": BAD, "NEEDS_MORE_INFO": WARN}
TODAY = date.today()
THIS_FY, LAST_FY = TODAY.year, TODAY.year - 1
CARD = {"className": "shadow-sm border-0 h-100"}

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY], suppress_callback_exceptions=True,
                title="Northbridge Client 360")
server = app.server
app.index_string = app.index_string.replace("</head>", """<style>
body{background:#F7F9FB;color:%s;font-size:14px}
.nb-section{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#6B7A8C;font-weight:600;margin-bottom:6px}
.nb-message{font-size:20px;font-weight:600;color:%s;line-height:1.3}
.nb-kpi-value{font-size:24px;font-weight:700;color:%s;line-height:1.1}
.nb-muted{color:#6B7A8C;font-size:12px}
.nb-pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px;font-weight:600;color:#fff;margin:0 4px 2px 0}
.nb-hit{border:0;border-bottom:1px solid #E6EBF0;cursor:pointer}
.nb-hit:hover{background:#EEF6F6}
.nb-tree ul{list-style:none;padding-left:18px;border-left:1px dashed #C9D3DD;margin:0}
.nb-tree>ul{border-left:0;padding-left:0}
.nb-bar{height:6px;background:%s;border-radius:3px;display:inline-block;vertical-align:middle}
.nb-cmp td{padding:4px 8px;font-size:13px;vertical-align:top}
.nb-cmp th{padding:4px 8px;font-size:11px;color:#6B7A8C;text-transform:uppercase}
.nav-tabs .nav-link.active{font-weight:600}
.nb-genie-md{font-size:13px;line-height:1.5}
.nb-genie-md p{margin:0 0 6px}.nb-genie-md ul,.nb-genie-md ol{margin:0 0 6px;padding-left:18px}
.nb-genie-md table{font-size:12px;border-collapse:collapse;margin:4px 0}.nb-genie-md td,.nb-genie-md th{border-bottom:1px solid #DDE3EA;padding:3px 8px}
</style></head>""" % (INK, NAVY, NAVY, NAVY))


def money(v, digits=2):
    v = float(v or 0)
    if abs(v) >= 1e6:
        return f"${v / 1e6:,.{digits}f}M"
    if abs(v) >= 1e3:
        return f"${v / 1e3:,.0f}K"
    return f"${v:,.0f}"


def pct(a, b):
    return None if not b else (float(a) - float(b)) / float(b)


def delta(a, b, label):
    d = pct(a, b)
    if d is None:
        return html.Span(f"no {label} comparison", className="nb-muted")
    color, arrow = (GOOD, "▲") if d >= 0 else (BAD, "▼")
    return html.Span([html.Span(f"{arrow} {abs(d):.0%}", style={"color": color, "fontWeight": 600}), f" vs {label}"], className="nb-muted")


def pills(systems):
    if isinstance(systems, str):
        systems = json.loads(systems)
    return [html.Span(SYSTEM_LABEL.get(s, s), className="nb-pill", style={"background": SYSTEM_COLOR.get(s, SLATE)}) for s in (systems or [])]


def section(title, *children, right=None):
    return html.Div([html.Div([html.Span(title, className="nb-section"), html.Span(right, className="float-end nb-muted") if right else None]), *children])


def error_alert(what, exc):
    return dbc.Alert([html.Strong(f"Couldn't load {what}. "), html.Span(str(exc)[:300])], color="danger", className="small")


def kpi(label, value, comparison=None, footnote=None):
    return dbc.Card(dbc.CardBody([html.Div(label, className="nb-section"), html.Div(value, className="nb-kpi-value"),
                                  html.Div(comparison, className="mt-1") if comparison is not None else None,
                                  html.Div(footnote, className="nb-muted mt-1") if footnote else None]), **CARD)


# ------------------------------------------------------------------------------------------------
# Layout
# ------------------------------------------------------------------------------------------------
header = dbc.Navbar(dbc.Container([
    html.Div([html.Span("NORTHBRIDGE", style={"fontWeight": 800, "letterSpacing": "3px", "color": "white"}),
              html.Span(" RISK PARTNERS", style={"color": "#9fb3c8", "letterSpacing": "2px"}),
              html.Span("  Client 360", style={"color": "white", "marginLeft": 12, "fontWeight": 300, "fontSize": 18})]),
    dcc.Loading(html.Div(id="whoami", className="text-end small", style={"color": "#dbe6f0"}), type="dot", color="#9fb3c8")], fluid=True),
    color=NAVY, dark=True, className="mb-3 py-2")

EMPTY_CLIENT = dbc.Card(dbc.CardBody([
    html.Div("Find a client", className="nb-message mb-2"),
    html.Div("Search by client, subsidiary, registration number or party id. Results come from the golden record built by "
             "entity resolution across Northbridge CRM, billing, the placement platform and Harbor & Cole.", className="nb-muted mb-3"),
    html.Div(["Try ", html.Code("Kestrel"), " (global client acquired with Harbor & Cole overlap) or ", html.Code("Ironclad"),
              " (Restricted segment: only visible if you are entitled)."], className="small")]), **CARD)

ae_tab = dbc.Container([
    dbc.Row([
        dbc.Col([
            dbc.InputGroup([dbc.Input(id="search", placeholder="Client, subsidiary, reg. number, party id", debounce=True, value="Kestrel"),
                            dbc.Button("Search", id="search-btn", color="primary")], size="sm"),
            dcc.Loading(html.Div(id="search-results", className="mt-2", style={"maxHeight": "78vh", "overflowY": "auto"}), type="dot",
                        target_components={"search-results": "children"}),
        ], md=3),
        dbc.Col(dcc.Loading(html.Div(id="client-view", children=EMPTY_CLIENT), type="default", target_components={"client-view": "children"},
                        delay_show=150), md=9),
    ], className="g-3"),
], fluid=True)

steward_tab = dbc.Container([
    dcc.Loading(html.Div(id="queue-summary", className="mb-2"), type="dot"),
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            section("Match review queue", html.Div("Pairs the match model could not decide (probability 0.30–0.80), each with a "
                                                   "Foundation Model recommendation. Merges the model was sure about never reach this queue.", className="nb-muted mb-2")),
            dcc.Loading(dash_table.DataTable(
                id="queue", row_selectable="single", page_size=14, sort_action="native", filter_action="native",
                columns=[{"name": n, "id": i} for n, i in [("Record A", "left_name"), ("Record B", "right_name"), ("Systems", "systems"),
                                                           ("Model p", "match_score"), ("LLM advice", "llm_recommendation")]],
                style_as_list_view=True,
                style_cell={"fontSize": 12, "textAlign": "left", "whiteSpace": "normal", "height": "auto", "maxWidth": 230, "padding": "6px", "fontFamily": "inherit"},
                style_header={"backgroundColor": MIST, "fontWeight": 600, "fontSize": 11, "textTransform": "uppercase"},
                style_data_conditional=[{"if": {"filter_query": f'{{llm_recommendation}} = "{k}"', "column_id": "llm_recommendation"}, "color": v, "fontWeight": 600}
                                        for k, v in REC_COLOR.items()] + [{"if": {"state": "selected"}, "backgroundColor": "#E3F2F1", "border": "0"}]),
                type="dot"),
        ]), **CARD), md=6),
        dbc.Col([html.Div(id="pair-detail", children=dbc.Card(dbc.CardBody([
            html.Div("Select a pair to review", className="nb-message mb-1"),
            html.Div("You'll see both source records side by side, which fields agree, the model's probability and the LLM's reasoning.", className="nb-muted")]), **CARD)),
            html.Div(id="decision-msg", className="mt-2")], md=6),
    ], className="g-3"),
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([section("Recent steward decisions", html.Div(id="decisions"), right="Lakebase · steward.steward_decisions")]), **CARD), md=7),
        dbc.Col(dbc.Card(dbc.CardBody([
            section("Apply decisions to the golden record",
                    html.Ol([html.Li("Decision row lands in Lakebase"), html.Li("Lakehouse Sync streams it to Unity Catalog (~15 s)"),
                             html.Li("Entity resolution re-clusters with your overrides"), html.Li("Gold rebuilds; Lakebase serving copy refreshes")],
                            className="nb-muted ps-3 mb-2"),
                    dbc.Button("Run entity resolution now", id="run-er", color="success", size="sm"),
                    html.Div(id="er-status", className="mt-2 small"))]), **CARD), md=5),
    ], className="g-3 mt-1"),
    dcc.Store(id="queue-store"), dcc.Interval(id="tick", interval=20_000),
], fluid=True)

footer = html.Div(["Golden records: certified ", html.Code("nb_gold"), " → Lakebase ", html.Code("nb_serving"),
                   " (unrestricted segment). Restricted clients and all Genie answers run as you, so Unity Catalog ABAC policies apply. "
                   "Revenue = fee + commission income (never premium), USD at finance planning rates; fiscal year = calendar year."],
                  className="nb-muted text-center py-3")

def serve_layout():   # a function so it can use components defined further down (Genie panel)
    return html.Div([
    header,
    dbc.Container(dbc.Tabs([dbc.Tab(ae_tab, label="Account executive", tab_id="ae", className="pt-3"),
                            dbc.Tab(steward_tab, label="Data steward", tab_id="steward", className="pt-3")], id="tabs", active_tab="ae"), fluid=True),
    footer, dcc.Store(id="selected-client"), dcc.Store(id="client-ctx"),
    dbc.Button(["✦  Ask Genie"], id="genie-open", color="primary", className="shadow",
               style={"position": "fixed", "right": 28, "bottom": 28, "zIndex": 1050, "borderRadius": 24, "padding": "10px 20px", "fontWeight": 600}),
    dbc.Offcanvas(genie_panel(), id="genie-panel", title="Ask Genie · Northbridge Client 360", placement="end", is_open=False,
                  scrollable=True, backdrop=False, style={"width": 480}),
])





# ------------------------------------------------------------------------------------------------
# Identity / entitlements (shown on every page - the app never hides who a query runs as)
# ------------------------------------------------------------------------------------------------
@app.callback(Output("whoami", "children"), Input("tabs", "active_tab"))
def whoami(_):
    e = be.user_entitlements()
    seg = html.Span("Restricted segment: visible" if e["restricted"] else "Restricted segment: hidden", className="nb-pill",
                    style={"background": BAD if e["restricted"] else SLATE})
    pii = html.Span("Contact PII: visible" if e["pii"] else "Contact PII: masked", className="nb-pill", style={"background": "#4A5868"})
    stw = html.Span("Data steward", className="nb-pill", style={"background": GOOD}) if e.get("steward") else None
    return [html.Span(f"Signed in as {e['user']}", className="me-2"), seg, pii, stw]


# ------------------------------------------------------------------------------------------------
# Account executive view
# ------------------------------------------------------------------------------------------------
@app.callback(Output("search-results", "children"), Input("search-btn", "n_clicks"), Input("search", "value"))
def do_search(_, text):
    if not text or len(text.strip()) < 2:
        return html.Div("Type at least 2 characters.", className="nb-muted p-2")
    try:
        df = be.search_clients(text)
    except Exception as e:
        return error_alert("search results", e)
    if df.empty:
        return html.Div([html.Div("No clients match.", className="fw-semibold"),
                         html.Div("Check spelling, or try a registration number. Restricted clients appear only if you are entitled.", className="nb-muted")], className="p-2")
    df = df.sort_values(["hierarchy_level", "party_name"])
    groups = df[df.hierarchy_level == 0]
    entities = df[df.hierarchy_level > 0]

    def hit(r):
        return dbc.ListGroupItem([
            html.Div([html.Span(r.party_name, className="fw-semibold"),
                      html.Span("RESTRICTED", className="nb-pill ms-1", style={"background": BAD}) if r.is_restricted else None]),
            html.Div(f"{r.country_iso} · {r.client_origin}" + ("" if r.hierarchy_level == 0 else f" · part of {r.ultimate_parent_name}"), className="nb-muted")],
            id={"type": "client-hit", "parent": r.ultimate_parent_party_id, "party": r.party_id, "restricted": bool(r.is_restricted)},
            action=True, n_clicks=0, className="nb-hit px-2 py-2")
    out = [html.Div(f"{len(df)} matches", className="nb-muted px-1 mb-1")]
    if len(groups):
        out += [html.Div("Client groups", className="nb-section px-1 mt-1"), dbc.ListGroup([hit(r) for r in groups.itertuples()], flush=True)]
    if len(entities):
        out += [html.Div("Legal entities", className="nb-section px-1 mt-3"), dbc.ListGroup([hit(r) for r in entities.itertuples()], flush=True)]
    return out


@app.callback(Output("selected-client", "data"), Input({"type": "client-hit", "parent": dash.ALL, "party": dash.ALL, "restricted": dash.ALL}, "n_clicks"),
              prevent_initial_call=True)
def pick(clicks):
    if not ctx.triggered_id or not any(clicks):
        return no_update
    return dict(ctx.triggered_id)


def revenue_figure(by_year):
    """Columns per fiscal year: commission (navy, solid) + fee (accent). The current year is year-to-date: hatched + labelled."""
    years = [int(y) for y in by_year.index]
    labels = [f"FY{y}" + (" YTD" if y == THIS_FY else "") for y in years]   # string categories: bars and labels share one axis
    hatch = ["/" if y == THIS_FY else "" for y in years]
    fig = go.Figure([
        go.Bar(name="Commission", x=labels, y=by_year.commission_income_usd.astype(float), marker=dict(color=NAVY, pattern=dict(shape=hatch, fgcolor="white", solidity=0.35)),
               hovertemplate="%{x} commission: $%{y:,.0f}<extra></extra>"),
        go.Bar(name="Fee", x=labels, y=by_year.fee_income_usd.astype(float), marker=dict(color=ACCENT, pattern=dict(shape=hatch, fgcolor="white", solidity=0.35)),
               hovertemplate="%{x} fee: $%{y:,.0f}<extra></extra>"),
    ])
    totals = by_year.total_revenue_usd.astype(float)
    for lab, tot in zip(labels, totals):
        fig.add_annotation(x=lab, y=tot, text=f"<b>{money(tot)}</b>", showarrow=False, yanchor="bottom", yshift=4, font=dict(size=11, color=INK))
    fig.update_layout(barmode="stack", height=270, margin=dict(l=0, r=0, t=30, b=0), plot_bgcolor="white", paper_bgcolor="white",
                      legend=dict(orientation="h", y=1.14, x=0, font=dict(size=11), traceorder="normal"), bargap=0.4,
                      yaxis=dict(visible=False, range=[0, max(totals.max(), 1) * 1.18]),
                      xaxis=dict(type="category", categoryorder="array", categoryarray=labels, tickfont=dict(size=11)))
    return fig


def lob_figure(in_force):
    g = (in_force.groupby("line_of_business").agg(placements=("placement_id", "count"), carriers=("carrier_name", "nunique"))
         .sort_values("placements"))
    fig = go.Figure(go.Bar(x=g.placements, y=g.index, orientation="h", marker_color=NAVY,
                           text=[f"{p} · {c} carrier{'s' if c > 1 else ''}" for p, c in zip(g.placements, g.carriers)],
                           textposition="outside", cliponaxis=False))
    fig.update_layout(height=max(160, 28 * len(g) + 30), margin=dict(l=0, r=90, t=4, b=0), plot_bgcolor="white", paper_bgcolor="white",
                      xaxis=dict(visible=False), yaxis=dict(tickfont=dict(size=11)))
    return fig


def hierarchy_tree(parties, revenue, focus):
    rev = revenue[revenue.fiscal_year == LAST_FY].groupby("party_id")["total_revenue_usd"].sum().to_dict() if len(revenue) else {}
    peak = max(rev.values()) if rev else 1
    kids = {}
    for r in parties.itertuples():
        kids.setdefault(r.parent_party_id if isinstance(r.parent_party_id, str) else None, []).append(r)

    def node(r):
        v = rev.get(r.party_id, 0)
        line = html.Div([
            html.Div([html.Span(r.party_name, style={"fontWeight": 600 if r.hierarchy_level == 0 else 400}),
                      html.Span(f" {r.country_iso}", className="nb-muted"), html.Span(pills(r.source_systems), className="ms-1")]),
            html.Div([html.Span(className="nb-bar me-2", style={"width": f"{max(2, 90 * v / peak):.0f}px"}),
                      html.Span(money(v) if v else "no FY revenue", className="nb-muted")])],
            style={"padding": "3px 6px", "borderRadius": 4, **({"background": "#E3F2F1"} if r.party_id == focus else {})})
        children = sorted(kids.get(r.party_id, []), key=lambda x: -rev.get(x.party_id, 0))
        return html.Li([line, html.Ul([node(c) for c in children])] if children else [line])

    return html.Div(html.Ul([node(r) for r in parties.itertuples() if r.hierarchy_level == 0]), className="nb-tree")


@app.callback(Output("client-view", "children"), Output("client-ctx", "data"), Input("selected-client", "data"), prevent_initial_call=True)
def client_view(sel):
    try:
        fam = be.client_family(sel["parent"], sel["restricted"])
    except Exception as e:
        return error_alert("this client", e), None
    parties, revenue, placements, xref = fam["parties"], fam["revenue"], fam["placements"], fam["xref"]
    if parties.empty:
        return dbc.Alert("No data is visible for this client with your entitlements. It may be in the Restricted segment.", color="warning"), None
    top = parties[parties.party_id == sel["parent"]].iloc[0]
    focus = parties[parties.party_id == sel["party"]].iloc[0]
    by_year = revenue.groupby("fiscal_year")[["commission_income_usd", "fee_income_usd", "total_revenue_usd"]].sum().sort_index()
    get = lambda fy, col: float(by_year.loc[fy, col]) if fy in by_year.index else 0.0
    ly, py, ytd = get(LAST_FY, "total_revenue_usd"), get(LAST_FY - 1, "total_revenue_usd"), get(THIS_FY, "total_revenue_usd")
    fee_share = get(LAST_FY, "fee_income_usd") / ly if ly else 0
    in_force = placements[pd.to_datetime(placements.expiry_date) >= pd.Timestamp(TODAY)] if len(placements) else placements
    systems = sorted(set(xref.source_system)) if len(xref) else []
    source = "Certified gold, queried as you (Restricted segment)" if sel["restricted"] else "Lakebase serving copy of certified gold"
    refreshed = None
    if "golden_record_refreshed_at" in parties.columns and parties.golden_record_refreshed_at.notna().any():
        refreshed = pd.to_datetime(parties.golden_record_refreshed_at).max()
    provenance = f"{source}" + (f" · refreshed {refreshed:%d %b %H:%M} UTC" if refreshed is not None else "")

    d = pct(ly, py)
    trend_word = "no prior-year comparison" if d is None else (f"up {d:.0%}" if d >= 0 else f"down {abs(d):.0%}") + f" on FY{LAST_FY - 1}"
    headline = html.Div([
        html.Div([html.Span(top.party_name), html.Span("RESTRICTED", className="nb-pill ms-2 align-middle", style={"background": BAD}) if sel["restricted"] else None],
                 className="nb-section", style={"fontSize": 12}),
        html.Div(f"{money(ly)} fee & commission income in FY{LAST_FY}, {trend_word}, across {len(parties)} legal entities "
                 f"unified from {len(xref)} source records in {len(systems)} systems.", className="nb-message"),
        html.Div(provenance, className="nb-muted mt-1")], className="mb-3")

    focus_card = dbc.Card(dbc.CardBody([
        section("Golden record" + ("" if focus.party_id == top.party_id else " · selected entity"), right=focus.party_id),
        html.Div(focus.party_name, className="fw-bold", style={"fontSize": 17, "color": NAVY}),
        html.Div(f"{focus.country_iso} · Reg. {focus.registration_number or 'not on file'}", className="small"),
        html.Div(f"{focus.industry or 'Industry n/a'} · {focus.client_segment or 'Unassigned'} · AE {focus.account_executive or 'unassigned'}", className="nb-muted"),
        html.Hr(className="my-2"),
        html.Div([html.Span(f"{int(focus.source_record_count)} source records  ", className="small"), *pills(focus.source_systems)]),
        html.Div("Client of both Northbridge and Harbor & Cole before the acquisition" if focus.client_origin == "Both" else f"Origin: {focus.client_origin}",
                 className="nb-muted mt-1"),
        html.Div(f"Weakest merge confidence {float(focus.min_match_confidence):.2f}" + (" · steward override applied" if bool(focus.has_steward_override) else ""),
                 className="nb-muted"),
    ]), **CARD)

    kpis = dbc.Row([
        dbc.Col(kpi(f"FY{LAST_FY} revenue", money(ly), delta(ly, py, f"FY{LAST_FY - 1}"), "fee + commission, all entities"), md=6, lg=3),
        dbc.Col(kpi(f"FY{THIS_FY} year to date", money(ytd), html.Span(f"partial year through {TODAY:%d %b}; not comparable to full years", className="nb-muted"),
                    None), md=6, lg=3),
        dbc.Col(kpi("Revenue mix", f"{fee_share:.0%} fee", html.Span(f"{1 - fee_share:.0%} commission, FY{LAST_FY}", className="nb-muted")), md=6, lg=3),
        dbc.Col(kpi("In-force programme", f"{len(in_force)} placements",
                    html.Span(f"{in_force.carrier_name.nunique() if len(in_force) else 0} carriers · {in_force.line_of_business.nunique() if len(in_force) else 0} lines", className="nb-muted")), md=6, lg=3),
    ], className="g-3")

    if len(in_force):
        top_carrier = in_force.carrier_name.value_counts()
        conc = f"Largest carrier {top_carrier.index[0]} holds {top_carrier.iloc[0] / len(in_force):.0%} of in-force placements"
        lob_panel = dcc.Graph(figure=lob_figure(in_force), config={"displayModeBar": False})
    else:
        conc, lob_panel = "No in-force placements", html.Div("No placements currently in force for this client.", className="nb-muted p-3")

    lineage = dash_table.DataTable(
        data=xref.sort_values(["party_id", "source_system"]).assign(match_confidence=lambda d: pd.to_numeric(d.match_confidence).round(2))
             [["source_system", "source_record_id", "source_name", "match_method", "match_confidence"]].to_dict("records"),
        columns=[{"name": n, "id": i} for n, i in [("System", "source_system"), ("Record id", "source_record_id"), ("Name as held in source", "source_name"),
                                                  ("Method", "match_method"), ("Confidence", "match_confidence")]],
        page_size=8, style_as_list_view=True, sort_action="native",
        style_cell={"fontSize": 12, "textAlign": "left", "padding": "5px", "fontFamily": "inherit"},
        style_header={"backgroundColor": MIST, "fontWeight": 600, "fontSize": 11, "textTransform": "uppercase"},
        style_data_conditional=[{"if": {"filter_query": f'{{source_system}} = "{k}"', "column_id": "source_system"}, "color": v, "fontWeight": 600}
                                for k, v in SYSTEM_COLOR.items()])

    return html.Div([
        headline,
        dbc.Row([dbc.Col(focus_card, lg=4), dbc.Col(kpis, lg=8)], className="g-3"),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([section(f"Revenue by fiscal year · rolled up to {top.party_name}", right="USD · FY = calendar year"),
                                           html.Div([html.Span(f"FY{LAST_FY}: {money(ly)} ({trend_word}). FY{THIS_FY} is year to date (hatched). "),
                                                     dbc.Button(f"Tie out FY{LAST_FY} to the certified metric view", id="verify-btn", color="link", size="sm", className="p-0 align-baseline")],
                                                    className="small mb-1"),
                                           dcc.Loading(html.Div(id="verify-result"), type="dot"),
                                           dcc.Store(id="verify-ctx", data={"parent": sel["parent"], "fy": LAST_FY, "app_value": ly}),
                                           dcc.Graph(figure=revenue_figure(by_year), config={"displayModeBar": False}) if len(by_year)
                                           else html.Div("No fee or commission income recorded.", className="nb-muted p-3")]), **CARD), lg=7),
            dbc.Col(dbc.Card(dbc.CardBody([section(f"Legal-entity hierarchy · FY{LAST_FY} revenue per entity", right=f"{len(parties)} entities"),
                                           html.Div(hierarchy_tree(parties, revenue, focus.party_id), style={"maxHeight": 330, "overflowY": "auto"})]), **CARD), lg=5),
        ], className="g-3 mt-1"),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([section("In-force placements by line of business", right=f"{len(in_force)} placements"),
                                           html.Div(conc, className="small mb-1"), lob_panel]), **CARD), lg=5),
            dbc.Col(dbc.Card(dbc.CardBody([section("Where this golden record came from", right=f"{len(xref)} records · {len(systems)} systems"),
                                           html.Div(pills(systems), className="mb-2"), lineage]), **CARD), lg=7),
        ], className="g-3 mt-1"),
    ]), {"name": top.party_name, "parent": sel["parent"], "restricted": sel["restricted"]}


MONEY_COL = re.compile(r"(usd|revenue|income|commission|fee|premium|gwp|amount)", re.I)
COUNT_COL = re.compile(r"(count|records|parties|placements|entities|pairs|merged)$", re.I)


def humanize(col):
    c = re.sub(r"_usd$", " (USD)", col.replace("`", ""))
    c = c.replace("_", " ").strip()
    return c[:1].upper() + c[1:]


def fmt_cell(col, v):
    if v is None or v == "":
        return "–"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if MONEY_COL.search(col):
        return f"${f:,.2f}"
    if COUNT_COL.search(col) or f.is_integer():
        return f"{f:,.0f}" if "year" not in col.lower() else f"{f:.0f}"
    return f"{f:,.2f}" if abs(f) >= 1 else f"{f:.4f}"


def genie_result(df):
    """Render a Genie result: one row -> stat tiles, many rows -> a tidy table. Id columns are hidden."""
    df = df[[c for c in df.columns if not re.search(r"(_id|party_id)$", c, re.I)]]
    if len(df) == 1 and len(df.columns) <= 8:
        row = df.iloc[0]
        labels = [c for c in df.columns if not MONEY_COL.search(c) and not COUNT_COL.search(c)]
        context = " · ".join(fmt_cell(c, row[c]) for c in labels)
        tiles = [dbc.Col(html.Div([html.Div(humanize(c), className="nb-section"),
                                   html.Div(fmt_cell(c, row[c]), className="nb-kpi-value", style={"fontSize": 20})],
                                  className="p-2", style={"background": MIST, "borderRadius": 6}), xs=6, md=3)
                 for c in df.columns if c not in labels]
        return html.Div([html.Div(context, className="fw-semibold mb-2") if context else None, dbc.Row(tiles, className="g-2")])
    cols = list(df.columns)
    data = [{c: fmt_cell(c, r[c]) for c in cols} for _, r in df.head(25).iterrows()]
    return html.Div([dash_table.DataTable(
        data=data, columns=[{"name": humanize(c), "id": c} for c in cols], style_as_list_view=True, page_size=10,
        style_table={"overflowX": "auto"},
        style_cell={"fontSize": 12, "textAlign": "left", "fontFamily": "inherit", "padding": "6px", "whiteSpace": "normal", "height": "auto", "minWidth": 90},
        style_cell_conditional=[{"if": {"column_id": c}, "textAlign": "right"} for c in cols if MONEY_COL.search(c) or COUNT_COL.search(c)],
        style_header={"backgroundColor": MIST, "fontWeight": 600, "fontSize": 11, "textTransform": "uppercase"}),
        html.Div(f"Showing {min(25, len(df))} of {len(df)} rows", className="nb-muted mt-1") if len(df) > 10 else None])



@app.callback(Output("verify-result", "children"), Input("verify-btn", "n_clicks"), State("verify-ctx", "data"), prevent_initial_call=True)
def verify(_, vctx):
    try:
        mv = be.metric_view_total(vctx["parent"], vctx["fy"])
    except Exception as e:
        return error_alert("the metric view", e)
    ok = abs(mv - vctx["app_value"]) < 0.005
    return dbc.Alert([html.Span(f"Certified metric view FY{vctx['fy']}: ${mv:,.2f} · this page: ${vctx['app_value']:,.2f} · "),
                      html.Strong("matches to the cent" if ok else "MISMATCH: investigate before using this number")],
                     color="success" if ok else "danger", className="py-1 px-2 mb-1 small")


# ------------------------------------------------------------------------------------------------
# Genie: floating side panel (lives outside the client view, so asking never re-renders the page)
# ------------------------------------------------------------------------------------------------
GENERAL_QS = ["Which acquired Harbor & Cole clients overlap with existing Northbridge clients?",
              "Top 10 clients by commission income this year, rolled up to parent",
              "Which clients have placements with more than three carriers?",
              "How many party records were merged by the entity resolution model last run?"]


def genie_panel():
    return html.Div([
        html.Div(id="genie-context", className="nb-muted mb-2"),
        html.Div(id="genie-suggest", className="mb-2"),
        html.Div(id="genie-thread", style={"minHeight": 60}),
        html.Div([dbc.InputGroup([dbc.Input(id="genie-q", placeholder="Ask about clients, revenue, placements...", debounce=False, n_submit=0),
                                  dbc.Button("Ask", id="genie-btn", color="primary")], size="sm"),
                  html.Div([html.Span("Runs as you: Unity Catalog policies decide what Genie can see. "),
                            dbc.Button("New conversation", id="genie-reset", color="link", size="sm", className="p-0 align-baseline")],
                           className="nb-muted mt-1")],
                 style={"position": "sticky", "bottom": 0, "background": "white", "paddingTop": 8}),
        dcc.Store(id="genie-history", data=[]), dcc.Store(id="genie-conv"),
    ])


@app.callback(Output("genie-panel", "is_open"), Input("genie-open", "n_clicks"), State("genie-panel", "is_open"), prevent_initial_call=True)
def toggle_genie(_, is_open):
    return not is_open


@app.callback(Output("genie-context", "children"), Output("genie-suggest", "children"), Input("client-ctx", "data"))
def genie_context(c):
    qs = ([f"What's our total revenue with {c['name']} across all entities in FY{LAST_FY}?",
           f"Which carriers hold {c['name']}'s in-force placements, by line of business?"] if c else []) + GENERAL_QS[:3]
    ctx_line = (f"Context: {c['name']}" + (" (Restricted)" if c.get("restricted") else "")) if c else "Ask anything about the certified Client 360 data."
    chips = [dbc.Button(q, id={"type": "genie-chip", "i": i}, color="light", size="sm", className="me-1 mb-1 text-start",
                        style={"fontSize": 12, "whiteSpace": "normal"}) for i, q in enumerate(qs)]
    return ctx_line, chips


@app.callback(Output("genie-history", "data"), Output("genie-q", "value"), Output("genie-conv", "data"),
              Input("genie-btn", "n_clicks"), Input("genie-q", "n_submit"), Input({"type": "genie-chip", "i": dash.ALL}, "n_clicks"),
              Input("genie-reset", "n_clicks"),
              State("genie-q", "value"), State("genie-suggest", "children"), State("genie-history", "data"),
              prevent_initial_call=True)
def ask_submit(_b, _s, chips, _r, typed, suggest, history):
    """Step 1 (instant): show the question with a 'thinking' placeholder. Step 2 (ask_run) calls Genie."""
    trig = ctx.triggered_id
    if trig == "genie-reset":
        return [], "", None
    if isinstance(trig, dict):   # a suggestion chip
        if not ctx.triggered or not ctx.triggered[0]["value"]:
            return no_update, no_update, no_update
        question = suggest[trig["i"]]["props"]["children"]
    else:
        question = (typed or "").strip()
    history = history or []
    if not question or (history and history[-1].get("pending")):
        return no_update, no_update, no_update
    return history + [{"q": question, "pending": True}], "", no_update


@app.callback(Output("genie-history", "data", allow_duplicate=True), Output("genie-conv", "data", allow_duplicate=True),
              Input("genie-history", "data"), State("genie-conv", "data"), prevent_initial_call=True)
def ask_run(history, conv):
    if not history or not history[-1].get("pending"):
        return no_update, no_update
    question = history[-1]["q"]
    try:
        a = be.ask_genie(question, conv)
        entry = {"q": question, **{k: a[k] for k in ("text", "sql", "columns", "rows", "conversation_url")}}
        conv = a["conversation_id"]
    except Exception as e:
        entry = {"q": question, "error": str(e)[:300]}
    return history[:-1] + [entry], conv


@app.callback(Output("genie-thread", "children"), Input("genie-history", "data"))
def render_thread(history):
    if not history:
        return html.Div("Pick a suggested question or type your own. Follow-ups stay in the same Genie conversation.", className="nb-muted")
    out = []
    for h in history:
        out.append(html.Div(h["q"], className="ms-auto mb-2 px-3 py-2",
                            style={"background": NAVY, "color": "white", "borderRadius": "12px 12px 2px 12px", "maxWidth": "88%", "width": "fit-content", "fontSize": 13}))
        if h.get("pending"):
            body = [html.Div([dbc.Spinner(size="sm", color="secondary", spinner_class_name="me-2"),
                              html.Span("Genie is writing and running a query against certified gold… usually 10–30 seconds.", className="nb-muted")])]
        elif h.get("error"):
            body = [dbc.Alert(f"Genie couldn't answer: {h['error']}", color="warning", className="py-2 mb-0 small")]
        elif not h.get("text") and not h.get("rows"):
            body = [html.Div("Genie couldn't answer that. Try naming the client, the measure and the fiscal year.", className="small")]
        else:
            body = [dcc.Markdown(h["text"], className="mb-1 nb-genie-md") if h.get("text") else None]
            if h.get("rows"):
                body.append(genie_result(pd.DataFrame(h["rows"], columns=h["columns"])))
            if h.get("sql"):
                body.append(html.Details([html.Summary("Show the SQL Genie ran", className="nb-muted mt-2", style={"cursor": "pointer"}),
                                          html.Pre(h["sql"], style={"fontSize": 10.5, "whiteSpace": "pre-wrap", "background": MIST, "padding": 8, "borderRadius": 4})]))
            body.append(html.Div(["AI-generated from certified gold · ", html.A("open in Genie ↗", href=h.get("conversation_url"), target="_blank")], className="nb-muted mt-1"))
        out.append(html.Div(body, className="mb-3 p-2", style={"background": MIST, "borderRadius": "12px 12px 12px 2px", "maxWidth": "100%"}))
    return out


# ------------------------------------------------------------------------------------------------
# Data steward view
# ------------------------------------------------------------------------------------------------
@app.callback(Output("queue", "data"), Output("queue-store", "data"), Output("queue-summary", "children"),
              Input("tabs", "active_tab"), Input("decision-msg", "children"))
def load_queue(tab, _):
    if tab != "steward":
        return no_update, no_update, no_update
    try:
        q = be.review_queue()
    except Exception as e:
        return [], [], error_alert("the review queue", e)
    if q.empty:
        return [], [], dbc.Alert("The review queue is empty: every ambiguous pair has a steward decision. Run entity resolution to apply them.", color="success", className="py-2")
    q["match_score"] = q["match_score"].astype(float).round(2)
    q["systems"] = q.left_source_system.map(SYSTEM_LABEL) + " / " + q.right_source_system.map(SYSTEM_LABEL)
    counts = q.llm_recommendation.value_counts()
    summary = html.Div([
        html.Span(f"{len(q)} pairs awaiting review", className="nb-message me-3", style={"fontSize": 16}),
        *[html.Span(f"{counts.get(k, 0)} {k.replace('_', ' ').lower()}", className="nb-pill", style={"background": v}) for k, v in REC_COLOR.items()],
        html.Span("  LLM advice is a recommendation; the steward decides.", className="nb-muted ms-2")])
    q["id"] = q["pair_id"]   # DataTable row id -> selected_row_ids stays correct after sort/filter
    return q[["id", "pair_id", "left_name", "right_name", "systems", "match_score", "llm_recommendation"]].to_dict("records"), q.to_dict("records"), summary


def _norm(v):
    return re.sub(r"[^A-Z0-9]", "", str(v or "").upper())


def compare(a, b, kind="text"):
    if not a or not b or str(a) in ("None", "nan") or str(b) in ("None", "nan"):
        return ("–", "missing on one side", SLATE)
    na, nb_ = _norm(a), _norm(b)
    if na == nb_:
        return ("✓", "same", GOOD)
    if kind == "reg" and len(na) == len(nb_) and sorted(na) == sorted(nb_):
        return ("≈", "same digits, transposed", WARN)
    ta, tb = set(re.findall(r"[A-Z0-9]+", str(a).upper())), set(re.findall(r"[A-Z0-9]+", str(b).upper()))
    if kind == "text" and ta and tb and len(ta & tb) / max(len(ta), len(tb)) >= 0.6:
        return ("≈", "similar", WARN)
    return ("✗", "differs", BAD)


@app.callback(Output("pair-detail", "children"), Input("queue", "selected_row_ids"), State("queue-store", "data"))
def pair_detail(ids, store):
    if not ids or not store:
        return no_update
    pid = ids[0]
    p = next((x for x in store if x["pair_id"] == pid), None)
    if p is None:
        return no_update
    fields = [("Source", SYSTEM_LABEL.get(p["left_source_system"]), SYSTEM_LABEL.get(p["right_source_system"]), None),
              ("Name", p["left_name"], p["right_name"], "text"), ("Country", p["left_country"], p["right_country"], "text"),
              ("Registration", p["left_registration"], p["right_registration"], "reg"), ("Address", p["left_address"], p["right_address"], "text"),
              ("Golden party now", p["left_party_id"], p["right_party_id"], "text")]
    rows_html = []
    for label, a, b, kind in fields:
        sym, why, col = compare(a, b, kind) if kind else ("", "", INK)
        rows_html.append(html.Tr([html.Th(label), html.Td(a or html.Span("missing", className="nb-muted")), html.Td(b or html.Span("missing", className="nb-muted")),
                                  html.Td(html.Span([html.B(sym, style={"color": col}), html.Span(f" {why}", className="nb-muted")]) if kind else "")]))
    score = float(p["match_score"])
    rec = p["llm_recommendation"]
    return dbc.Card(dbc.CardBody([
        section("Candidate match", right=f"pair {pid}"),
        html.Table([html.Thead(html.Tr([html.Th(""), html.Th("Record A"), html.Th("Record B"), html.Th("Agreement")])), html.Tbody(rows_html)],
                   className="table table-sm nb-cmp mb-2"),
        html.Div([html.Span("Match model probability ", className="nb-section"), html.Span(f"{score:.2f}", className="fw-bold"),
                  html.Span("  review band 0.30 – 0.80 (auto-merge at 0.80)", className="nb-muted")]),
        html.Div(html.Div(style={"width": f"{score * 100:.0f}%", "height": 8, "background": NAVY, "borderRadius": 4}),
                 style={"background": MIST, "borderRadius": 4, "position": "relative"}, className="mb-1"),
        html.Div([html.Div(style={"position": "absolute", "left": "30%", "top": -12, "height": 12, "borderLeft": f"2px solid {SLATE}"}),
                  html.Div(style={"position": "absolute", "left": "80%", "top": -12, "height": 12, "borderLeft": f"2px solid {GOOD}"})],
                 style={"position": "relative", "height": 2}),
        html.Div([html.Div([html.Span(rec.replace("_", " "), className="nb-pill", style={"background": REC_COLOR.get(rec, SLATE)}),
                            html.Span(f"{p['llm_confidence']} confidence · {p['llm_endpoint']}", className="nb-muted")]),
                  html.Div(p["llm_rationale"], className="small mt-1"),
                  html.Div("AI-generated recommendation. You make the decision.", className="nb-muted mt-1")],
                 className="p-2 mt-3", style={"background": MIST, "borderLeft": f"4px solid {REC_COLOR.get(rec, SLATE)}", "borderRadius": 4}),
        dbc.Textarea(id="rationale", placeholder="Your rationale (stored with the decision and visible in the audit trail)", rows=2, className="mt-3"),
        dbc.ButtonGroup([dbc.Button("Approve merge", id="d-approve", color="success"),
                         dbc.Button("Keep separate", id="d-reject", color="danger", outline=True),
                         dbc.Button("Split record B out", id="d-split", color="secondary", outline=True)], className="mt-2", size="sm"),
        dcc.Store(id="pair-ctx", data=p),
    ]), **CARD)


@app.callback(Output("decision-msg", "children"), Input("d-approve", "n_clicks"), Input("d-reject", "n_clicks"), Input("d-split", "n_clicks"),
              State("pair-ctx", "data"), State("rationale", "value"), prevent_initial_call=True)
def decide(a, r, s, pair, rationale):
    if not ctx.triggered_id or not (a or r or s):
        return no_update
    decision = {"d-approve": "approve_merge", "d-reject": "reject", "d-split": "split"}[ctx.triggered_id]
    if not be.user_entitlements().get("steward"):
        return dbc.Alert(f"Only members of {be.STEWARD_GROUP} can record match decisions. Nothing was saved.", color="warning", className="py-2")
    try:
        did = be.record_decision(pair, decision, rationale)
    except Exception as e:
        return error_alert("your decision (nothing was saved)", e)
    return dbc.Alert(f"Recorded '{decision.replace('_', ' ')}' for {pair['left_name']} / {pair['right_name']} (decision {did[:8]}). "
                     "It's in Lakebase now and reaches Unity Catalog within seconds; run entity resolution to apply it.", color="success", dismissable=True, className="py-2")


@app.callback(Output("decisions", "children"), Input("tabs", "active_tab"), Input("decision-msg", "children"), Input("tick", "n_intervals"))
def decisions(tab, *_):
    if tab != "steward":
        return no_update
    try:
        d = be.recent_decisions()
    except Exception as e:
        return error_alert("recent decisions", e)
    if d.empty:
        return html.Div("No decisions yet. Pick a pair from the queue to start.", className="nb-muted")
    d["decided_at"] = pd.to_datetime(d.decided_at).dt.strftime("%d %b %H:%M")
    return dash_table.DataTable(data=d.to_dict("records"), columns=[{"name": c.replace("_", " "), "id": c} for c in d.columns],
                                style_as_list_view=True, page_size=8,
                                style_cell={"fontSize": 12, "textAlign": "left", "fontFamily": "inherit", "whiteSpace": "normal", "height": "auto"},
                                style_header={"backgroundColor": MIST, "fontWeight": 600, "fontSize": 11, "textTransform": "uppercase"})


@app.callback(Output("er-status", "children"), Input("run-er", "n_clicks"), Input("tick", "n_intervals"), State("tabs", "active_tab"))
def er_status(clicks, _, tab):
    if tab != "steward":
        return no_update
    try:
        note = None
        if ctx.triggered_id == "run-er" and clicks:
            if not be.user_entitlements().get("steward"):
                note = dbc.Alert(f"Only members of {be.STEWARD_GROUP} can run entity resolution.", color="warning", className="py-2 mb-2")
            else:
                started, why = be.run_roundtrip()
                note = None if started else dbc.Alert(why, color="info", className="py-2 mb-2")
        r = be.last_roundtrip()
    except Exception as e:
        return error_alert("job status", e)
    if not r:
        return [note, html.Span("No entity resolution runs yet.", className="nb-muted")]
    color = {"SUCCESS": GOOD, "FAILED": BAD}.get(r["state"], WARN)
    return html.Div([note, html.Span(f"Last run {r['start']:%d %b %H:%M} UTC ", className="nb-muted"),
                     html.Span(r["state"], className="nb-pill", style={"background": color}), html.A(" open run", href=r["url"], target="_blank")])


@server.route("/api/selftest")
def selftest():
    """Exercises every backend path for a client name (default Kestrel) and returns JSON - used as run evidence."""
    import time as _t
    from flask import jsonify, request as rq
    name = rq.args.get("client", "Kestrel Industries plc")
    out, t0 = {}, _t.time()
    out["entitlements"] = be.user_entitlements()
    hits = be.search_clients(name)
    out["search"] = {"query": name, "hits": len(hits), "restricted_hits": int(hits.is_restricted.sum()) if len(hits) else 0,
                     "top": hits.head(5)[["party_id", "party_name", "country_iso", "hierarchy_level", "is_restricted"]].to_dict("records"),
                     "ms": round((_t.time() - t0) * 1000)}
    exact = hits[hits.party_name == name]
    if len(exact):
        row = exact.iloc[0]
        t1 = _t.time()
        fam = be.client_family(row.ultimate_parent_party_id, bool(row.is_restricted))
        rev = fam["revenue"].groupby("fiscal_year")["total_revenue_usd"].sum().round(2)
        out["client_view"] = {"source": "UC gold (on behalf of user)" if row.is_restricted else "Lakebase", "ms": round((_t.time() - t1) * 1000),
                              "legal_entities": len(fam["parties"]), "source_records": len(fam["xref"]),
                              "source_systems": sorted(set(fam["xref"].source_system)), "placements": len(fam["placements"]),
                              "revenue_by_fiscal_year_usd": {int(k): float(v) for k, v in rev.items()},
                              "hierarchy": fam["parties"].sort_values(["hierarchy_level", "party_name"])[["party_id", "party_name", "country_iso", "hierarchy_level", "parent_party_id"]].to_dict("records")}
        try:
            mv = be.metric_view_total(row.ultimate_parent_party_id, LAST_FY)
            out["metric_view_check"] = {"fiscal_year": LAST_FY, "metric_view_usd": round(mv, 2), "app_usd": float(rev.get(LAST_FY, 0)),
                                        "matches_to_the_cent": abs(mv - float(rev.get(LAST_FY, 0))) < 0.005}
        except Exception as e:
            out["metric_view_check"] = {"error": str(e)[:200]}
    q = be.review_queue()
    out["steward_queue"] = {"pending_pairs": len(q), "by_llm_recommendation": q.llm_recommendation.value_counts().to_dict() if len(q) else {}}
    out["recent_decisions"] = len(be.recent_decisions())
    out["genie_space_url"] = be.genie_space_url()
    return jsonify(out)


app.layout = serve_layout

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("DATABRICKS_APP_PORT", "8000")), debug=False)
