from __future__ import annotations

from typing import Dict, List

import pandas as pd

from .engine import DraftModelEngine


class RecommendationEngine:
    def __init__(self, dataset_path: str):
        self.engine = DraftModelEngine(dataset_path)

    def top_players_by_position(
        self,
        position: str,
        top_n: int = 10,
        excluded_player_names: List[str] | None = None,
        season: str | None = None,
    ) -> pd.DataFrame:
        rankings = self.engine.rank_players(position, top_n=len(self.engine.raw_data))
        if season is not None:
            rankings = rankings[rankings["season"].astype(str).str.strip() == season]
        excluded = {name.casefold() for name in (excluded_player_names or [])}
        if excluded:
            rankings = rankings[
                ~rankings["Player"].astype(str).str.casefold().isin(excluded)
            ]
        return rankings.head(top_n).reset_index(drop=True)

    def get_feature_importance(self, position: str) -> pd.Series:
        if position.upper() not in self.engine.position_models:
            self.engine.train_position_model(position)
        return self.engine.position_models[position.upper()]["feature_importance"]

    def get_all_position_rankings(self, top_n: int = 10) -> Dict[str, pd.DataFrame]:
        rankings: Dict[str, pd.DataFrame] = {}
        for position in sorted(self.engine.raw_data["Pos"].dropna().astype(str).str.upper().unique()):
            rankings[position] = self.top_players_by_position(position, top_n=top_n)
        return rankings

    def compare_players(self, position: str, player_names: List[str]) -> pd.DataFrame:
        rankings = self.engine.rank_players(position, top_n=len(self.engine.raw_data))
        selected = rankings[rankings["Player"].isin(player_names)].copy()
        selected = selected.sort_values("projected_avg", ascending=False)
        return selected.drop_duplicates(subset=["Player"], keep="first").reset_index(drop=True)
