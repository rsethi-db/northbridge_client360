# Notebook run: 9c5602df-d73b-4742-a531-09e5566bcd42

```markdown
%md
# 12 · GenAI assist for ambiguous matches

Pairs the match model scores in the **review band (0.30-0.80)** are sent to a Databricks Foundation Model via
`ai_query`, which returns a structured recommendation (`MERGE` / `KEEP_SEPARATE` / `NEEDS_MORE_INFO`) and a
plain-English rationale the steward sees in the Client 360 app.

Bounded and cheap: at most `max_new_pairs` new pairs per run, and assessments are cached by `pair_id`
in `ml.llm_match_assessments` so re-runs never pay for the same pair twice.
```

```python
dbutils.widgets.text("catalog", "richasethi_febar_catalog")
dbutils.widgets.text("schema_prefix", "nb_")
dbutils.widgets.text("llm_endpoint", "databricks-claude-sonnet-4-6")
dbutils.widgets.text("max_new_pairs", "300")
CATALOG, P = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema_prefix")
ENDPOINT, CAP = dbutils.widgets.get("llm_endpoint"), int(dbutils.widgets.get("max_new_pairs"))
ML = f"{CATALOG}.{P}ml"
```

```python
spark.sql(f"""CREATE TABLE IF NOT EXISTS {ML}.llm_match_assessments (
  pair_id STRING, llm_recommendation STRING, llm_confidence STRING, llm_rationale STRING, llm_error STRING,
  llm_endpoint STRING, assessed_at TIMESTAMP)
COMMENT 'Cache of Foundation Model assessments for review-band candidate pairs, keyed by pair_id.'""")
spark.sql(f"DELETE FROM {ML}.llm_match_assessments WHERE llm_error IS NOT NULL OR llm_recommendation IS NULL")   # retry transient failures

SCHEMA = ('{"type":"json_schema","json_schema":{"name":"match_assessment","strict":true,"schema":{"type":"object",'
          '"properties":{"recommendation":{"type":"string","enum":["MERGE","KEEP_SEPARATE","NEEDS_MORE_INFO"]},'
          '"confidence":{"type":"string","enum":["high","medium","low"]},"rationale":{"type":"string"}},'
          '"required":["recommendation","confidence","rationale"]}}}')

spark.sql(f"""
CREATE OR REPLACE TEMP VIEW to_assess AS
SELECT s.*,
  concat(
    'You are a client master-data steward at Northbridge Risk Partners, a global insurance broker that recently acquired the ',
    'Harbor & Cole agency. Decide whether two client records refer to the SAME LEGAL ENTITY (same company, same registration), ',
    'not merely the same corporate group. Subsidiaries, regional holding companies and same-name companies in other countries are ',
    'DIFFERENT legal entities. Registration numbers can contain data-entry errors such as a single transposed digit; legal suffixes ',
    'vary (Ltd/Limited/plc/Public Limited Company); legacy systems use upper case and abbreviations. ',
    'Weigh the evidence like an experienced steward: ',
    '(1) Same full legal name after ignoring case, punctuation, legal-suffix spelling and abbreviations (Inds/Industries, Hldgs/Holdings), ',
    'same country, and no conflicting registration number => MERGE with medium confidence, even if addresses differ (legacy and branch systems often hold a former or branch address). ',
    '(2) Registration numbers that are identical or differ by one transposed digit, plus a matching name => MERGE with high confidence. ',
    '(3) Names that differ by a structural qualifier (Holdings, Europe, Americas, Services, a country name), different countries, or clearly different registration numbers => KEEP_SEPARATE. ',
    '(4) Use NEEDS_MORE_INFO only when the evidence is genuinely balanced, e.g. a dropped word that could be a qualifier. ',
    'Give a rationale of at most 35 words citing the specific evidence (names, registration, address).\\n\\n',
    'Record A (', s.system_l, ' ', s.id_l, '): name="', s.source_name_l, '", country=', coalesce(s.country_l, 'unknown'),
    ', registration=', coalesce(s.reg_l, 'missing'), ', address="', coalesce(s.addr_l, 'missing'), '"\\n',
    'Record B (', s.system_r, ' ', s.id_r, '): name="', s.source_name_r, '", country=', coalesce(s.country_r, 'unknown'),
    ', registration=', coalesce(s.reg_r, 'missing'), ', address="', coalesce(s.addr_r, 'missing'), '"\\n',
    'Match model probability: ', format_number(s.match_score, 2)) AS prompt
FROM {ML}.match_candidates_scored s
LEFT ANTI JOIN {ML}.llm_match_assessments a ON s.pair_id = a.pair_id
WHERE s.match_band = 'review'
ORDER BY abs(s.match_score - 0.55), s.pair_id
LIMIT {CAP}
""")
n_new = spark.table("to_assess").count()
print(f"assessing {n_new} new review-band pairs with {ENDPOINT}")
```
**Output:**
```
assessing 51 new review-band pairs with databricks-claude-sonnet-4-6
```

```python
if n_new:
    spark.sql(f"""
    INSERT INTO {ML}.llm_match_assessments
    SELECT pair_id, parsed.recommendation, parsed.confidence, parsed.rationale, resp.errorMessage, '{ENDPOINT}', current_timestamp()
    FROM (
      SELECT pair_id, resp,
             from_json(resp.result, 'recommendation STRING, confidence STRING, rationale STRING') AS parsed
      FROM (SELECT pair_id, ai_query('{ENDPOINT}', prompt, responseFormat => '{SCHEMA}', failOnError => false) AS resp FROM to_assess)
    )""")
```

```markdown
%md ## Steward review queue (synced to Lakebase for the app)
```

```python
spark.sql(f"""
CREATE OR REPLACE TABLE {ML}.match_review_queue
COMMENT 'Steward match-review queue: review-band candidate pairs with model score and LLM recommendation/rationale. Synced to Lakebase and shown in the Client 360 steward view.'
AS SELECT s.pair_id, s.key_l AS left_record_key, s.key_r AS right_record_key,
          s.system_l AS left_source_system, s.source_name_l AS left_name, s.country_l AS left_country, s.reg_l AS left_registration,
          s.addr_l AS left_address, s.party_id_l AS left_party_id,
          s.system_r AS right_source_system, s.source_name_r AS right_name, s.country_r AS right_country, s.reg_r AS right_registration,
          s.addr_r AS right_address, s.party_id_r AS right_party_id,
          round(s.match_score, 4) AS match_score, s.model_version, (s.party_id_l = s.party_id_r) AS currently_same_party,
          a.llm_recommendation, a.llm_confidence, a.llm_rationale, a.llm_endpoint, a.assessed_at
   FROM {ML}.match_candidates_scored s JOIN {ML}.llm_match_assessments a USING (pair_id)
   WHERE s.match_band = 'review' AND a.llm_error IS NULL
""")
display(spark.sql(f"SELECT llm_recommendation, llm_confidence, count(*) n FROM {ML}.match_review_queue GROUP BY ALL ORDER BY n DESC"))
```
