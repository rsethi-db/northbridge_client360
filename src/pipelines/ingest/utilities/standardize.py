"""Standardization rules shared by the silver layer.

These are deterministic clean-up rules only (casing, punctuation, legal suffixes, country spellings).
Deciding which records are the same company is left to the entity resolution model.
"""
from itertools import chain

from pyspark.sql import Column
from pyspark.sql import functions as F

COUNTRY_SPELLINGS = {
    "UK": "GB", "UNITED KINGDOM": "GB", "GB": "GB", "ENGLAND": "GB", "US": "US", "USA": "US", "U.S.A.": "US",
    "UNITED STATES": "US", "DE": "DE", "GERMANY": "DE", "DEUTSCHLAND": "DE", "FR": "FR", "FRANCE": "FR",
    "NL": "NL", "NETHERLANDS": "NL", "HOLLAND": "NL", "IE": "IE", "IRELAND": "IE", "SG": "SG", "SINGAPORE": "SG",
    "AU": "AU", "AUSTRALIA": "AU", "CA": "CA", "CANADA": "CA", "JP": "JP", "JAPAN": "JP", "ES": "ES", "SPAIN": "ES",
    "ESPAÑA": "ES", "IT": "IT", "ITALY": "IT", "CH": "CH", "SWITZERLAND": "CH", "HK": "HK", "HONG KONG": "HK",
    "BR": "BR", "BRAZIL": "BR", "BRASIL": "BR", "MX": "MX", "MEXICO": "MX", "AE": "AE", "UAE": "AE",
    "UNITED ARAB EMIRATES": "AE", "ZA": "ZA", "SOUTH AFRICA": "ZA", "IN": "IN", "INDIA": "IN", "SE": "SE", "SWEDEN": "SE",
}
VALID_COUNTRIES = sorted(set(COUNTRY_SPELLINGS.values()))

# Fixed planning rates used by Northbridge finance for the demo period (USD per unit of currency).
FX_TO_USD = {"GBP": 1.27, "USD": 1.0, "EUR": 1.08, "SGD": 0.74, "AUD": 0.66, "CAD": 0.73, "JPY": 0.0067, "CHF": 1.12,
             "HKD": 0.128, "BRL": 0.19, "MXN": 0.055, "AED": 0.272, "ZAR": 0.054, "INR": 0.012, "SEK": 0.095}

LEGAL_SUFFIX_TOKENS = ["PUBLIC LIMITED COMPANY", "GESELLSCHAFT MBH", "S A DE C V", "SA DE CV", "PRIVATE LIMITED", "PTE LIMITED",
                       "PTY LIMITED", "LIMITED", "LTD", "PLC", "INCORPORATED", "INC", "L L C", "LLC", "CORPORATION", "CORP",
                       "GMBH", "AG", "B V", "BV", "N V", "NV", "SAS", "SA", "PTE", "PTY", "K K", "KK", "S L", "SL", "S P A",
                       "SPA", "S R L", "SRL", "LTDA", "FZE", "AB", "DAC", "PVT", "PRIVATE"]
ABBREVIATIONS = {"INDS": "INDUSTRIES", "INDUS": "INDUSTRIES", "IND": "INDUSTRIES", "INTL": "INTERNATIONAL", "INT L": "INTERNATIONAL",
                 "HLDGS": "HOLDINGS", "HOLD": "HOLDINGS", "SVCS": "SERVICES", "ENG": "ENGINEERING", "MFG": "MANUFACTURING",
                 "GRP": "GROUP", "LOG": "LOGISTICS", "TECH": "TECHNOLOGIES", "PHARMACEUTICALS": "PHARMA"}


def country_iso(c: Column) -> Column:
    m = F.create_map(*[F.lit(x) for x in chain(*COUNTRY_SPELLINGS.items())])
    return m[F.upper(F.trim(c))]


def fx_rate(ccy: Column) -> Column:
    m = F.create_map(*[F.lit(x) for x in chain(*FX_TO_USD.items())])
    return m[F.upper(ccy)]


def name_clean(c: Column) -> Column:
    s = F.upper(F.trim(c))
    s = F.regexp_replace(s, "&", " AND ")
    s = F.regexp_replace(s, "[^A-Z0-9 ]", " ")
    return F.trim(F.regexp_replace(s, " +", " "))


def name_core(c: Column) -> Column:
    """Clean name with legal-form suffixes removed and common abbreviations expanded."""
    s = F.concat(F.lit(" "), name_clean(c), F.lit(" "))
    for tok in LEGAL_SUFFIX_TOKENS:
        s = F.regexp_replace(s, f" {tok} ", " ")
    for k, v in ABBREVIATIONS.items():
        s = F.regexp_replace(s, f" {k} ", f" {v} ")
    s = F.regexp_replace(s, " THE ", " ")
    return F.trim(F.regexp_replace(s, " +", " "))


def reg_norm(c: Column) -> Column:
    s = F.regexp_replace(F.upper(c), "[^A-Z0-9]", "")
    return F.when(F.length(s) > 0, s)


def address_norm(c: Column) -> Column:
    s = F.concat(F.lit(" "), name_clean(c), F.lit(" "))
    s = F.regexp_replace(s, "^ (FLOOR|SUITE|LEVEL|UNIT) [0-9]+ ", " ")
    for ab, full in [("ST", "STREET"), ("RD", "ROAD"), ("AVE", "AVENUE"), ("BLVD", "BOULEVARD"), ("SQ", "SQUARE"), ("LN", "LANE")]:
        s = F.regexp_replace(s, f" {ab} ", f" {full} ")
    return F.trim(F.regexp_replace(s, " +", " "))


def postcode_norm(c: Column) -> Column:
    return F.regexp_replace(F.upper(c), "[^A-Z0-9]", "")


def parse_amount(c: Column) -> Column:
    """Handles '1,234.56', '1234,56' (European decimal comma) and junk like 'N/A' (-> NULL)."""
    s = F.trim(c)
    s = F.when(s.rlike(r"^-?[0-9]+,[0-9]{2}$"), F.regexp_replace(s, ",", ".")).otherwise(F.regexp_replace(s, ",", ""))
    return F.when(s.rlike(r"^-?[0-9]+(\.[0-9]+)?$"), s.cast("decimal(18,2)"))
