# Databricks notebook source
# MAGIC %md
# MAGIC # 10 · Train the pairwise party match model
# MAGIC
# MAGIC 1. **Blocking** - generate candidate pairs from `silver.party_source_records` across all four systems.
# MAGIC 2. **Features** - name similarity (Jaro-Winkler, token sort/set), structural-word mismatch (HOLDINGS, EUROPE...),
# MAGIC    registration number exact / one-transposition / conflict, country, address, postcode, city, industry.
# MAGIC 3. **Labels** - steward-labelled match history (synthetic, `_labels/er_ground_truth.csv`).
# MAGIC 4. **Model** - gradient-boosted classifier, split by corporate family so subsidiaries never leak across train/test.
# MAGIC 5. **Register** in Unity Catalog as `ml.party_match_model`, alias `champion`.
# MAGIC
# MAGIC Skips if a champion already exists unless `retrain=true`.

# COMMAND ----------

# MAGIC %pip install -q rapidfuzz==3.9.7 "mlflow>=3.1" scikit-learn==1.5.2
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "richasethi_febar_catalog")
dbutils.widgets.text("schema_prefix", "nb_")
dbutils.widgets.dropdown("retrain", "false", ["true", "false"])
CATALOG, P = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema_prefix")
RETRAIN = dbutils.widgets.get("retrain") == "true"
MODEL_NAME = f"{CATALOG}.{P}ml.party_match_model"
LABELS = f"/Volumes/{CATALOG}/{P}raw/landing/_labels/er_ground_truth.csv"

# COMMAND ----------

import mlflow
from mlflow import MlflowClient

mlflow.set_registry_uri("databricks-uc")
client = MlflowClient()
try:
    champ = client.get_model_version_by_alias(MODEL_NAME, "champion")
except Exception:
    champ = None
if champ is not None and not RETRAIN:   # notebook.exit raises internally, so it must not sit inside a try/except
    dbutils.notebook.exit(f"champion v{champ.version} exists - skipping training (set retrain=true to retrain)")

# COMMAND ----------

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

from er_features import FEATURES, candidate_pairs_sql, featurize

pairs = spark.sql(candidate_pairs_sql(f"{CATALOG}.{P}silver.party_source_records")).toPandas()
labels = spark.read.option("header", True).csv(LABELS).toPandas()
labels["record_key"] = labels["source_system"] + ":" + labels["source_record_id"]
ent = dict(zip(labels.record_key, labels.true_entity_id))
fam = dict(zip(labels.record_key, labels.true_family_id))

pairs["label"] = (pairs.key_l.map(ent) == pairs.key_r.map(ent)).astype(int)
pairs["family"] = pairs.key_l.map(fam)
X = featurize(pairs)
y = pairs["label"].values
print(f"{len(pairs):,} candidate pairs, {y.sum():,} true matches ({y.mean():.1%})")

# COMMAND ----------

gss = GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=7)
tr, te = next(gss.split(X, y, groups=pairs["family"].fillna("none")))

EXP_NAME = f"/Users/{spark.sql('select current_user()').first()[0]}/northbridge_entity_resolution"
_exp = client.get_experiment_by_name(EXP_NAME)
if _exp is not None and _exp.lifecycle_stage == "deleted":
    client.restore_experiment(_exp.experiment_id)
mlflow.set_experiment(EXP_NAME)
with mlflow.start_run(run_name="party_match_hgb") as run:
    params = {"max_iter": 300, "learning_rate": 0.08, "max_leaf_nodes": 31, "l2_regularization": 1.0}
    model = HistGradientBoostingClassifier(**params, random_state=7).fit(X.iloc[tr], y[tr])
    p = model.predict_proba(X.iloc[te])[:, 1]
    metrics = {"auc": roc_auc_score(y[te], p), "avg_precision": average_precision_score(y[te], p),
               "precision_at_0_8": precision_score(y[te], p >= 0.8), "recall_at_0_8": recall_score(y[te], p >= 0.8),
               "f1_at_0_5": f1_score(y[te], p >= 0.5), "review_band_share": float(((p >= 0.3) & (p < 0.8)).mean()),
               "train_pairs": len(tr), "test_pairs": len(te)}
    mlflow.log_params({**params, "features": ",".join(FEATURES), "blocking": "reg|token+country|soundex|postcode"})
    mlflow.log_metrics(metrics)
    sig = mlflow.models.infer_signature(X.iloc[:50], model.predict_proba(X.iloc[:50])[:, 1])
    info = mlflow.sklearn.log_model(model, name="model", signature=sig, input_example=X.iloc[:5],
                                    registered_model_name=MODEL_NAME, pyfunc_predict_fn="predict_proba")
    print(metrics)

# COMMAND ----------

mv = info.registered_model_version
client.set_registered_model_alias(MODEL_NAME, "champion", mv)
client.update_registered_model(MODEL_NAME, description=(
    "Pairwise party match model for Northbridge Client 360 entity resolution. Input: features of a candidate pair of "
    "client records from NB_CRM / NB_BILLING / NB_PLACEMENT / HC_AMS. Output: probability the two records are the same "
    "legal entity. >= 0.80 auto-merge, 0.30-0.80 steward review with LLM rationale, < 0.30 no match."))
client.update_model_version(MODEL_NAME, mv, description=f"AUC {metrics['auc']:.4f}, precision@0.8 {metrics['precision_at_0_8']:.3f}, recall@0.8 {metrics['recall_at_0_8']:.3f}")
dbutils.notebook.exit(f"registered {MODEL_NAME} v{mv} as champion")
