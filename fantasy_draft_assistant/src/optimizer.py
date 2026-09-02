from __future__ import annotations

from typing import Dict, List

import pandas as pd

from .recommendations import RecommendationEngine
from .models import Player


FORMATIONS: Dict[str, Dict[str, int]] = {
    "3-4-3": {"DEF": 3, "MID": 4, "FW": 3, "GK": 1},
    "3-5-2": {"DEF": 3, "MID": 5, "FW": 2, "GK": 1},
    "4-3-3": {"DEF": 4, "MID": 3, "FW": 3, "GK": 1},
    "4-4-2": {"DEF": 4, "MID": 4, "FW": 2, "GK": 1},
    "4-5-1": {"DEF": 4, "MID": 5, "FW": 1, "GK": 1},
    "5-3-2": {"DEF": 5, "MID": 3, "FW": 2, "GK": 1},
    "5-4-1": {"DEF": 5, "MID": 4, "FW": 1, "GK": 1},
}


class BestElevenOptimizer:
    """Find the highest projected eleven from currently available players."""

    def __init__(self, recommendation_engine: RecommendationEngine):
        self.recommendation_engine = recommendation_engine

    def _ranked_players(self, season: str | None = None) -> pd.DataFrame:
        frames = []
        for position in ["FW", "MID", "DEF", "GK"]:
            rankings = self.recommendation_engine.engine.rank_players(
                position,
                top_n=len(self.recommendation_engine.engine.raw_data),
            )
            if season is not None:
                rankings = rankings[rankings["season"].astype(str).str.strip() == season]
            frames.append(rankings)
        return pd.concat(frames, ignore_index=True).sort_values("projected_avg", ascending=False).drop_duplicates(
            subset=["Player"], keep="first"
        )

    def optimize(
        self,
        team_players: List[Player],
        opponent_player_names: List[str],
        formation: str | None = None,
        season: str | None = None,
    ) -> dict:
        ranked_players = self._ranked_players(season)
        opponent_names = {name.casefold() for name in opponent_player_names}
        team_names = {player.name.casefold() for player in team_players}
        available = ranked_players[
            ~ranked_players["Player"].astype(str).str.casefold().isin(opponent_names | team_names)
        ]
        owned_rows = []
        for player in team_players:
            matching_rows = ranked_players[
                (ranked_players["Player"].astype(str).str.casefold() == player.name.casefold())
                & (ranked_players["Pos"] == player.position.upper())
            ]
            if matching_rows.empty:
                owned_rows.append(
                    pd.DataFrame([{
                        "Player": player.name,
                        "Pos": player.position.upper(),
                        "Club": player.club,
                        "Avg": float("nan"),
                        "Price": player.price,
                        "projected_avg": player.projected_avg,
                    }])
                )
            else:
                owned_row = matching_rows.head(1).copy()
                owned_row["Price"] = player.price
                owned_row["projected_avg"] = player.projected_avg
                owned_rows.append(owned_row)
        owned = pd.concat(owned_rows, ignore_index=True) if owned_rows else pd.DataFrame(columns=ranked_players.columns)
        candidates = []

        formations_to_check = [formation] if formation else list(FORMATIONS)
        for selected_formation in formations_to_check:
            requirements = FORMATIONS[selected_formation]
            selected = []
            possible = True
            for position, count in requirements.items():
                owned_players = owned[owned["Pos"] == position]
                if len(owned_players) > count:
                    possible = False
                    break
                open_slots = count - len(owned_players)
                available_players = available[available["Pos"] == position].head(open_slots)
                if len(available_players) < open_slots:
                    possible = False
                    break
                selected.append(pd.concat([owned_players, available_players], ignore_index=True))
            if possible:
                lineup = pd.concat(selected, ignore_index=True)
                candidates.append(
                    {
                        "formation": selected_formation,
                        "requirements": requirements,
                        "lineup": lineup,
                        "total_projected_avg": float(lineup["projected_avg"].sum()),
                    }
                )

        if not candidates:
            if formation:
                raise ValueError(f"Formation {formation} cannot be completed with the current roster and available players.")
            raise ValueError("Not enough available players to create a valid eleven.")
        return max(candidates, key=lambda candidate: candidate["total_projected_avg"])
