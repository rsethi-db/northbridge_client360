# Notebook run: f5c49ef0-d270-4fcd-b767-df1b9707f724

```markdown
%md
# 11 · Resolve parties → golden `party_id` + legal-entity hierarchy

1. Score every candidate pair with the `champion` match model.
2. Apply **steward decisions** written back from the Client 360 app (Lakebase → Lakehouse Sync → `app.lb_steward_decisions_history`):
   `approve_merge` adds an edge, `reject` removes one, `split` detaches a record from its cluster.
3. Cluster (connected components) → golden parties. `party_id`s are **stable**: a cluster keeps the id most of
   its records had last run; brand-new clusters get a deterministic hash id.
4. Derive the **legal-entity hierarchy** from the registry feed (direct parent registration number), falling back
   to explicit CRM parent-account links.
5. Append a run summary to `ml.er_run_log`.
```

```python
%pip install -q rapidfuzz==3.9.7 "mlflow>=3.1" scikit-learn==1.5.2
%restart_python
```
**Output:**
```
Note: you may need to restart the kernel using %restart_python or dbutils.library.restartPython() to use updated packages.
```

```python
dbutils.widgets.text("catalog", "richasethi_febar_catalog")
dbutils.widgets.text("schema_prefix", "nb_")
CATALOG, P = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema_prefix")
ML, SILVER, APP = f"{CATALOG}.{P}ml", f"{CATALOG}.{P}silver", f"{CATALOG}.{P}app"
MODEL_NAME = f"{ML}.party_match_model"
AUTO_MATCH, REVIEW_FLOOR = 0.80, 0.30
```

```python
import hashlib, json, uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone

import mlflow
import pandas as pd
from mlflow import MlflowClient

from er_features import FEATURES, UnionFind, candidate_pairs_sql, featurize, pair_id

mlflow.set_registry_uri("databricks-uc")
mv = MlflowClient().get_model_version_by_alias(MODEL_NAME, "champion")
model = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}@champion")

records = spark.table(f"{SILVER}.party_source_records").toPandas()
records["record_key"] = records.source_system + ":" + records.source_record_id
pairs = spark.sql(candidate_pairs_sql(f"{SILVER}.party_source_records")).toPandas()
X = featurize(pairs)
pairs["match_score"] = model.predict_proba(X)[:, 1]
pairs["pair_id"] = [pair_id(a, b) for a, b in zip(pairs.key_l, pairs.key_r)]
pairs["match_band"] = pd.cut(pairs.match_score, [-1, REVIEW_FLOOR, AUTO_MATCH, 2], labels=["no_match", "review", "auto_match"], right=False).astype(str)
print(pairs.match_band.value_counts())
```
**Output:**
```
match_band
no_match      33026
auto_match     3610
review           51
Name: count, dtype: int64
```

```markdown
%md ## Steward decisions (latest decision per pair wins)
```

```python
# Steward decisions are written by the Client 360 app to Lakebase (steward.steward_decisions) and land in the lakehouse
# through Lakebase Lakehouse Sync as an SCD2 change history: app.lb_steward_decisions_history.
HISTORY = f"{APP}.lb_steward_decisions_history"
if spark.catalog.tableExists(HISTORY):
    spark.sql(f"""CREATE OR REPLACE VIEW {APP}.steward_decisions_current
      COMMENT 'Current steward match-review decisions (approve_merge | reject | split), latest version per decision_id from the Lakebase change history. Applied as overrides by entity resolution.'
      AS SELECT decision_id, pair_id, left_record_key, right_record_key, decision, steward, rationale, decided_at
         FROM {HISTORY}
         QUALIFY row_number() OVER (PARTITION BY decision_id ORDER BY _sort_by DESC) = 1 AND _pg_change_type <> 'delete'""")
    dec = spark.sql(f"""SELECT * FROM {APP}.steward_decisions_current
                       QUALIFY row_number() OVER (PARTITION BY coalesce(pair_id, left_record_key) ORDER BY decided_at DESC) = 1""").toPandas()
else:
    print(f"{HISTORY} not found yet (no Lakebase write-back configured) - no steward overrides")
    dec = pd.DataFrame(columns=["decision_id", "pair_id", "left_record_key", "right_record_key", "decision", "steward", "rationale", "decided_at"])
approve = {(r.left_record_key, r.right_record_key) for r in dec.itertuples() if r.decision == "approve_merge"}
reject = {tuple(sorted((r.left_record_key, r.right_record_key))) for r in dec.itertuples() if r.decision == "reject"}
split = {r.left_record_key for r in dec.itertuples() if r.decision == "split"}
```
**Output:**
```
richasethi_febar_catalog.nb_app.lb_steward_decisions_history not found yet (no Lakebase write-back configured) - no steward overrides
```

```python
# Cannot-link constraints stop transitive chains (A~B, B~C) from fusing different legal entities:
# a golden party may hold only one country and no two registration numbers that differ by more than a typo.
from rapidfuzz.distance import OSA

keys = records.record_key.tolist()
uf = UnionFind(keys)
regs = {k: ({r} if r else set()) for k, r in zip(records.record_key, records.registration_number_norm)}
ctry = {k: ({c} if c else set()) for k, c in zip(records.record_key, records.country_iso)}

members = {k: {k} for k in keys}
cannot = defaultdict(set)   # steward 'reject' = these two records may never share a golden party, even transitively
for a, b in reject:
    cannot[a].add(b); cannot[b].add(a)

def compatible(ra, rb):
    if ctry[ra] and ctry[rb] and ctry[ra] != ctry[rb]:
        return False
    if any(cannot[x] & members[rb] for x in members[ra] if cannot[x]):
        return False
    return all(OSA.distance(x, y) <= 1 for x in regs[ra] for y in regs[rb])

def merge(a, b):
    ra, rb = uf.find(a), uf.find(b)
    if ra == rb or not compatible(ra, rb):
        return False
    uf.union(ra, rb)
    root = uf.find(ra)
    regs[root], ctry[root], members[root] = regs[ra] | regs[rb], ctry[ra] | ctry[rb], members[ra] | members[rb]
    return True

method, blocked = {}, 0
for a, b in approve:   # steward approvals are applied first and override the constraints
    if a in uf.p and b in uf.p and a not in split and b not in split:
        ra, rb = uf.find(a), uf.find(b)
        uf.union(ra, rb)
        root = uf.find(ra)
        regs[root], ctry[root], members[root] = regs[ra] | regs[rb], ctry[ra] | ctry[rb], members[ra] | members[rb]
        method[a] = method[b] = "steward_approved"
edges = pairs[pairs.match_band == "auto_match"].sort_values("match_score", ascending=False)
for a, b in zip(edges.key_l, edges.key_r):
    if (a, b) in reject or a in split or b in split:
        continue
    if not merge(a, b):
        blocked += uf.find(a) != uf.find(b)
clusters = defaultdict(list)
for k in keys:
    clusters[uf.find(k)].append(k)

# best score linking each record into its cluster (for the xref confidence)
best = defaultdict(float)
for a, b, s in zip(pairs.key_l, pairs.key_r, pairs.match_score):
    if uf.find(a) == uf.find(b):
        best[a], best[b] = max(best[a], s), max(best[b], s)
```

```markdown
%md ## Stable party ids
```

```python
try:
    prev = dict(spark.table(f"{ML}.party_xref").select("record_key", "party_id").toPandas().values)
except Exception:
    prev = {}
assigned, record_party = set(), {}
prev_ids = set(prev.values())
for root, members in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
    votes = Counter(prev[m] for m in members if m in prev and prev[m] not in assigned)
    if votes:
        pid = votes.most_common(1)[0][0]
    else:   # deterministic new id; salt on collision with an id another cluster already holds
        salt = 0
        while True:
            pid = "NBP-" + hashlib.sha1(f"{min(members)}#{salt}".encode()).hexdigest()[:10].upper()
            if pid not in assigned and pid not in prev_ids:
                break
            salt += 1
    assigned.add(pid)
    for m in members:
        record_party[m] = pid

xref = records[["record_key", "source_system", "source_record_id", "source_name"]].copy()
xref["party_id"] = xref.record_key.map(record_party)
size = xref.party_id.map(xref.party_id.value_counts())
xref["match_method"] = [("steward_split" if k in split else method.get(k) or ("singleton" if n == 1 else "model"))
                        for k, n in zip(xref.record_key, size)]
xref["match_confidence"] = [1.0 if n == 1 else round(best[k], 4) for k, n in zip(xref.record_key, size)]
xref["previous_party_id"] = xref.record_key.map(prev)
# Join back to the source records in Spark so Unity Catalog lineage runs party_source_records -> party_xref
from pyspark.sql import functions as F
assign = spark.createDataFrame(xref[["record_key", "party_id", "match_method", "match_confidence", "previous_party_id"]])
(spark.table(f"{SILVER}.party_source_records")
      .select(F.concat_ws(":", "source_system", "source_record_id").alias("record_key"), "source_system", "source_record_id", "source_name")
      .join(assign, "record_key")
      .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{ML}.party_xref"))
spark.sql(f"COMMENT ON TABLE {ML}.party_xref IS 'Entity resolution output: maps every source record (record_key = source_system:source_record_id) to its golden party_id. match_method: model | steward_approved | steward_split | singleton.'")
```

```markdown
%md ## Legal-entity hierarchy
```

```python
reg = spark.table(f"{SILVER}.le_registry").toPandas()
reg_party = defaultdict(Counter)   # registration number -> party votes
for r in records.itertuples():
    if r.registration_number_norm:
        reg_party[r.registration_number_norm][record_party[r.record_key]] += 1
reg_to_party = {k: v.most_common(1)[0][0] for k, v in reg_party.items()}

parent, source = {}, {}
for r in reg.itertuples():
    child = reg_to_party.get(r.registration_number_norm)
    par = reg_to_party.get(r.direct_parent_registration_number_norm) if r.direct_parent_registration_number_norm else None
    if child and par and child != par:
        parent[child], source[child] = par, "LE_REGISTRY"
for r in records[records.source_parent_record_id.notna()].itertuples():   # explicit CRM / AMS parent links
    sys_prefix = "NB_CRM" if r.source_system == "NB_CRM" else "HC_AMS"
    child, par = record_party[r.record_key], record_party.get(f"{sys_prefix}:{r.source_parent_record_id}")
    if par and child != par and child not in parent:
        parent[child], source[child] = par, f"{r.source_system}_PARENT_LINK"

def path_to_top(p):
    path, seen = [p], {p}
    while path[-1] in parent and parent[path[-1]] not in seen and len(path) < 10:
        seen.add(parent[path[-1]]); path.append(parent[path[-1]])
    return path[::-1]

hier = []
for pid in sorted(set(record_party.values())):
    path = path_to_top(pid)
    hier.append({"party_id": pid, "parent_party_id": parent.get(pid), "ultimate_parent_party_id": path[0],
                 "hierarchy_level": len(path) - 1, "hierarchy_path": path, "parent_link_source": source.get(pid)})
(spark.createDataFrame(pd.DataFrame(hier))
      .join(spark.table(f"{ML}.party_xref").select("party_id").distinct(), "party_id")                      # lineage: xref -> hierarchy
      .join(spark.table(f"{SILVER}.le_registry").select(F.lit(1).alias("_r")).limit(1), how="left")         # lineage: registry -> hierarchy
      .drop("_r")
      .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{ML}.party_hierarchy"))
spark.sql(f"COMMENT ON TABLE {ML}.party_hierarchy IS 'Legal-entity hierarchy over golden parties. parent_link_source: LE_REGISTRY (registry direct-parent registration number) or NB_CRM_PARENT_LINK (explicit CRM parent account). hierarchy_level 0 = ultimate parent.'")
```

```markdown
%md ## Persist scored pairs and the run log
```

```python
keep = ["pair_id", "key_l", "key_r", "system_l", "id_l", "source_name_l", "country_l", "reg_l", "addr_l", "system_r", "id_r",
        "source_name_r", "country_r", "reg_r", "addr_r", "match_score", "match_band"]
scored = pairs[keep].copy()
scored = pd.concat([scored, X.reset_index(drop=True)], axis=1)
scored["party_id_l"], scored["party_id_r"] = scored.key_l.map(record_party), scored.key_r.map(record_party)
scored["model_version"] = int(mv.version)
spark.createDataFrame(scored).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{ML}.match_candidates_scored")
spark.sql(f"COMMENT ON TABLE {ML}.match_candidates_scored IS 'Every blocked candidate pair with model features and match_score. match_band: auto_match (>= 0.80), review (0.30-0.80), no_match.'")

n_parties = xref.party_id.nunique()
changed = int(((xref.previous_party_id.notna()) & (xref.previous_party_id != xref.party_id)).sum())
run = {"run_id": str(uuid.uuid4()), "run_ts": datetime.now(timezone.utc), "model_name": MODEL_NAME, "model_version": int(mv.version),
       "source_records": len(records), "candidate_pairs": len(pairs), "auto_match_pairs": int((pairs.match_band == "auto_match").sum()),
       "review_band_pairs": int((pairs.match_band == "review").sum()), "golden_parties": int(n_parties),
       "records_merged": int(len(records) - n_parties), "multi_record_parties": int((xref.party_id.value_counts() > 1).sum()),
       "multi_system_parties": int((xref.groupby("party_id").source_system.nunique() > 1).sum()),
       "steward_decisions_applied": int(len(dec)), "merges_blocked_by_constraints": int(blocked), "records_reassigned_vs_previous_run": changed}
# Quality vs the steward-labelled history (synthetic ground truth): pairwise precision / recall of the clustering
try:
    gt = spark.read.option("header", True).csv(f"/Volumes/{CATALOG}/{P}raw/landing/_labels/er_ground_truth.csv").toPandas()
    truth = dict(zip(gt.source_system + ":" + gt.source_record_id, gt.true_entity_id))
    pred_pairs = {tuple(sorted(c)) for g in xref.groupby("party_id").record_key for c in __import__("itertools").combinations(g[1], 2)}
    by_truth = defaultdict(list)
    for k, e in truth.items():
        by_truth[e].append(k)
    true_pairs = {tuple(sorted(c)) for v in by_truth.values() for c in __import__("itertools").combinations(v, 2)}
    tp = len(pred_pairs & true_pairs)
    run["pairwise_precision"] = round(tp / max(1, len(pred_pairs)), 4)
    run["pairwise_recall"] = round(tp / max(1, len(true_pairs)), 4)
except Exception as exc:
    print("evaluation skipped:", exc)
spark.createDataFrame([run]).write.mode("append").option("mergeSchema", "true").saveAsTable(f"{ML}.er_run_log")
spark.sql(f"COMMENT ON TABLE {ML}.er_run_log IS 'One row per entity resolution run. records_merged = source_records - golden_parties (records folded into another record''s golden party).'")
print(json.dumps(run, default=str, indent=2))
dbutils.notebook.exit(json.dumps(run, default=str))
```
**Output:**
```
{"run_id": "68b61fd9-8e53-4a2a-87af-172d07b685d7", "run_ts": "2026-10-16 21:37:49.675951+00:00", "model_name": "richasethi_febar_catalog.nb_ml.party_match_model", "model_version": 1, "source_records": 4267, "candidate_pairs": 36687, "auto_match_pairs": 3610, "review_band_pairs": 51, "golden_parties": 1862, "records_merged": 2405, "multi_record_parties": 1375, "multi_system_parties": 1346, "steward_decisions_applied": 0, "merges_blocked_by_constraints": 22, "records_reassigned_vs_previous_run": 0, "pairwise_precision": 1.0, "pairwise_recall": 0.9821}
```
