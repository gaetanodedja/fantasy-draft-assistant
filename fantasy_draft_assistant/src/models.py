from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Player:
    player_id: str
    name: str
    position: str
    club: str
    season: str
    stats: Dict[str, float] = field(default_factory=dict)
    projected_avg: float = 0.0
    price: float = 0.0
    available: bool = True


@dataclass
class DraftPick:
    round: int
    pick_number: int
    team_id: str
    player_id: str
    player_name: str
    price: float
    timestamp: str


@dataclass
class Team:
    team_id: str
    name: str
    budget_remaining: float
    roster: Dict[str, Player] = field(default_factory=dict)
    starters: Dict[str, Player] = field(default_factory=dict)
    bench: Dict[str, Player] = field(default_factory=dict)
    picks: List[DraftPick] = field(default_factory=list)


@dataclass
class LeagueState:
    teams: Dict[str, Team]
    draft_order: List[str]
    remaining_players: List[Player]
    draft_log: List[DraftPick]
    current_round: int = 1
    current_pick: int = 1
    league_budget_limit: float = 100.0
