from __future__ import annotations

import json
from typing import Dict, List

from .models import LeagueState, Player, Team


class LeagueManager:
    def __init__(self, team_count: int = 20, league_budget_limit: float = 1000.0):
        self.team_count = team_count
        self.league_budget_limit = league_budget_limit
        self.state = LeagueState(
            teams={},
            draft_order=[],
            remaining_players=[],
            draft_log=[],
            current_round=1,
            current_pick=1,
            league_budget_limit=league_budget_limit,
        )

    def create_teams(self, names: List[str] | None = None) -> Dict[str, Team]:
        names = names or [f"Team {i}" for i in range(1, self.team_count + 1)]
        self.state.teams = {}
        for name in names:
            team_id = name.lower().replace(" ", "_")
            self.state.teams[team_id] = Team(
                team_id=team_id,
                name=name,
                budget_remaining=self.league_budget_limit,
            )
        self.state.draft_order = list(self.state.teams.keys())
        return self.state.teams

    def add_pick(self, team_id: str, player: Player) -> None:
        team = self.state.teams.get(team_id)
        if team is None:
            raise ValueError(f"Unknown team: {team_id}")
        if player.price > team.budget_remaining:
            raise ValueError(f"Player {player.name} exceeds team budget.")
        team.budget_remaining -= player.price
        team.roster[player.player_id] = player
        self.state.remaining_players = [p for p in self.state.remaining_players if p.player_id != player.player_id]

    def rename_team(self, team_id: str, new_name: str) -> None:
        team = self.state.teams.get(team_id)
        cleaned_name = new_name.strip()
        if team is None:
            raise ValueError(f"Unknown team: {team_id}")
        if not cleaned_name:
            raise ValueError("Team name cannot be empty.")
        if any(other.name.casefold() == cleaned_name.casefold() for other in self.state.teams.values() if other.team_id != team_id):
            raise ValueError("Team names must be unique.")
        team.name = cleaned_name

    def rename_teams(self, names: Dict[str, str]) -> None:
        cleaned_names = {team_id: name.strip() for team_id, name in names.items()}
        if set(cleaned_names) != set(self.state.teams):
            raise ValueError("Team rename data does not match the current league.")
        if any(not name for name in cleaned_names.values()):
            raise ValueError("Team name cannot be empty.")
        normalized_names = [name.casefold() for name in cleaned_names.values()]
        if len(normalized_names) != len(set(normalized_names)):
            raise ValueError("Team names must be unique.")
        for team_id, name in cleaned_names.items():
            self.state.teams[team_id].name = name

    def team_projected_points(self, team_id: str) -> float:
        team = self.state.teams.get(team_id)
        if team is None:
            raise ValueError(f"Unknown team: {team_id}")
        return sum(player.projected_avg for player in team.roster.values())

    def export_state(self) -> str:
        payload = {
            "team_count": self.team_count,
            "league_budget_limit": self.league_budget_limit,
            "draft_order": self.state.draft_order,
            "current_round": self.state.current_round,
            "current_pick": self.state.current_pick,
            "teams": {
                team_id: {
                    "team_id": team.team_id,
                    "name": team.name,
                    "budget_remaining": team.budget_remaining,
                    "roster": [
                        {
                            "player_id": player.player_id,
                            "name": player.name,
                            "position": player.position,
                            "club": player.club,
                            "season": player.season,
                            "stats": player.stats,
                            "projected_avg": player.projected_avg,
                            "price": player.price,
                            "available": player.available,
                        }
                        for player in team.roster.values()
                    ],
                }
                for team_id, team in self.state.teams.items()
            },
        }
        return json.dumps(payload, indent=2)

    def import_state(self, serialized_state: str) -> None:
        payload = json.loads(serialized_state)
        teams = {}
        for team_id, team_data in payload["teams"].items():
            team = Team(
                team_id=team_data["team_id"],
                name=team_data["name"],
                budget_remaining=float(team_data["budget_remaining"]),
            )
            for player_data in team_data["roster"]:
                player = Player(**player_data)
                team.roster[player.player_id] = player
            teams[team_id] = team

        self.team_count = int(payload["team_count"])
        self.league_budget_limit = float(payload["league_budget_limit"])
        self.state.teams = teams
        self.state.draft_order = list(payload["draft_order"])
        self.state.current_round = int(payload["current_round"])
        self.state.current_pick = int(payload["current_pick"])
        self.state.league_budget_limit = self.league_budget_limit
