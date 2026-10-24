"""Small helpers shared by several pipeline steps.

The step scripts start with numbers (01_fetch_acs.py, ...), which Python can't import,
so anything two steps need lives here.
"""
import os
import re

import pandas as pd
from dotenv import load_dotenv

import config

load_dotenv(config.ROOT / ".env")


def require_env(name: str) -> str:
    """Read a key from .env, or stop with a message saying which key is missing."""
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing {name} in .env (see .env.example).")
    return value


def require_file(path, what: str):
    """Stop with a clear message if an input file is missing (ground rule 1: never invent data)."""
    if not path.exists():
        raise FileNotFoundError(f"Missing {path.relative_to(config.ROOT)}: expected {what}.")
    return path


def read_acs(geo: str) -> pd.DataFrame:
    """Load the ACS file written by 01_fetch_acs.py ("county" or "tract").

    IDs stay strings; estimates become numbers, with ACS's huge negative
    "missing" codes turned into NaN so they can never be mistaken for real values.
    """
    path = require_file(config.RAW / f"acs_{geo}.csv", f"ACS {geo} table from 01_fetch_acs.py")
    df = pd.read_csv(path, dtype=str)
    for col in config.ACS_VARIABLES.values():
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df.loc[df[col] <= config.ACS_SENTINEL_THRESHOLD, col] = float("nan")
    return df


def tract_display_name(number: str, neighborhood=None) -> str:
    """'Tract 3.01 · Walltown area', or just 'Tract 3.01' when no neighborhood touches it.

    Used by both the map shapes (05) and the scored units (06), so the names always match.
    """
    label = f"Tract {number}"
    if isinstance(neighborhood, str) and neighborhood:
        label += f" · {neighborhood} area"
    return label


def read_tract_neighborhoods() -> dict:
    """GEOID -> neighborhood name, from the table written by 05_build_geo.py."""
    path = require_file(config.INTERIM / "tract_neighborhoods.csv", "tract neighborhood table from 05_build_geo.py")
    df = pd.read_csv(path, dtype={"geoid": str})
    return dict(zip(df["geoid"], df["neighborhood"].where(df["neighborhood"].notna(), None)))


def _normalize_county_name(name: str) -> str:
    # "McDowell County, North Carolina" / "MCDOWELL" / "Mcdowell" -> "mcdowell"
    name = str(name).split(",")[0]
    name = re.sub(r"\bcounty\b", "", name, flags=re.IGNORECASE)
    return re.sub(r"[^a-z]", "", name.lower())


def county_name_to_fips(names) -> dict:
    """Map county names (as written in court files) to 5-digit FIPS codes.

    This is the ONLY place in the project that joins on names (ground rule 3).
    The official name list comes from the Census ACS county table. Every one of
    NC's 100 counties must be matched exactly once, or we stop and list the problems.
    """
    acs = read_acs("county")
    official = {_normalize_county_name(n): f for n, f in zip(acs["NAME"], acs["fips"])}
    if len(official) != config.N_COUNTIES:
        raise ValueError(f"Census county list has {len(official)} names, expected {config.N_COUNTIES}.")

    mapping, unmatched = {}, []
    for name in names:
        fips = official.get(_normalize_county_name(name))
        if fips is None:
            unmatched.append(name)
        else:
            mapping[name] = fips

    matched_fips = list(mapping.values())
    duplicates = sorted({f for f in matched_fips if matched_fips.count(f) > 1})
    missing = sorted(set(official.values()) - set(matched_fips))
    if unmatched or duplicates or missing:
        raise ValueError(
            "County names did not match the 100 NC counties exactly once.\n"
            f"  Unmatched names: {unmatched}\n"
            f"  FIPS matched more than once: {duplicates}\n"
            f"  FIPS never matched: {missing}"
        )
    return mapping
