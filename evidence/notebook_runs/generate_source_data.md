# Notebook run: 5a1267a1-4ace-4838-8df5-ba95399a9515

```markdown
%md
# 01 · Generate synthetic source extracts

Simulates Northbridge Risk Partners one quarter after acquiring Harbor & Cole. A single
ground-truth universe of corporate legal entities (global parents → regional holding
companies → operating subsidiaries) is rendered into five inconsistent source extracts:

| Folder | System | Format | Mess injected |
|---|---|---|---|
| `crm/` | Northbridge CRM | JSON | in-system duplicates, country spelled out, missing reg numbers, partial parent links |
| `billing/` | Northbridge billing & commission | CSV | billed-entity names, null client ids, non-numeric amounts |
| `placement/` | Placement platform | Parquet | insured-name variants, expiry before inception, % keyed as ratio |
| `harbor_cole/` | Harbor & Cole legacy AMS | pipe-delimited TXT | UPPERCASE names, single-line addresses, transposed reg digits, heavy duplication |
| `carrier_statements/` | Carrier commission statements | CSV, three layouts | different columns, delimiters, date and number formats per carrier |
| `reference/` | Legal-entity registry feed (LEI-style) | CSV | parent / ultimate-parent registration numbers |

Revenue is **fee and commission income**. GWP is carried on placements as a reference attribute only.
Deterministic (fixed seed). Skips if data already exists unless `regenerate=true`.
```

```python
dbutils.widgets.text("catalog", "richasethi_febar_catalog")
dbutils.widgets.text("schema_prefix", "nb_")
dbutils.widgets.dropdown("regenerate", "false", ["true", "false"])
dbutils.widgets.text("ingest_pipeline_id", "")
CATALOG = dbutils.widgets.get("catalog")
P = dbutils.widgets.get("schema_prefix")
REGENERATE = dbutils.widgets.get("regenerate") == "true"
ROOT = f"/Volumes/{CATALOG}/{P}raw/landing"
```

```python
import os, random, shutil, string, csv, json, datetime as dt
import pandas as pd

if os.path.exists(f"{ROOT}/crm") and not REGENERATE:
    dbutils.notebook.exit("source data already present - skipping (set regenerate=true to rebuild)")
for sub in ["crm", "billing", "placement", "harbor_cole", "carrier_statements", "reference", "_labels"]:
    shutil.rmtree(f"{ROOT}/{sub}", ignore_errors=True)

rng = random.Random(20261016)
AS_OF = dt.date(2026, 10, 15)
ACQUISITION_DATE = dt.date(2026, 3, 31)
```

```markdown
%md ## Reference vocabulary
```

```python
COUNTRIES = {
    # iso: (name, currency, legal suffixes, cities, raw spellings seen in source systems)
    "GB": ("United Kingdom", "GBP", ["Limited", "plc"], ["London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Bristol"], ["UK", "United Kingdom", "GB", "England"]),
    "US": ("United States", "USD", ["Inc.", "LLC", "Corporation"], ["New York", "Chicago", "Houston", "Atlanta", "Dallas", "Boston", "San Francisco"], ["US", "USA", "U.S.A.", "United States"]),
    "DE": ("Germany", "EUR", ["GmbH", "AG"], ["Frankfurt", "Munich", "Hamburg", "Düsseldorf", "Stuttgart"], ["DE", "Germany", "Deutschland"]),
    "FR": ("France", "EUR", ["SAS", "SA"], ["Paris", "Lyon", "Marseille", "Lille"], ["FR", "France"]),
    "NL": ("Netherlands", "EUR", ["B.V.", "N.V."], ["Amsterdam", "Rotterdam", "Utrecht", "Eindhoven"], ["NL", "Netherlands", "Holland"]),
    "IE": ("Ireland", "EUR", ["Limited", "DAC"], ["Dublin", "Cork", "Galway"], ["IE", "Ireland"]),
    "SG": ("Singapore", "SGD", ["Pte. Ltd."], ["Singapore"], ["SG", "Singapore"]),
    "AU": ("Australia", "AUD", ["Pty Ltd"], ["Sydney", "Melbourne", "Brisbane", "Perth"], ["AU", "Australia"]),
    "CA": ("Canada", "CAD", ["Inc.", "Ltd."], ["Toronto", "Calgary", "Vancouver", "Montreal"], ["CA", "Canada"]),
    "JP": ("Japan", "JPY", ["K.K."], ["Tokyo", "Osaka", "Yokohama"], ["JP", "Japan"]),
    "ES": ("Spain", "EUR", ["S.L.", "S.A."], ["Madrid", "Barcelona", "Valencia"], ["ES", "Spain", "España"]),
    "IT": ("Italy", "EUR", ["S.p.A.", "S.r.l."], ["Milan", "Rome", "Turin"], ["IT", "Italy"]),
    "CH": ("Switzerland", "CHF", ["AG", "SA"], ["Zurich", "Geneva", "Basel"], ["CH", "Switzerland"]),
    "HK": ("Hong Kong", "HKD", ["Limited"], ["Hong Kong"], ["HK", "Hong Kong"]),
    "BR": ("Brazil", "BRL", ["Ltda."], ["São Paulo", "Rio de Janeiro"], ["BR", "Brazil", "Brasil"]),
    "MX": ("Mexico", "MXN", ["S.A. de C.V."], ["Mexico City", "Monterrey"], ["MX", "Mexico"]),
    "AE": ("United Arab Emirates", "AED", ["LLC", "FZE"], ["Dubai", "Abu Dhabi"], ["AE", "UAE", "United Arab Emirates"]),
    "ZA": ("South Africa", "ZAR", ["(Pty) Ltd"], ["Johannesburg", "Cape Town"], ["ZA", "South Africa"]),
    "IN": ("India", "INR", ["Private Limited"], ["Mumbai", "Bengaluru", "Delhi"], ["IN", "India"]),
    "SE": ("Sweden", "SEK", ["AB"], ["Stockholm", "Gothenburg"], ["SE", "Sweden"]),
}
FX_TO_USD = {"GBP": 1.27, "USD": 1.0, "EUR": 1.08, "SGD": 0.74, "AUD": 0.66, "CAD": 0.73, "JPY": 0.0067, "CHF": 1.12,
             "HKD": 0.128, "BRL": 0.19, "MXN": 0.055, "AED": 0.272, "ZAR": 0.054, "INR": 0.012, "SEK": 0.095}
HQ_WEIGHTS = {"GB": 22, "US": 30, "DE": 8, "FR": 6, "NL": 5, "IE": 3, "SG": 4, "AU": 4, "CA": 5, "JP": 3, "ES": 2, "IT": 2,
              "CH": 3, "HK": 2, "BR": 1, "MX": 1, "AE": 1, "ZA": 1, "IN": 1, "SE": 2}
REGIONAL_HUBS = {"Europe": ["NL", "IE", "DE", "CH", "GB"], "Americas": ["US", "CA"], "Asia Pacific": ["SG", "HK", "AU"]}

STEMS = ["Kestrel", "Atlas", "Meridian", "Halcyon", "Northgate", "Bramwell", "Corvus", "Sterling", "Tidewater", "Granite",
         "Vantage", "Orion", "Pinnacle", "Ashford", "Blackmoor", "Caldera", "Driftwood", "Everline", "Fairhaven", "Gryphon",
         "Harrowgate", "Ironbridge", "Juniper", "Keystone", "Lindqvist", "Marlowe", "Nordhavn", "Oakridge", "Pemberton",
         "Quayside", "Redwater", "Saltmarsh", "Thornbury", "Upland", "Valecrest", "Westbrook", "Yarrow", "Zenith", "Albright",
         "Beaumont", "Castellan", "Dunmore", "Elmstead", "Foxglove", "Greystone", "Highmoor", "Islington", "Jarrow",
         "Kingsway", "Larkspur", "Montclair", "Newhaven", "Ottershaw", "Penrose", "Rosedale", "Silverline", "Trident",
         "Umbra", "Verity", "Whitcombe", "Aldridge", "Brightwater", "Coldharbour", "Davenport", "Eastleigh", "Farrington",
         "Glenmore", "Hawthorne", "Ingram", "Kirkwall", "Lowther", "Maddox", "Northcote", "Osgood", "Prescott", "Radcliffe",
         "Selwyn", "Tamworth", "Underhill", "Wexford", "Alder", "Brunel", "Cavendish", "Drake", "Exmoor", "Falkirk",
         "Hadley", "Ivers", "Lancaster", "Merrow Bay", "Norwood", "Pellham", "Quinton", "Rutherford", "Stanmore", "Tolland",
         "Vickery", "Wolsey", "Arden", "Belmont", "Carrick", "Delmar", "Ellery", "Fenwick", "Garrison", "Holloway"]
INDUSTRIES = {
    # industry: (name nouns, lines of business weights)
    "Manufacturing": (["Industries", "Engineering", "Manufacturing"], ["Property", "Casualty", "Product Liability", "D&O", "Cyber", "Marine Cargo", "Trade Credit"]),
    "Energy": (["Energy", "Power", "Resources"], ["Energy Upstream", "Property", "Casualty", "Environmental Liability", "D&O", "Political Risk"]),
    "Marine & Logistics": (["Shipping", "Logistics", "Maritime"], ["Marine Hull", "Marine Cargo", "Casualty", "Property", "Cyber"]),
    "Life Sciences": (["Pharma", "Biosciences", "Life Sciences"], ["Product Liability", "Clinical Trials", "Property", "D&O", "Cyber"]),
    "Food & Agribusiness": (["Foods", "Agri", "Farms"], ["Property", "Product Recall", "Casualty", "Marine Cargo", "Trade Credit"]),
    "Construction & Real Estate": (["Construction", "Properties", "Developments"], ["Construction All Risks", "Property", "Casualty", "Professional Indemnity"]),
    "Financial Institutions": (["Capital", "Financial", "Bancorp"], ["Financial Institutions Bond", "D&O", "Cyber", "Professional Indemnity"]),
    "Technology & Telecom": (["Technologies", "Telecom", "Digital"], ["Cyber", "Technology E&O", "D&O", "Property"]),
    "Retail & Consumer": (["Retail Group", "Brands", "Stores"], ["Property", "Casualty", "Cyber", "Product Liability"]),
    "Hospitality & Leisure": (["Hotels", "Leisure", "Resorts"], ["Property", "Casualty", "Terrorism", "Cyber"]),
    "Aviation & Aerospace": (["Aviation", "Aerospace", "Air"], ["Aviation Hull & Liability", "Product Liability", "Property", "D&O"]),
    "Mining & Metals": (["Mining", "Metals", "Minerals"], ["Property", "Casualty", "Political Risk", "Environmental Liability"]),
    "Defence & Government": (["Defence Systems", "Security", "Dynamics"], ["Property", "Casualty", "Political Risk", "Cyber", "D&O"]),
}
CARRIERS = [  # fictional carriers; layout = how their commission statements arrive
    ("ALBM", "Albion Mutual Insurance", "A"), ("CRST", "Crestline Specialty", "A"), ("HBLR", "Harbourline Re", "B"),
    ("NSEA", "Northsea Underwriting", "B"), ("MRDS", "Meridian Specialty Syndicate 4471", "C"), ("GRTL", "Greatlake Casualty", "A"),
    ("AURA", "Aurora Global Assurance", "C"), ("BCKN", "Beacon Hill Indemnity", "A"), ("SLVR", "Silverbirch Insurance AG", "B"),
    ("KNGT", "Knightsbridge Marine", "C"), ("PACR", "Pacific Rim Assurance", "A"), ("VLRA", "Valora Seguros", "B"),
    ("TMBR", "Timberline Mutual", "A"), ("CORS", "Corsair Specialty Lines", "C"),
]
BROKERS_NB = ["Amelia Grant", "Daniel Okafor", "Priya Raman", "Tom Whitfield", "Sofia Lindgren", "Marcus Chen", "Hannah Osei",
              "Luca Bianchi", "Olivia Brooks", "James Achebe", "Chloe Martin", "Rajesh Iyer", "Emma Kowalski", "Noah Fischer"]
PRODUCERS_HC = ["R. HARBOR", "J. COLE", "M. DEVLIN", "S. PATEL", "K. O'NEILL", "T. NAKAMURA"]
FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Jamie", "Robin", "Charlie", "Avery", "Quinn", "Riley", "Elena",
         "Mateo", "Aisha", "Kenji", "Ingrid", "Ravi", "Fatima", "Lars", "Chiara", "Diego", "Mei", "Oliver", "Zara", "Henrik"]
LAST = ["Smith", "Johnson", "Patel", "Nguyen", "Müller", "Rossi", "García", "Okonkwo", "Andersson", "Tanaka", "Dubois",
        "O'Brien", "Kowalski", "Haddad", "Silva", "Fraser", "Lindqvist", "Moreau", "Schmidt", "Ito", "Murphy", "Costa"]
TITLES = ["Group Risk Manager", "CFO", "Head of Insurance", "Treasurer", "General Counsel", "Risk & Insurance Director", "Finance Director"]
STREET_NAMES = ["King", "Queen", "High", "Station", "Harbour", "Market", "Church", "Mill", "Bridge", "Park", "Victoria",
                "Albert", "Commerce", "Main", "Lake", "Riverside", "Canal", "Wharf", "Union", "Exchange"]
STREET_TYPES = ["Street", "Road", "Avenue", "Lane", "Square", "Place", "Quay", "Boulevard"]

def pick_country():
    return rng.choices(list(HQ_WEIGHTS), weights=list(HQ_WEIGHTS.values()))[0]

def reg_number(country):
    d = lambda n: "".join(rng.choice(string.digits) for _ in range(n))
    return {"GB": lambda: "0" + d(7), "US": lambda: f"{d(2)}-{d(7)}", "DE": lambda: f"HRB {d(6)}", "FR": lambda: f"{d(3)} {d(3)} {d(3)}",
            "NL": lambda: d(8), "IE": lambda: d(6), "SG": lambda: f"{d(9)}K", "AU": lambda: f"{d(3)} {d(3)} {d(3)}",
            "CA": lambda: d(9), "JP": lambda: d(13), "ES": lambda: f"B{d(8)}", "IT": lambda: d(11), "CH": lambda: f"CHE-{d(3)}.{d(3)}.{d(3)}",
            "HK": lambda: d(8), "BR": lambda: f"{d(2)}.{d(3)}.{d(3)}/0001-{d(2)}", "MX": lambda: f"{''.join(rng.choice(string.ascii_uppercase) for _ in range(3))}{d(6)}{d(3)}",
            "AE": lambda: f"CN-{d(7)}", "ZA": lambda: f"{d(4)}/{d(6)}/07", "IN": lambda: f"U{d(5)}MH{d(4)}PTC{d(6)}", "SE": lambda: f"{d(6)}-{d(4)}"}[country]()

def postcode(country):
    d = lambda n: "".join(rng.choice(string.digits) for _ in range(n))
    L = lambda n: "".join(rng.choice(string.ascii_uppercase) for _ in range(n))
    return {"GB": lambda: f"{L(2)}{d(1)} {d(1)}{L(2)}", "US": lambda: d(5), "CA": lambda: f"{L(1)}{d(1)}{L(1)} {d(1)}{L(1)}{d(1)}",
            "NL": lambda: f"{d(4)} {L(2)}", "IE": lambda: f"D{d(2)} {L(1)}{d(1)}{L(1)}{d(1)}", "JP": lambda: f"{d(3)}-{d(4)}",
            "BR": lambda: f"{d(5)}-{d(3)}", "SE": lambda: f"{d(3)} {d(2)}"}.get(country, lambda: d(rng.choice([4, 5, 6])))()

def address(country):
    city = rng.choice(COUNTRIES[country][3])
    return {"line1": f"{rng.randint(1, 250)} {rng.choice(STREET_NAMES)} {rng.choice(STREET_TYPES)}", "city": city, "postcode": postcode(country)}
```

```markdown
%md ## Ground-truth legal-entity universe
```

```python
entities, families = [], []
_eid = [0]

_used_names = set()
_ALL_SUFFIXES = sorted({x for v in COUNTRIES.values() for x in v[2]}, key=len, reverse=True)
_QUALIFIERS = ["Services", "Trading", "Operations", "Solutions", "Partners", "Distribution", "Ventures", "Technical"]

def unique_name(name, country):
    """A registered legal name is unique within a jurisdiction: add a trading qualifier before the legal suffix if taken."""
    base, sfx = name, ""
    for x in _ALL_SUFFIXES:
        if name.endswith(" " + x):
            base, sfx = name[: -len(x) - 1], x
            break
    cand, i = name, 0
    while (cand.lower(), country) in _used_names:
        cand = f"{base} {_QUALIFIERS[i % len(_QUALIFIERS)]}{'' if i < len(_QUALIFIERS) else ' ' + str(i)} {sfx}".strip()
        i += 1
    _used_names.add((cand.lower(), country))
    return cand

def new_entity(family, name, country, parent, level, reg=None, addr=None):
    name = unique_name(name, country)
    _eid[0] += 1
    e = {"entity_id": f"LE{_eid[0]:05d}", "family_id": family["family_id"], "legal_name": name, "country": country,
         "reg_no": reg or reg_number(country), "parent_entity_id": parent["entity_id"] if parent else None, "level": level,
         "industry": family["industry"], "is_restricted": family["is_restricted"], "segment": family["segment"],
         "nb_client": family["nb_client"], "hc_client": family["hc_client"], "size": family["size"], **(addr or address(country))}
    e["old_addr"] = address(country)
    entities.append(e)
    return e

def new_family(stem, industry, hq, nb_client, hc_client, size=None, forced_segment=None):
    size = size or rng.choices(["global", "large", "mid"], weights=[18, 37, 45])[0]
    fam = {"family_id": f"FAM{len(families) + 1:04d}", "stem": stem, "industry": industry, "hq": hq, "size": size,
           "is_restricted": industry == "Defence & Government",
           "segment": forced_segment or {"global": "Global Corporate", "large": "Large Corporate", "mid": "Middle Market"}[size],
           "nb_client": nb_client, "hc_client": hc_client}
    families.append(fam)
    return fam

def build_family(fam):
    stem, ind, hq = fam["stem"], fam["industry"], fam["hq"]
    noun = rng.choice(INDUSTRIES[ind][0])
    sfx = lambda c: rng.choice(COUNTRIES[c][2])
    top_sfx = "plc" if hq == "GB" and fam["size"] != "mid" else sfx(hq)
    top = new_entity(fam, f"{stem} {noun} {'Group ' if rng.random() < .3 and 'Group' not in noun else ''}{top_sfx}".replace("  ", " "), hq, None, 0)
    n_hold = {"global": rng.randint(2, 3), "large": rng.randint(0, 2), "mid": 0}[fam["size"]]
    n_ops = {"global": rng.randint(5, 9), "large": rng.randint(2, 5), "mid": rng.randint(0, 2)}[fam["size"]]
    holdcos = []
    for region in rng.sample(list(REGIONAL_HUBS), n_hold):
        c = rng.choice([x for x in REGIONAL_HUBS[region] if x != hq] or REGIONAL_HUBS[region])
        holdcos.append(new_entity(fam, f"{stem} {noun} {region} Holdings {sfx(c)}", c, top, 1))
    for _ in range(n_ops):
        parent = rng.choice(holdcos) if holdcos and rng.random() < .65 else top
        pool = [c for r, cs in REGIONAL_HUBS.items() for c in cs] + list(COUNTRIES)
        c = rng.choice(pool)
        if rng.random() < .15:   # acquired subsidiary trading under an unrelated name
            name = f"{rng.choice(STEMS)} {rng.choice(['Coatings', 'Components', 'Services', 'Solutions', 'Systems'])} {sfx(c)}"
        else:
            qual = rng.choice([COUNTRIES[c][0], rng.choice(["Services", "Operations", "Trading", "International"]), ""])
            name = f"{stem} {noun} {qual} {sfx(c)}" if c != hq or qual else f"{stem} {rng.choice(INDUSTRIES[ind][0])} {sfx(c)}"
        shared = {k: parent[k] for k in ("line1", "city", "postcode")} if c == parent["country"] and rng.random() < .4 else None
        new_entity(fam, " ".join(name.split()), c, parent, 2, addr=shared)
    return top

# --- Headline family: Kestrel Industries plc (hand-built so the demo has a known rich example) ---
kes = new_family("Kestrel", "Manufacturing", "GB", True, True, size="global")
k0 = new_entity(kes, "Kestrel Industries plc", "GB", None, 0, reg="04718293", addr={"line1": "40 Leadenhall Street", "city": "London", "postcode": "EC3A 2BJ"})
k1 = new_entity(kes, "Kestrel Industries Holdings Inc.", "US", k0, 1, reg="36-4182937", addr={"line1": "233 Wacker Drive", "city": "Chicago", "postcode": "60606"})
k2 = new_entity(kes, "Kestrel Industries Europe B.V.", "NL", k0, 1, reg="58213946", addr={"line1": "12 Wilhelminakade", "city": "Rotterdam", "postcode": "3072 AP"})
k3 = new_entity(kes, "Kestrel Marine Services Limited", "GB", k0, 2, reg="07391022", addr={"line1": "3 Ocean Quay", "city": "Southampton", "postcode": "SO14 3QN"})
k4 = new_entity(kes, "Kestrel Industries GmbH", "DE", k2, 2, reg="HRB 774120", addr={"line1": "88 Hafenstraße", "city": "Hamburg", "postcode": "20457"})
k5 = new_entity(kes, "Kestrel Logistics LLC", "US", k1, 2, reg="47-2290183", addr={"line1": "900 Commerce Avenue", "city": "Atlanta", "postcode": "30303"})
k6 = new_entity(kes, "Bluewater Coatings Inc.", "US", k1, 2, reg="81-5532018", addr={"line1": "15 Harbor Road", "city": "Houston", "postcode": "77002"})
k7 = new_entity(kes, "Kestrel Industries (Singapore) Pte. Ltd.", "SG", k0, 2, reg="201734118K", addr={"line1": "1 Marina Boulevard", "city": "Singapore", "postcode": "018989"})

# --- A restricted (defence) family so the row filter has something visible to hide ---
iron = new_family("Ironclad", "Defence & Government", "GB", True, True, size="global")
build_family(iron)

# --- Random families ---
stems = [s for s in STEMS if s not in ("Kestrel", "Ironclad")]
rng.shuffle(stems)
industries = list(INDUSTRIES)
for i, stem in enumerate(stems * 4):
    if len(families) >= 420:
        break
    ind = rng.choices(industries, weights=[14, 8, 9, 7, 7, 8, 9, 9, 8, 5, 4, 5, 3])[0]
    r = rng.random()
    nb, hc = (True, False) if r < .70 else (True, True) if r < .82 else (False, True)   # 12% overlap, 18% H&C-only
    build_family(new_family(stem if i < len(stems) else f"{stem} {rng.choice(['North', 'Global', 'United', 'First', 'Royal'])}", ind, pick_country(), nb, hc))

# --- True negatives: same trading name, different country, unrelated company ---
decoys = [("Kestrel", "Manufacturing", "AU", "Kestrel Industries Pty Ltd"), ("Kestrel", "Food & Agribusiness", "GB", "Kestrel Foods Limited")]
for e in rng.sample([e for e in entities if e["level"] == 0 and e["family_id"] not in (kes["family_id"], iron["family_id"])], 30):
    c = rng.choice([x for x in ["US", "GB", "AU", "CA", "IE", "DE", "SG"] if x != e["country"]])
    core = " ".join(w for w in e["legal_name"].split() if w not in sum([v[2] for v in COUNTRIES.values()], []) and w not in ("Group",))
    decoys.append((core.split()[0], e["industry"], c, f"{core} {rng.choice(COUNTRIES[c][2])}"))
for stem, ind, c, name in decoys:
    fam = new_family(stem, ind, c, True, rng.random() < .3, size="mid")
    new_entity(fam, name, c, None, 0)

ent_df = pd.DataFrame(entities)
ENT = {e["entity_id"]: e for e in entities}
print(f"{len(families)} families, {len(entities)} legal entities")
```
**Output:**
```
452 families, 2061 legal entities
```

```markdown
%md ## Messy renderings
```

```python
SUFFIX_VARIANTS = {"Limited": ["Ltd", "Ltd.", "LIMITED", "Limited"], "plc": ["PLC", "Plc", "plc", "Public Limited Company"],
                   "Inc.": ["Inc", "Incorporated", "INC", "Inc."], "LLC": ["L.L.C.", "LLC", "Llc"], "Corporation": ["Corp", "Corp.", "Corporation"],
                   "GmbH": ["GmbH", "GMBH", "Gesellschaft mbH"], "B.V.": ["BV", "B.V.", "b.v."], "N.V.": ["NV", "N.V."],
                   "Pte. Ltd.": ["Pte Ltd", "PTE. LTD.", "Pte. Limited"], "Pty Ltd": ["Pty. Ltd.", "PTY LTD", "Pty Limited"],
                   "S.A. de C.V.": ["SA de CV", "S.A. DE C.V."], "Private Limited": ["Pvt Ltd", "Pvt. Ltd.", "Private Ltd"],
                   "(Pty) Ltd": ["Pty Ltd", "(PTY) LTD"], "S.p.A.": ["SpA", "S.P.A."], "S.r.l.": ["Srl", "S.R.L."], "S.L.": ["SL", "S.L."], "Ltd.": ["Ltd", "Limited"]}
WORD_ABBREV = {"Industries": ["Ind.", "Inds", "Industries", "Indus."], "International": ["Intl", "Int'l", "International"],
               "Holdings": ["Hldgs", "Holdings", "Hold."], "Services": ["Svcs", "Services"], "Engineering": ["Eng.", "Engineering"],
               "Logistics": ["Logistics", "Log."], "Group": ["Group", "Grp", ""], "Technologies": ["Tech", "Technologies"],
               "Pharma": ["Pharma", "Pharmaceuticals"], "Manufacturing": ["Mfg", "Manufacturing"], "and": ["&", "and"]}

def name_variant(name, intensity=0.5):
    words = name.split()
    out = []
    for w in words:
        if w in WORD_ABBREV and rng.random() < intensity:
            w = rng.choice(WORD_ABBREV[w])
        out.append(w)
    s = " ".join(x for x in out if x)
    for k, vs in SUFFIX_VARIANTS.items():
        if s.endswith(" " + k) and rng.random() < .7:
            s = s[: -len(k)] + rng.choice(vs)
            break
    if rng.random() < .08 * intensity * 2:   # typo: swap two adjacent characters
        i = rng.randint(1, max(1, len(s) - 3))
        s = s[:i] + s[i + 1] + s[i] + s[i + 2:]
    if rng.random() < .12 * intensity:   # a qualifier word dropped, e.g. "Kestrel Marine Services" -> "Kestrel Marine"
        parts = s.split()
        if len(parts) > 3:
            del parts[rng.randint(1, len(parts) - 2)]
            s = " ".join(parts)
    if rng.random() < .1:
        s = s.upper()
    return s

def stale_addr(e, p):
    """Legacy and secondary systems often hold a former registered office or a branch address."""
    return e["old_addr"] if rng.random() < p else {k: e[k] for k in ("line1", "city", "postcode")}

def addr_variant(line1):
    s = line1
    for full, ab in [("Street", "St"), ("Road", "Rd"), ("Avenue", "Ave"), ("Boulevard", "Blvd"), ("Square", "Sq"), ("Lane", "Ln")]:
        if full in s and rng.random() < .5:
            s = s.replace(full, ab + rng.choice(["", "."]))
    if rng.random() < .15:
        s = rng.choice(["Floor 3, ", "Suite 400, ", "Level 12, ", "Unit 2, "]) + s
    return s

def reg_variant(reg, p_missing, p_transpose=0.0):
    if rng.random() < p_missing:
        return None
    digits = [i for i, ch in enumerate(reg) if ch.isdigit()]
    if rng.random() < p_transpose and len(digits) > 3:
        i = rng.choice(digits[1:-1])
        j = i + 1 if i + 1 in digits else i - 1
        r = list(reg); r[i], r[j] = r[j], r[i]; reg = "".join(r)
    return reg if rng.random() < .6 else reg.replace(" ", "").replace("-", "").replace(".", "")

def raw_country(iso):
    return rng.choice(COUNTRIES[iso][4])

labels = []   # (source_system, source_record_id, true_entity_id)
```

```markdown
%md ### Northbridge CRM (JSON)
```

```python
crm, contacts = [], []
crm_by_entity = {}
def crm_record(e, dup=False, name=None, reg=..., parent_ref=True):
    aid = f"001NB{len(crm) + 1:07d}"
    a = stale_addr(e, .45 if dup else 0)
    rec = {"account_id": aid, "account_name": name or (name_variant(e["legal_name"], .6) if dup else e["legal_name"]),
           "billing_country": raw_country(e["country"]), "billing_street": addr_variant(a["line1"]) if dup else a["line1"],
           "billing_city": a["city"], "billing_postal_code": a["postcode"],
           "company_registration_no": reg_variant(e["reg_no"], .5 if dup else .25) if reg is ... else reg,
           "industry": e["industry"], "client_segment": e["segment"],
           "client_confidentiality": "Restricted" if e["is_restricted"] else rng.choice(["Standard", "Standard", "Confidential"]),
           "account_executive": rng.choice(BROKERS_NB), "parent_account_id": None,
           "created_date": str(dt.date(2014, 1, 1) + dt.timedelta(days=rng.randint(0, 4200))),
           "last_modified": str(AS_OF - dt.timedelta(days=rng.randint(0, 400)))}
    crm.append(rec)
    crm_by_entity.setdefault(e["entity_id"], []).append(rec)
    labels.append(("NB_CRM", aid, e["entity_id"]))
    for _ in range(rng.choice([1, 1, 2, 3])):
        fn, ln = rng.choice(FIRST), rng.choice(LAST)
        dom = "".join(ch for ch in e["legal_name"].split()[0].lower() if ch.isalpha()) + rng.choice([".com", ".co.uk", ".de", ".net"])
        email = f"{fn.lower()}.{ln.lower().replace(chr(39), '')}@{dom}" if rng.random() > .02 else f"{fn.lower()}{ln.lower()}{dom}"
        contacts.append({"contact_id": f"003NB{len(contacts) + 1:07d}", "account_id": aid, "first_name": fn, "last_name": ln,
                         "title": rng.choice(TITLES), "email": email, "phone": f"+{rng.randint(1, 99)} {rng.randint(100, 999)} {rng.randint(1000000, 9999999)}"})
    return rec

for e in entities:
    if not e["nb_client"] or e["family_id"] == kes["family_id"]:
        continue
    if rng.random() < (.95 if e["level"] == 0 else .7):
        crm_record(e)
        if rng.random() < .06:
            crm_record(e, dup=True)
# Kestrel: two CRM accounts for the parent (one created by the London office, one by the Chicago office)
crm_record(k0); crm_record(k0, name="Kestrel Industries PLC", reg=None)
for k in [k1, k2, k3, k4, k5, k7]:   # headline family: registration numbers on file so the hierarchy is complete every run
    crm_record(k, reg=k["reg_no"])
# parent links: CRM knows ~55% of parent relationships
for e in entities:
    if e["parent_entity_id"] and e["entity_id"] in crm_by_entity and e["parent_entity_id"] in crm_by_entity and rng.random() < .55:
        for rec in crm_by_entity[e["entity_id"]]:
            rec["parent_account_id"] = crm_by_entity[e["parent_entity_id"]][0]["account_id"]
# dirty rows the pipeline should quarantine
for rec in rng.sample(crm, int(len(crm) * .01)):
    rec["billing_country"] = rng.choice(["ZZ", "", "N/A"])
for rec in rng.sample(crm, 6):
    rec["account_name"] = None
```

```markdown
%md ### Placement platform (Parquet) and Harbor & Cole AMS (pipe-delimited)
```

```python
insureds, placements = [], []
ins_by_entity = {}
def insured_record(e, name=None, reg=...):
    iid = f"INS{len(insureds) + 1:07d}"
    a = stale_addr(e, .12)
    rec = {"insured_id": iid, "insured_name": name or name_variant(e["legal_name"], .3), "domicile_country": e["country"],
           "registration_number": reg_variant(e["reg_no"], .35) if reg is ... else reg, "address": f"{a['line1']}, {a['city']}, {a['postcode']}",
           "parent_insured_name": None, "industry_code": e["industry"].upper().replace(" & ", "_").replace(" ", "_")}
    insureds.append(rec)
    ins_by_entity[e["entity_id"]] = rec
    labels.append(("NB_PLACEMENT", iid, e["entity_id"]))
    return rec

for e in entities:
    if e["nb_client"] and e["entity_id"] not in (k0["entity_id"], k3["entity_id"], k6["entity_id"]) and rng.random() < .82:
        insured_record(e)
insured_record(k0, "Kestrel Industries plc"); insured_record(k3); insured_record(k6, "Bluewater Coatings, Inc.", reg=k6["reg_no"])   # acquired sub, different name: linked only via the registry

def gwp_for(e):
    base = {"global": 900_000, "large": 350_000, "mid": 120_000}[e["size"]] * (1.6 if e["level"] == 0 else 1.0)
    return round(rng.lognormvariate(0, .7) * base, -2)

pid = 0
for e in entities:
    if e["entity_id"] not in ins_by_entity:
        continue
    lobs = INDUSTRIES[e["industry"]][1]
    n_lines = min(len(lobs), rng.randint(1, 4) + (2 if e["level"] == 0 else 0))
    ccy = COUNTRIES[e["country"]][1]
    for lob in rng.sample(lobs, n_lines):
        carrier = rng.choice(CARRIERS)
        start = dt.date(rng.choice([2022, 2023]), rng.randint(1, 12), 1)
        rem = rng.choices(["Commission", "Fee", "Commission + Fee"], weights=[70, 12, 18])[0]
        gwp_local = gwp_for(e) / FX_TO_USD[ccy]
        while start <= AS_OF:
            pid += 1
            if rng.random() < .25:   # change carrier at renewal sometimes
                carrier = rng.choice(CARRIERS)
            rate = 0.0 if rem == "Fee" else round(rng.uniform(.075, .175), 4)
            fee = round(rng.uniform(15_000, 180_000) / FX_TO_USD[ccy], -2) if rem != "Commission" else 0.0
            gwp_local = round(gwp_local * rng.uniform(.95, 1.12), -2)
            placements.append({"placement_id": f"PLC-{pid:07d}", "insured_id": ins_by_entity[e["entity_id"]]["insured_id"],
                               "line_of_business": lob, "carrier_code": carrier[0], "carrier_name": carrier[1],
                               "inception_date": start, "expiry_date": start.replace(year=start.year + 1) - dt.timedelta(days=1),
                               "broker_of_record": rng.choice(BROKERS_NB), "placing_office": rng.choice(["London", "New York", "Chicago", "Singapore", "Frankfurt", "Toronto"]),
                               "currency": ccy, "gross_written_premium": gwp_local, "remuneration_basis": rem,
                               "commission_rate": rate, "fee_amount": fee,
                               "placement_status": "Bound" if start.replace(year=start.year + 1) > AS_OF else "Expired"})
            start = start.replace(year=start.year + 1)
for p in rng.sample(placements, int(len(placements) * .006)):
    p["expiry_date"] = p["inception_date"] - dt.timedelta(days=rng.randint(1, 60))
for p in rng.sample(placements, int(len(placements) * .003)):
    p["commission_rate"] = round(p["commission_rate"] * 100, 2) or 12.5   # keyed as a percentage, not a ratio

hc_clients, hc_policies = [], []
hc_codes = {}
def hc_record(e, name=None, reg=..., sens=None):
    base = "".join(ch for ch in e["legal_name"].upper() if ch.isalpha())[:5]
    hc_codes[base] = hc_codes.get(base, 0) + 1
    code = f"{base}{hc_codes[base]:02d}"
    nm = name or name_variant(e["legal_name"], .8).upper()
    a = stale_addr(e, .35) if name is None else {k: e[k] for k in ("line1", "city", "postcode")}
    rec = {"CLIENT_CODE": code, "CLIENT_NAME": nm, "ADDR": f"{addr_variant(a['line1']).upper()}, {a['city'].upper()}, {a['postcode']}",
           "CNTRY": raw_country(e["country"]).upper(), "REG_NO": reg_variant(e["reg_no"], .4, .15) if reg is ... else reg,
           "SIC_DESC": e["industry"].upper(), "SENS_FLAG": "Y" if e["is_restricted"] else "N",
           "PRODUCER": rng.choice(PRODUCERS_HC), "DATE_OPENED": (dt.date(2009, 1, 1) + dt.timedelta(days=rng.randint(0, 5500))).strftime("%m/%d/%Y"),
           "PARENT_CLIENT_CODE": ""}
    hc_clients.append(rec)
    labels.append(("HC_AMS", code, e["entity_id"]))
    return rec

for e in entities:
    if e["hc_client"] and e["family_id"] != kes["family_id"] and (e["level"] == 0 or rng.random() < .55):
        hc_record(e)
        if rng.random() < .15:
            hc_record(e)
# Kestrel: Harbor & Cole held the parent twice (one with a transposed reg number) and the UK marine sub
hc_record(k0, name="KESTREL INDUSTRIES PLC", reg="04712893")
hc_record(k0, name="KESTREL INDS PLC", reg=None)
hc_record(k3, name="KESTREL MARINE SVCS LTD")
for rec in rng.sample(hc_clients, 4):
    rec["CLIENT_NAME"] = ""

HC_LOB = {"Property": "PROP", "Casualty": "GL", "D&O": "DO", "Cyber": "CYB", "Marine Cargo": "MCGO", "Marine Hull": "MHUL",
          "Product Liability": "PL", "Professional Indemnity": "PI", "Trade Credit": "TCR", "Environmental Liability": "ENV",
          "Political Risk": "PRI", "Construction All Risks": "CAR", "Terrorism": "TERR", "Technology E&O": "TEO",
          "Energy Upstream": "ENUP", "Aviation Hull & Liability": "AVN", "Financial Institutions Bond": "FIB",
          "Product Recall": "PRC", "Clinical Trials": "CTL"}
hc_ent = {r_id: eid for (sys, r_id, eid) in labels if sys == "HC_AMS"}
for rec in hc_clients:
    e = ENT[hc_ent[rec["CLIENT_CODE"]]]
    for lob in rng.sample(INDUSTRIES[e["industry"]][1], rng.randint(1, 3)):
        start = dt.date(rng.choice([2021, 2022, 2023, 2024]), rng.randint(1, 12), 1)
        prem = gwp_for(e) * .6
        while start <= AS_OF:
            comm_pct = round(rng.uniform(8, 15), 1)
            carrier = rng.choice(CARRIERS)
            hc_policies.append({"POLICY_NO": f"HC-{rng.randint(10, 99)}-{len(hc_policies) + 1:06d}", "CLIENT_CODE": rec["CLIENT_CODE"],
                                "LOB": HC_LOB[lob], "CARRIER": carrier[1].upper(), "EFF_DATE": start.strftime("%m/%d/%Y"),
                                "EXP_DATE": (start.replace(year=start.year + 1)).strftime("%m/%d/%Y"),
                                "PREMIUM": f"{prem:.2f}", "COMM_PCT": f"{comm_pct}", "COMM_AMT": f"{prem * comm_pct / 100:.2f}",
                                "FEE": f"{rng.choice([0, 0, 0, 2500, 5000, 7500]):.2f}", "CCY": "USD" if e["country"] in ("US", "CA") else "GBP" if e["country"] == "GB" else "EUR",
                                "PRODUCER": rec["PRODUCER"]})
            prem *= rng.uniform(.97, 1.1)
            start = start.replace(year=start.year + 1)
```

```markdown
%md ### Billing & commission (CSV): billed clients and revenue transactions
```

```python
billing_clients, txns = [], []
bill_by_entity = {}
def billing_record(e, name=None):
    bid = f"BL-{len(billing_clients) + 1:06d}"
    a = stale_addr(e, .15)
    rec = {"billing_client_id": bid, "billing_name": name or name_variant(e["legal_name"], .4),
           "tax_or_registration_id": reg_variant(e["reg_no"], .3), "country_code": e["country"] if rng.random() < .8 else raw_country(e["country"]),
           "invoice_address": f"{addr_variant(a['line1'])}; {a['city']}; {a['postcode']}", "invoice_currency": COUNTRIES[e["country"]][1],
           "payment_terms": rng.choice(["30 days", "45 days", "60 days"]), "ar_status": rng.choice(["Current", "Current", "Current", "Overdue"])}
    billing_clients.append(rec)
    bill_by_entity[e["entity_id"]] = rec
    labels.append(("NB_BILLING", bid, e["entity_id"]))
    return rec

for e in entities:
    if e["entity_id"] in ins_by_entity and e["entity_id"] != k0["entity_id"] and rng.random() < .8:
        billing_record(e)
billing_record(k0, "Kestrel Industries Public Limited Company")

def billed_entity(eid):
    # commission is billed to the insured if it has a billing account, otherwise up the ownership chain
    while eid and eid not in bill_by_entity:
        eid = ENT[eid]["parent_entity_id"]
    return eid
insured_to_entity = {v["insured_id"]: k for k, v in ins_by_entity.items()}
tid = 0
for p in placements:
    if p["inception_date"] > AS_OF or p["expiry_date"] < p["inception_date"]:
        continue
    be = billed_entity(insured_to_entity[p["insured_id"]])
    if not be:
        continue
    bid = bill_by_entity[be]["billing_client_id"]
    rate = p["commission_rate"] if p["commission_rate"] < 1 else p["commission_rate"] / 100
    comm = p["gross_written_premium"] * rate
    n_inst = rng.choice([1, 1, 2, 4])
    for i in range(n_inst):
        d = p["inception_date"] + dt.timedelta(days=int(365 / n_inst) * i + rng.randint(0, 20))
        if d > AS_OF:
            break
        if comm > 0:
            tid += 1
            txns.append({"transaction_id": f"TX{tid:08d}", "billing_client_id": bid, "placement_ref": p["placement_id"],
                         "transaction_date": d.isoformat(), "revenue_type": "Commission", "line_of_business": p["line_of_business"],
                         "carrier_code": p["carrier_code"], "currency": p["currency"], "amount": f"{comm / n_inst:.2f}"})
        if p["fee_amount"] > 0:
            tid += 1
            txns.append({"transaction_id": f"TX{tid:08d}", "billing_client_id": bid, "placement_ref": p["placement_id"],
                         "transaction_date": d.isoformat(), "revenue_type": "Fee", "line_of_business": p["line_of_business"],
                         "carrier_code": p["carrier_code"], "currency": p["currency"], "amount": f"{p['fee_amount'] / n_inst:.2f}"})
for t in rng.sample(txns, int(len(txns) * .02)):   # mid-term adjustments / return commission
    tid += 1
    txns.append({**t, "transaction_id": f"TX{tid:08d}", "revenue_type": "Commission Adjustment",
                 "amount": f"{-abs(float(t['amount'])) * rng.uniform(.05, .4):.2f}"})
for t in rng.sample(txns, int(len(txns) * .007)):
    t["billing_client_id"] = ""
for t in rng.sample(txns, int(len(txns) * .003)):
    t["amount"] = rng.choice(["N/A", "#VALUE!", "TBC"])
```

```markdown
%md ### Carrier commission statements (three layouts) and the legal-entity registry
```

```python
stmts = {c[0]: [] for c in CARRIERS}
ins_name = {v["insured_id"]: v["insured_name"] for v in insureds}
for p in placements:
    if p["inception_date"] > AS_OF or p["commission_rate"] == 0 or p["expiry_date"] < p["inception_date"]:
        continue
    rate = p["commission_rate"] if p["commission_rate"] < 1 else p["commission_rate"] / 100
    comm = p["gross_written_premium"] * rate * (1 if rng.random() > .04 else rng.uniform(.85, .98))   # some carriers short-pay
    stmts[p["carrier_code"]].append({"period": p["inception_date"].replace(day=28), "policy": p["placement_id"] if rng.random() > .02 else "",
                                     "insured": ins_name[p["insured_id"]], "lob": p["line_of_business"], "premium": p["gross_written_premium"],
                                     "rate": rate, "comm": comm, "ccy": p["currency"]})

os.makedirs(f"{ROOT}/carrier_statements", exist_ok=True)
for code, name, layout in CARRIERS:
    rows = stmts[code]
    d = f"{ROOT}/carrier_statements/layout_{layout.lower()}/{code}"
    os.makedirs(d, exist_ok=True)
    for year in sorted({r["period"].year for r in rows}):
        yr = [r for r in rows if r["period"].year == year]
        path = f"{d}/{code}_commission_statement_{year}.csv"
        with open(path, "w", newline="") as f:
            if layout == "A":
                w = csv.writer(f)
                w.writerow(["Carrier", "Statement Period", "Policy Ref", "Insured Name", "Line", "Gross Premium", "Comm %", "Comm Amt", "Ccy"])
                for r in yr:
                    w.writerow([name, r["period"].isoformat(), r["policy"], r["insured"], r["lob"], f"{r['premium']:.2f}", f"{r['rate'] * 100:.2f}", f"{r['comm']:.2f}", r["ccy"]])
            elif layout == "B":
                w = csv.writer(f, quoting=csv.QUOTE_ALL)
                w.writerow(["carrier_name", "stmt_month", "policy_number", "client", "premium", "brokerage_rate", "commission", "currency_code"])
                for r in yr:
                    w.writerow([name, r["period"].strftime("%d/%m/%Y"), r["policy"], r["insured"].upper(), f"{r['premium']:,.2f}", f"{r['rate']:.4f}", f"{r['comm']:,.2f}", r["ccy"]])
            else:
                w = csv.writer(f, delimiter=";")
                w.writerow(["PERIOD_END", "POLICY", "ASSURED", "CLASS", "BROKERAGE", "CURRENCY", "SYNDICATE"])
                for r in yr:
                    w.writerow([r["period"].strftime("%Y%m%d"), r["policy"], r["insured"], r["lob"].upper(), f"{r['comm']:.2f}".replace(".", ","), r["ccy"], name])

registry = []
for e in entities:
    if rng.random() < .88 or e["family_id"] == kes["family_id"]:
        parent = ENT[e["parent_entity_id"]] if e["parent_entity_id"] else None
        top = e
        while top["parent_entity_id"]:
            top = ENT[top["parent_entity_id"]]
        registry.append({"lei": "5493" + "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(16)),
                         "legal_name": e["legal_name"], "jurisdiction": e["country"], "registration_number": e["reg_no"],
                         "registered_address": f"{e['line1']}, {e['city']}, {e['postcode']}",
                         "direct_parent_registration_number": parent["reg_no"] if parent is not None else None,
                         "direct_parent_jurisdiction": parent["country"] if parent is not None else None,
                         "ultimate_parent_registration_number": top["reg_no"], "ultimate_parent_jurisdiction": top["country"],
                         "entity_status": "ACTIVE"})
```

```markdown
%md ## Write the drop zone
```

```python
def mk(p):
    os.makedirs(p, exist_ok=True); return p

def write_json_lines(rows, path):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")

def chunks(rows, n):
    k = max(1, len(rows) // n + 1)
    return [rows[i:i + k] for i in range(0, len(rows), k)]

for i, part in enumerate(chunks(crm, 3)):
    write_json_lines(part, f"{mk(f'{ROOT}/crm/accounts')}/accounts_extract_{i:02d}.json")
write_json_lines(contacts, f"{mk(f'{ROOT}/crm/contacts')}/contacts_extract_00.json")
pd.DataFrame(billing_clients).to_csv(f"{mk(f'{ROOT}/billing/clients')}/billing_clients.csv", index=False)
for i, part in enumerate(chunks(txns, 4)):
    pd.DataFrame(part).to_csv(f"{mk(f'{ROOT}/billing/transactions')}/revenue_transactions_{i:02d}.csv", index=False)
pd.DataFrame(insureds).to_parquet(f"{mk(f'{ROOT}/placement/insureds')}/insureds.parquet", index=False)
pdf = pd.DataFrame(placements)
pdf.to_parquet(f"{mk(f'{ROOT}/placement/placements')}/placements.parquet", index=False)   # python dates -> parquet DATE
pd.DataFrame(hc_clients).to_csv(f"{mk(f'{ROOT}/harbor_cole/clients')}/HC_CLIENT_MASTER.TXT", sep="|", index=False)
pd.DataFrame(hc_policies).to_csv(f"{mk(f'{ROOT}/harbor_cole/policies')}/HC_POLICY_REGISTER.TXT", sep="|", index=False)
pd.DataFrame(registry).to_csv(f"{mk(f'{ROOT}/reference/le_registry')}/legal_entity_registry.csv", index=False)
pd.DataFrame(labels, columns=["source_system", "source_record_id", "true_entity_id"]).merge(
    ent_df[["entity_id", "family_id"]].rename(columns={"entity_id": "true_entity_id", "family_id": "true_family_id"})
).to_csv(f"{mk(f'{ROOT}/_labels')}/er_ground_truth.csv", index=False)
ent_df.to_csv(f"{ROOT}/_labels/legal_entity_truth.csv", index=False)

if REGENERATE and dbutils.widgets.get("ingest_pipeline_id"):
    # New files replace old ones at the same paths, so streaming checkpoints must be reset: full-refresh the ingest pipeline.
    import time
    from databricks.sdk import WorkspaceClient
    _w, _pid = WorkspaceClient(), dbutils.widgets.get("ingest_pipeline_id")
    _upd = _w.pipelines.start_update(_pid, full_refresh=True).update_id
    while (_st := _w.pipelines.get_update(_pid, _upd).update.state.value) not in ("COMPLETED", "FAILED", "CANCELED"):
        time.sleep(15)
    assert _st == "COMPLETED", f"ingest full refresh {_st}"

summary = {"families": len(families), "legal_entities": len(entities), "crm_accounts": len(crm), "crm_contacts": len(contacts),
           "billing_clients": len(billing_clients), "revenue_transactions": len(txns), "insureds": len(insureds),
           "placements": len(placements), "hc_clients": len(hc_clients), "hc_policies": len(hc_policies),
           "carrier_statement_lines": sum(len(v) for v in stmts.values()), "registry_rows": len(registry), "source_party_records": len(labels)}
print(json.dumps(summary, indent=2))
dbutils.notebook.exit(json.dumps(summary))
```
**Output:**
```
{"families": 452, "legal_entities": 2061, "crm_accounts": 1365, "crm_contacts": 2348, "billing_clients": 1085, "revenue_transactions": 33307, "insureds": 1380, "placements": 16748, "hc_clients": 460, "hc_policies": 4037, "carrier_statement_lines": 14537, "registry_rows": 1805, "source_party_records": 4290}
```
