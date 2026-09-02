from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd


def clean_player_name(name: str) -> str:
    if pd.isna(name):
        return ""
    cleaned = str(name).strip()
    cleaned = cleaned.replace("\xa0", "")
    cleaned = cleaned.replace("\u00a0", "")
    cleaned = cleaned.strip()
    cleaned = __import__("re").sub(r"^[0-9]+", "", cleaned)
    return cleaned.strip()


def clean_column_name(column_name: str) -> str:
    cleaned = str(column_name).strip()
    cleaned = cleaned.replace("\n", "").replace("\r", "")
    cleaned = cleaned.replace("\xa0", "")
    cleaned = "".join(ch for ch in cleaned if ch.isprintable())
    return cleaned.strip()


def load_player_dataset(csv_path: str | Path) -> pd.DataFrame:
    """Load and normalize the CSV file used for the draft assistant."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_csv(path)
    df.columns = [clean_column_name(col) for col in df.columns]

    required_columns = {"Player", "Pos", "Club", "Avg", "Price", "sheet_name", "league", "season"}
    missing = sorted(required_columns - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.copy()
    df["Player"] = df["Player"].map(clean_player_name)
    df["Pos"] = df["Pos"].astype(str).str.upper().str.strip()
    df["Club"] = df["Club"].astype(str).str.strip()
    df["season"] = df["season"].astype(str)

    numeric_columns = [
        "Avg", "Price", "Apps", "St", "Min", "G", "PG", "PMS", "A", "Sh", "SoT",
        "SOFF", "WOOD", "KP", "BC", "BCM", "PAS", "APAS", "PAS%", "CRS", "ACR",
        "LB", "LBW", "TB", "PFT", "Drb", "DRA", "DRP", "Tkl", "Int", "Clr", "BLK",
        "LMT", "REC", "DUE", "DUW", "AER", "FDR", "FLS", "OFS", "DIS", "PLS",
        "ERG", "ELS", "PCM", "CS", "GC", "Sv", "SIB", "SV%", "PSV", "HCL",
        "PUN", "YC", "2YC", "RC", "OG"
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Player", "Pos", "Avg"]).copy()
    return df


def filter_season_2026(df: pd.DataFrame) -> pd.DataFrame:
    if "season" in df.columns:
        return df[df["season"].astype(str).str.strip() == "2026"].copy()
    return df.copy()


def get_position_data(df: pd.DataFrame, position: str) -> pd.DataFrame:
    return df[df["Pos"].str.upper() == position.upper()].copy()


def build_player_catalog(csv_path: str | Path) -> Dict[str, pd.DataFrame]:
    df = load_player_dataset(csv_path)
    df = filter_season_2026(df)
    position_map = {
        "FW": get_position_data(df, "FW"),
        "MID": get_position_data(df, "MID"),
        "DEF": get_position_data(df, "DEF"),
        "GK": get_position_data(df, "GK"),
    }
    return position_map
