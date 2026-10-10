import json
from pathlib import Path

import pandas as pd

from formation_assistant.data_service import (
    DIFFICULTY_LEVELS,
    FORMATIONS,
    _read_roster,
    _read_whoscored_missing_players,
    _read_whoscored_schedule,
    _calculate_last_five_xg,
    canonical_team_key,
    difficulty_from_percentile,
    normalize_player_name,
)


def test_player_name_normalization_ignores_accents_and_leading_numbers():
    assert normalize_player_name("10 Jérémy Jacquet") == "jeremy jacquet"


def test_team_aliases_resolve_to_known_roster_code():
    assert canonical_team_key("Brighton and Hove Albion") == "BHA"


def test_difficulty_bands_map_low_xg_to_easy_and_high_xg_to_hard():
    assert difficulty_from_percentile(0.2) == "very easy"
    assert difficulty_from_percentile(0.4) == "easy"
    assert difficulty_from_percentile(0.6) == "average"
    assert difficulty_from_percentile(0.8) == "hard"
    assert difficulty_from_percentile(1.0) == "very hard"
    assert len(DIFFICULTY_LEVELS) == 5


def test_supported_formations_all_select_eleven_players():
    assert all(sum(slots.values()) == 11 for slots in FORMATIONS.values())


def test_roster_loads_positions_for_players_mapped_in_the_workbook():
    project_root = Path(__file__).resolve().parents[2]
    roster = _read_roster(project_root / "data" / "fantasy_data.xlsx", 2026)
    assert len(roster) == 20
    assert roster["position"].notna().sum() == 19
    assert roster.loc[roster["player_name"] == "Matija Katic", "position"].isna().all()


class _InvalidWhoScoredResponse:
    def read_schedule(self, force_cache: bool = False):
        raise json.JSONDecodeError("Expecting value", "", 0)

    def read_missing_players(self, match_id: list[int], force_cache: bool = False):
        raise json.JSONDecodeError("Expecting value", "", 0)


def test_invalid_whoscored_schedule_json_is_reported_without_stopping_refresh():
    issues = []
    schedule = _read_whoscored_schedule(
        _InvalidWhoScoredResponse(),
        force_cache=False,
        issues=issues,
    )

    assert schedule.empty
    assert {"league", "home_team", "away_team", "date", "game_id"}.issubset(
        schedule.columns
    )
    assert len(issues) == 1
    assert "empty or invalid JSON" in issues[0]
    assert "ESPN" in issues[0]


def test_invalid_whoscored_missing_player_json_is_reported_and_returns_no_override():
    issues = []
    missing_players = _read_whoscored_missing_players(
        _InvalidWhoScoredResponse(),
        match_ids=[123],
        force_cache=False,
        issues=issues,
    )

    assert missing_players.empty
    assert len(issues) == 1
    assert "recent appearances only" in issues[0]


def test_xg_averages_last_five_matches_across_both_venues():
    matches = []
    for index in range(7):
        matches.append(
            {
                "league": "test-league",
                "date": f"2026-01-{index + 1:02d}",
                "home_team": "Alpha FC" if index % 2 == 0 else "Opponent FC",
                "away_team": "Opponent FC" if index % 2 == 0 else "Alpha FC",
                "home_xg": 1.0 + index if index % 2 == 0 else 2.0 + index,
                "away_xg": 2.0 + index if index % 2 == 0 else 1.0 + index,
            }
        )

    averages = _calculate_last_five_xg(pd.DataFrame(matches))
    alpha = averages.loc[
        (averages["league"] == "test-league")
        & (averages["team_key"] == "alphafc"),
        "xg",
    ].item()
    expected_alpha = sum([3.0, 4.0, 5.0, 6.0, 7.0]) / 5

    assert alpha == expected_alpha
    assert "venue" not in averages.columns
