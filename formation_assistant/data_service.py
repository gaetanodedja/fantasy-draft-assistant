from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import soccerdata as sd


PLAYERS = [
    "Vanja Milinković-Savić",
    "Alex Meret",
    "Luka Vuskovic",
    "Jeff Chabot",
    "Mario Hermoso",
    "Lewis Dunk",
    "Jérémy Jacquet",
    "Kristoffer Ajer",
    "Matija Katic",
    "Scott McTominay",
    "Can Uzun",
    "Pierre-Emile Højbjerg",
    "Edu Exposito",
    "Pape Gueye",
    "Erling Haaland",
    "Igor Thiago",
    "Mattia Zaccagni",
    "Randal Kolo Muani",
    "Alexander Isak",
    "Dominic Calvert-Lewin",
]

LEAGUE_BY_TEAM = {
    "NAP": "ITA-Serie A",
    "LAZ": "ITA-Serie A",
    "JUV": "ITA-Serie A",
    "ROM": "ITA-Serie A",
    "VFB": "GER-Bundesliga",
    "SGE": "GER-Bundesliga",
    "OM": "FRA-Ligue 1",
    "ESY": "ESP-La Liga",
    "VIL": "ESP-La Liga",
    "BHA": "ENG-Premier League",
    "LIV": "ENG-Premier League",
    "BRE": "ENG-Premier League",
    "MCI": "ENG-Premier League",
    "LEE": "ENG-Premier League",
}

TEAM_ALIASES = {
    "NAP": ("Napoli", "Naples"),
    "BHA": ("Brighton and Hove Albion", "Brighton & Hove Albion", "Brighton"),
    "VFB": ("Stuttgart", "VfB Stuttgart"),
    "ROM": ("Roma", "AS Roma"),
    "LIV": ("Liverpool",),
    "BRE": ("Brentford",),
    "SGE": ("Eintracht Frankfurt", "Frankfurt"),
    "OM": ("Marseille", "Olympique de Marseille"),
    "ESY": ("Espanyol", "RCD Espanyol", "Espanyol Barcelona"),
    "VIL": ("Villarreal", "Villarreal CF"),
    "MCI": ("Manchester City",),
    "LAZ": ("Lazio",),
    "JUV": ("Juventus",),
    "LEE": ("Leeds United", "Leeds"),
}

DIFFICULTY_LEVELS = ("very easy", "easy", "average", "hard", "very hard")
POSITION_ORDER = ("GK", "DEF", "MID", "FW")
FORMATIONS = {
    "3-4-3": {"GK": 1, "DEF": 3, "MID": 4, "FW": 3},
    "3-5-2": {"GK": 1, "DEF": 3, "MID": 5, "FW": 2},
    "4-3-3": {"GK": 1, "DEF": 4, "MID": 3, "FW": 3},
    "4-4-2": {"GK": 1, "DEF": 4, "MID": 4, "FW": 2},
    "4-5-1": {"GK": 1, "DEF": 4, "MID": 5, "FW": 1},
    "5-3-2": {"GK": 1, "DEF": 5, "MID": 3, "FW": 2},
    "5-4-1": {"GK": 1, "DEF": 5, "MID": 4, "FW": 1},
}


def normalize_player_name(name: Any) -> str:
    value = re.sub(r"^\s*\d+\s*", "", str(name or ""))
    value = " ".join(value.replace("\u00a0", " ").split()).casefold()
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )


def normalize_team_name(name: Any) -> str:
    value = unicodedata.normalize("NFKD", str(name or "")).casefold()
    return "".join(char for char in value if char.isalnum())


def is_team(name: Any, club_code: str) -> bool:
    aliases = TEAM_ALIASES.get(club_code, (club_code,))
    return normalize_team_name(name) in {normalize_team_name(alias) for alias in aliases}


def canonical_team_key(name: Any) -> str:
    normalized = normalize_team_name(name)
    for code, aliases in TEAM_ALIASES.items():
        if normalized == normalize_team_name(code) or normalized in {
            normalize_team_name(alias) for alias in aliases
        }:
            return code
    return normalized


def difficulty_from_percentile(percentile: float) -> str | None:
    if pd.isna(percentile):
        return None
    value = float(percentile)
    for upper_bound, label in zip(
        (0.2, 0.4, 0.6, 0.8), DIFFICULTY_LEVELS, strict=False
    ):
        if value <= upper_bound:
            return label
    return DIFFICULTY_LEVELS[-1]


def _read_roster(workbook_path: Path, season: int) -> pd.DataFrame:
    if not workbook_path.is_file():
        raise FileNotFoundError(f"Fantasy workbook not found: {workbook_path}")

    workbook = pd.read_excel(
        workbook_path,
        sheet_name=None,
        usecols=["Player", "Pos", "Club"],
    )
    player_lookup: dict[str, tuple[int, str, str]] = {}
    for sheet_name, sheet in workbook.items():
        try:
            sheet_season = int(sheet_name.rsplit(" ", maxsplit=1)[-1])
        except ValueError:
            continue
        if sheet_season > season:
            continue
        for player_name, position, club in sheet.itertuples(index=False, name=None):
            key = normalize_player_name(player_name)
            if not key:
                continue
            previous = player_lookup.get(key)
            if previous is None or sheet_season > previous[0]:
                player_lookup[key] = (sheet_season, str(position), str(club))

    rows = []
    for player_name in PLAYERS:
        record = player_lookup.get(normalize_player_name(player_name))
        rows.append(
            {
                "player_name": player_name,
                "position": record[1].upper() if record else None,
                "team": record[2] if record else None,
            }
        )
    return pd.DataFrame(rows)


def _read_whoscored_schedule(
    whoscored: Any,
    force_cache: bool,
    issues: list[str],
) -> pd.DataFrame:
    try:
        schedule = whoscored.read_schedule(force_cache=force_cache).reset_index()
    except json.JSONDecodeError:
        issues.append(
            "WhoScored returned an empty or invalid JSON response for its schedule. "
            "Fixtures and recent appearances are still shown from ESPN; the "
            "WhoScored missing-player override could not be checked."
        )
        return pd.DataFrame(
            columns=["league", "home_team", "away_team", "date", "game_id"]
        )

    for column in ("league", "home_team", "away_team", "date", "game_id"):
        if column not in schedule.columns:
            schedule[column] = pd.Series(dtype="object")
    return schedule


def _read_whoscored_missing_players(
    whoscored: Any,
    match_ids: list[int],
    force_cache: bool,
    issues: list[str],
) -> pd.DataFrame:
    if not match_ids:
        return pd.DataFrame()
    try:
        return whoscored.read_missing_players(
            match_id=match_ids,
            force_cache=force_cache,
        )
    except json.JSONDecodeError:
        issues.append(
            "WhoScored returned an empty or invalid JSON response for missing-player "
            "reports. Expected-to-play percentages use recent appearances only."
        )
        return pd.DataFrame()


def _calculate_last_five_xg(understat_matches: pd.DataFrame) -> pd.DataFrame:
    """Average each team's xG across its five latest matches, irrespective of venue."""
    home_xg_rows = pd.DataFrame(
        {
            "league": understat_matches["league"],
            "team_key": understat_matches["home_team"].map(canonical_team_key),
            "date_utc": pd.to_datetime(
                understat_matches["date"], utc=True, errors="coerce"
            ),
            "xg": pd.to_numeric(understat_matches["home_xg"], errors="coerce"),
        }
    )
    away_xg_rows = pd.DataFrame(
        {
            "league": understat_matches["league"],
            "team_key": understat_matches["away_team"].map(canonical_team_key),
            "date_utc": pd.to_datetime(
                understat_matches["date"], utc=True, errors="coerce"
            ),
            "xg": pd.to_numeric(understat_matches["away_xg"], errors="coerce"),
        }
    )
    team_match_xg = pd.concat([home_xg_rows, away_xg_rows], ignore_index=True)
    team_match_xg = team_match_xg.dropna(subset=["xg", "date_utc"]).sort_values(
        "date_utc"
    )
    last_five_xg = (
        team_match_xg.groupby(["league", "team_key"], group_keys=False)
        .tail(5)
        .groupby(["league", "team_key"], as_index=False)["xg"]
        .mean()
    )
    last_five_xg["league_percentile"] = last_five_xg.groupby("league")["xg"].rank(
        pct=True
    )
    last_five_xg["difficulty"] = last_five_xg["league_percentile"].map(
        difficulty_from_percentile
    )
    return last_five_xg


def load_gameweek_data(
    workbook_path: Path,
    season: int,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, list[str]]:
    """Fetch current fixtures, recent appearances, venue xG, and the roster."""
    roster = _read_roster(workbook_path, season)
    team_contexts = {
        (LEAGUE_BY_TEAM[club], club)
        for club in roster["team"].dropna().unique()
        if club in LEAGUE_BY_TEAM
    }
    leagues = sorted({league for league, _ in team_contexts})
    if not leagues:
        raise ValueError("No roster teams could be matched to a supported league.")

    espn = sd.ESPN(leagues=leagues, seasons=season)
    whoscored = sd.WhoScored(leagues=leagues, seasons=season, headless=True)
    now_utc = pd.Timestamp.now(tz="UTC")
    use_cache = not force_refresh
    issues: list[str] = []

    espn_schedule = espn.read_schedule(force_cache=use_cache).reset_index()
    espn_schedule["date_utc"] = pd.to_datetime(
        espn_schedule["date"], utc=True, errors="coerce"
    )
    whoscored_schedule = _read_whoscored_schedule(
        whoscored,
        force_cache=use_cache,
        issues=issues,
    )
    whoscored_schedule["date_utc"] = pd.to_datetime(
        whoscored_schedule["date"], utc=True, errors="coerce"
    )

    understat = sd.Understat(leagues=leagues, seasons=season)
    understat_matches = understat.read_team_match_stats(force_cache=use_cache).reset_index()
    understat_matches["date_utc"] = pd.to_datetime(
        understat_matches["date"], utc=True, errors="coerce"
    )
    understat_matches = understat_matches[
        understat_matches["date_utc"] < now_utc
    ].copy()

    last_five_xg = _calculate_last_five_xg(understat_matches)
    xg_lookup = {
        (row.league, row.team_key): row.xg
        for row in last_five_xg.itertuples(index=False)
    }
    difficulty_lookup = {
        (row.league, row.team_key): row.difficulty
        for row in last_five_xg.itertuples(index=False)
    }

    fixture_plans: dict[tuple[str, str], dict[str, Any]] = {}
    for league, club_code in team_contexts:
        league_schedule = espn_schedule[espn_schedule["league"] == league].copy()
        club_fixtures = league_schedule[
            league_schedule["home_team"].map(lambda name: is_team(name, club_code))
            | league_schedule["away_team"].map(lambda name: is_team(name, club_code))
        ]
        upcoming = club_fixtures[
            club_fixtures["date_utc"] >= now_utc
        ].sort_values("date_utc")
        if upcoming.empty:
            issues.append(f"No upcoming fixture found for {club_code} ({league}).")
            continue

        next_match = upcoming.iloc[0]
        is_home = is_team(next_match["home_team"], club_code)
        team_name = next_match["home_team"] if is_home else next_match["away_team"]
        opponent = next_match["away_team"] if is_home else next_match["home_team"]
        venue = "Home" if is_home else "Away"
        recent_matches = club_fixtures[
            club_fixtures["date_utc"] < next_match["date_utc"]
        ].sort_values("date_utc", ascending=False).head(4)
        fixture_plans[(league, club_code)] = {
            "opponent": opponent,
            "team_name": team_name,
            "next_date": next_match["date_utc"],
            "venue": venue,
            "recent_matches": recent_matches,
        }
        if len(recent_matches) < 4:
            issues.append(
                f"{club_code} ({league}): only {len(recent_matches)} recent fixture(s) available."
            )

    recent_match_ids = list(
        dict.fromkeys(
            int(match_id)
            for plan in fixture_plans.values()
            for match_id in plan["recent_matches"]["game_id"].dropna()
        )
    )
    lineup_rows: list[dict[str, Any]] = []
    matches = espn_schedule[espn_schedule["game_id"].isin(recent_match_ids)]
    for match in matches.itertuples(index=False):
        game_id = int(match.game_id)
        url = (
            "http://site.api.espn.com/apis/site/v2/sports/soccer/"
            f"{match.league_id}/summary?event={game_id}"
        )
        summary = json.load(espn.get(url, espn.data_dir / f"Summary_{game_id}.json"))
        for roster_group in summary.get("rosters", []):
            team_name = roster_group.get("team", {}).get("displayName")
            for player in roster_group.get("roster", []):
                subbed_in = player.get("subbedIn", False)
                entered = (
                    subbed_in.get("didSub", False)
                    if isinstance(subbed_in, dict)
                    else bool(subbed_in)
                )
                lineup_rows.append(
                    {
                        "league": match.league,
                        "game": match.game,
                        "team": team_name,
                        "player": player["athlete"]["displayName"],
                        "played": bool(player.get("starter", False)) or entered,
                    }
                )
    lineups = pd.DataFrame(lineup_rows)
    if not recent_match_ids:
        issues.append("No recent match IDs were available to estimate player availability.")
    elif lineups.empty:
        issues.append("Recent ESPN lineups were unavailable; expected-to-play values are blank.")

    who_scored_ids = []
    for (league, club_code), plan in fixture_plans.items():
        schedule = whoscored_schedule[whoscored_schedule["league"] == league].copy()
        candidates = schedule[
            schedule["home_team"].map(lambda name: is_team(name, club_code))
            | schedule["away_team"].map(lambda name: is_team(name, club_code))
        ].copy()
        candidates["date_gap"] = (candidates["date_utc"] - plan["next_date"]).abs()
        candidates = candidates[
            candidates["date_gap"] <= pd.Timedelta(days=3)
        ].sort_values("date_gap")
        if candidates.empty:
            issues.append(f"WhoScored fixture not matched for {club_code} ({league}).")
        else:
            who_scored_ids.append(int(candidates.iloc[0]["game_id"]))

    missing_players = _read_whoscored_missing_players(
        whoscored,
        match_ids=list(dict.fromkeys(who_scored_ids)),
        force_cache=use_cache,
        issues=issues,
    )
    missing_player_keys = set()
    if not missing_players.empty:
        for row in missing_players.reset_index().itertuples(index=False):
            for league, club_code in team_contexts:
                if row.league == league and is_team(row.team, club_code):
                    missing_player_keys.add(
                        (league, club_code, normalize_player_name(row.player))
                    )

    def expected_probability(
        player_name: str, league: str, club_code: str
    ) -> float | None:
        plan = fixture_plans.get((league, club_code))
        if plan is None or lineups.empty:
            return None
        player_key = normalize_player_name(player_name)
        played_count = observed_count = 0
        for match in plan["recent_matches"].itertuples(index=False):
            rows = lineups[
                (lineups["league"] == league)
                & (lineups["game"] == match.game)
                & lineups["team"].map(lambda name: is_team(name, club_code))
            ]
            if rows.empty:
                continue
            observed_count += 1
            appeared = rows[
                rows["player"].map(normalize_player_name) == player_key
            ]["played"]
            if not appeared.empty and appeared.any():
                played_count += 1
        if observed_count == 0:
            return None
        if (league, club_code, player_key) in missing_player_keys:
            return 0.0
        return played_count / observed_count

    rows = []
    for player in roster.to_dict(orient="records"):
        result = {
            **player,
            "team_full_name": None,
            "fixture_time": None,
            "venue": None,
            "team_xg": None,
            "opponent_xg": None,
            "opposition_difficulty": None,
            "expected_to_play": None,
            "opponent": None,
        }
        club_code = player["team"]
        league = LEAGUE_BY_TEAM.get(club_code)
        if league is None:
            issues.append(
                f"No current team/league mapping found for {player['player_name']}."
            )
            rows.append(result)
            continue

        plan = fixture_plans.get((league, club_code))
        if plan is None:
            rows.append(result)
            continue

        team_key = canonical_team_key(plan["team_name"])
        opponent_key = canonical_team_key(plan["opponent"])
        result.update(
            {
                "team_full_name": plan["team_name"],
                "fixture_time": plan["next_date"]
                .tz_convert(ZoneInfo("Europe/Rome"))
                .strftime("%Y-%m-%d %H:%M %Z"),
                "venue": plan["venue"],
                "team_xg": xg_lookup.get((league, team_key)),
                "opponent_xg": xg_lookup.get((league, opponent_key)),
                "opposition_difficulty": difficulty_lookup.get(
                    (league, opponent_key)
                ),
                "expected_to_play": expected_probability(
                    player["player_name"], league, club_code
                ),
                "opponent": plan["opponent"],
            }
        )
        rows.append(result)

    return pd.DataFrame(rows), list(dict.fromkeys(issues))
