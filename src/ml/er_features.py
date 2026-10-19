"""Entity resolution: blocking + pairwise features. Shared by training and resolution notebooks."""
import hashlib

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler, OSA

FEATURES = ["name_jw", "name_token_sort", "name_token_set", "name_core_exact", "first_token_eq", "extra_token_count",
            "holdings_mismatch", "reg_both_present", "reg_exact", "reg_near", "reg_conflict", "country_eq",
            "addr_token_sort", "postcode_eq", "city_eq", "same_source_system", "industry_eq"]

STRUCTURE_WORDS = {"HOLDINGS", "GROUP", "EUROPE", "AMERICAS", "ASIA", "PACIFIC", "INTERNATIONAL", "SERVICES", "OPERATIONS",
                   "TRADING", "GLOBAL", "NORTH", "UNITED", "FIRST", "ROYAL"}


def record_key(system, record_id):
    return f"{system}:{record_id}"


def pair_id(k1, k2):
    a, b = sorted([k1, k2])
    return hashlib.sha1(f"{a}|{b}".encode()).hexdigest()[:16]


def candidate_pairs_sql(table):
    """Blocking: only compare records that share a registration number, a name token + country,
    a phonetic name key, or a postcode. Cuts N^2 comparisons to a few tens of thousands."""
    return f"""
    WITH r AS (
      SELECT concat(source_system, ':', source_record_id) AS record_key, *,
             get(split(name_core, ' '), 0) AS tok1,
             soundex(coalesce(get(split(name_core, ' '), 1), '')) AS sdx2
      FROM {table}
    ),
    blocks AS (
      SELECT record_key, concat('reg|', registration_number_norm) AS block FROM r WHERE registration_number_norm IS NOT NULL
      UNION ALL SELECT record_key, concat('tokc|', tok1, '|', country_iso) FROM r WHERE tok1 IS NOT NULL
      UNION ALL SELECT record_key, concat('sdx|', tok1, '|', sdx2) FROM r WHERE tok1 IS NOT NULL
      UNION ALL SELECT record_key, concat('pc|', postcode_norm, '|', country_iso) FROM r WHERE length(postcode_norm) >= 4
    ),
    pairs AS (
      SELECT DISTINCT a.record_key AS key_l, b.record_key AS key_r
      FROM blocks a JOIN blocks b ON a.block = b.block AND a.record_key < b.record_key
    )
    SELECT p.key_l, p.key_r,
           l.source_system AS system_l, l.source_record_id AS id_l, l.source_name AS source_name_l, l.name_core AS name_core_l,
           l.country_iso AS country_l, l.registration_number_norm AS reg_l, l.address_norm AS addr_l, l.postcode_norm AS postcode_l,
           l.city AS city_l, l.industry AS industry_l,
           r2.source_system AS system_r, r2.source_record_id AS id_r, r2.source_name AS source_name_r, r2.name_core AS name_core_r,
           r2.country_iso AS country_r, r2.registration_number_norm AS reg_r, r2.address_norm AS addr_r, r2.postcode_norm AS postcode_r,
           r2.city AS city_r, r2.industry AS industry_r
    FROM pairs p JOIN r l ON p.key_l = l.record_key JOIN r r2 ON p.key_r = r2.record_key
    """


def _s(x):
    return "" if x is None or (isinstance(x, float) and np.isnan(x)) else str(x)


def featurize(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    nl, nr = df["name_core_l"].map(_s), df["name_core_r"].map(_s)
    out["name_jw"] = [JaroWinkler.similarity(a, b) for a, b in zip(nl, nr)]
    out["name_token_sort"] = [fuzz.token_sort_ratio(a, b) / 100 for a, b in zip(nl, nr)]
    out["name_token_set"] = [fuzz.token_set_ratio(a, b) / 100 for a, b in zip(nl, nr)]
    out["name_core_exact"] = (nl == nr).astype(int)
    out["first_token_eq"] = [int(a.split(" ")[:1] == b.split(" ")[:1]) for a, b in zip(nl, nr)]
    toks = [(set(a.split()), set(b.split())) for a, b in zip(nl, nr)]
    out["extra_token_count"] = [len(a ^ b) for a, b in toks]
    out["holdings_mismatch"] = [int(bool((a ^ b) & STRUCTURE_WORDS)) for a, b in toks]
    rl, rr = df["reg_l"].map(_s), df["reg_r"].map(_s)
    both = (rl != "") & (rr != "")
    dist = [OSA.distance(a, b) if a and b else 99 for a, b in zip(rl, rr)]
    out["reg_both_present"] = both.astype(int)
    out["reg_exact"] = (both & (rl == rr)).astype(int)
    out["reg_near"] = [int(b and d == 1) for b, d in zip(both, dist)]   # one transposition / typo
    out["reg_conflict"] = [int(b and d > 1) for b, d in zip(both, dist)]
    out["country_eq"] = (df["country_l"].map(_s) == df["country_r"].map(_s)).astype(int)
    out["addr_token_sort"] = [fuzz.token_sort_ratio(_s(a), _s(b)) / 100 if _s(a) and _s(b) else -1.0
                              for a, b in zip(df["addr_l"], df["addr_r"])]
    pl, pr = df["postcode_l"].map(_s), df["postcode_r"].map(_s)
    out["postcode_eq"] = np.where((pl == "") | (pr == ""), -1, (pl == pr).astype(int))
    cl, cr = df["city_l"].map(_s), df["city_r"].map(_s)
    out["city_eq"] = np.where((cl == "") | (cr == ""), -1, (cl == cr).astype(int))
    out["same_source_system"] = (df["system_l"] == df["system_r"]).astype(int)
    il, ir = df["industry_l"].map(lambda x: _s(x).lower()), df["industry_r"].map(lambda x: _s(x).lower())
    out["industry_eq"] = np.where((il == "") | (ir == ""), -1, (il == ir).astype(int))
    return out[FEATURES].astype(float)


class UnionFind:
    def __init__(self, items):
        self.p = {i: i for i in items}

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)
