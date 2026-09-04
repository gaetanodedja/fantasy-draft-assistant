"""
Fantasy Draft Assistant - Main Streamlit App
A real-time draft recommendation engine powered by LightGBM position models.
"""

import sys
import warnings
import base64
from pathlib import Path

import streamlit as st
import pandas as pd

warnings.filterwarnings("ignore")

# Add src to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from config import DATASET_PATH, DEFAULT_LEAGUE_BUDGET, TEAM_COUNT
from src.recommendations import RecommendationEngine
from src.league import LeagueManager
from src.models import Player
from src.optimizer import BestElevenOptimizer, FORMATIONS


def apply_soccer_field_background():
    """Add subtle pitch markings behind the Streamlit application."""
    pitch_svg = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 800'>
        <rect width='1200' height='800' fill='#173f2a'/>
        <path d='M0 80H1200 M0 240H1200 M0 400H1200 M0 560H1200 M0 720H1200'
              stroke='#2f6642' stroke-width='3' opacity='.42'/>
        <g fill='none' stroke='#91bd82' stroke-width='4' opacity='.34'>
          <rect x='38' y='38' width='1124' height='724' rx='4'/>
          <path d='M600 38V762 M38 400H1162'/>
          <circle cx='600' cy='400' r='92'/>
          <circle cx='600' cy='400' r='7' fill='#91bd82'/>
          <path d='M38 245H190V555H38 M1162 245H1010V555H1162'/>
          <path d='M38 315H112V485H38 M1162 315H1088V485H1162'/>
          <path d='M190 335H228V465H190 M1010 335H972V465H1010'/>
        </g>
        <g stroke='#d5e8c8' stroke-width='2' opacity='.16'>
          <path d='M100 38V762 M300 38V762 M900 38V762 M1100 38V762'/>
        </g>
      </svg>"""
    pitch_data = base64.b64encode(pitch_svg.encode("utf-8")).decode("ascii")
    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background-color: #102d1f;
            background-image: linear-gradient(rgba(8, 22, 15, 0.58), rgba(8, 22, 15, 0.58)),
                url("data:image/svg+xml;base64,{pitch_data}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        [data-testid="stHeader"] {{
            background: rgba(8, 22, 15, 0.42);
        }}
        [data-testid="stSidebar"] {{
            background: rgba(10, 24, 18, 0.9);
        }}
        [data-testid="stMainBlockContainer"] {{
            background: rgba(8, 22, 15, 0.52);
            border-radius: 12px;
            padding: 2rem 2.5rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_session_state():
    """Initialize Streamlit session state."""
    if "recommendation_engine" not in st.session_state:
        st.session_state.recommendation_engine = RecommendationEngine(str(DATASET_PATH))
    
    if "league_manager" not in st.session_state:
        league = LeagueManager(team_count=TEAM_COUNT, league_budget_limit=DEFAULT_LEAGUE_BUDGET)
        league.create_teams([f"Team {i}" for i in range(1, TEAM_COUNT + 1)])
        st.session_state.league_manager = league
    
    if "current_view" not in st.session_state:
        st.session_state.current_view = "home"


def sidebar_navigation():
    """Render sidebar navigation."""
    st.sidebar.title("Fantasy Draft Assistant")
    st.sidebar.divider()
    navigation_options = ["Home", "Rankings", "Player Profile", "Best Eleven", "Draft Tracker", "Teams", "Save / Load"]
    requested_page = st.session_state.pop("requested_page", None)
    if requested_page in navigation_options:
        st.session_state["nav_radio"] = requested_page
    nav_option = st.sidebar.radio(
        "Navigate",
        navigation_options,
        key="nav_radio"
    )
    return {
        "Home": "home",
        "Rankings": "rankings",
        "Player Profile": "player_profile",
        "Best Eleven": "best_eleven",
        "Draft Tracker": "draft_tracker",
        "Teams": "teams",
        "Save / Load": "save_load",
    }[nav_option]


def open_player_profile(player_name: str, season: str) -> None:
    """Navigate to Player Profile with a player preselected."""
    st.session_state["profile_target_player"] = player_name
    st.session_state["profile_target_season"] = season
    st.session_state["requested_page"] = "Player Profile"
    st.rerun()


def home_page():
    """Home page with team setup and projected standings."""
    st.title("Fantasy Draft Assistant")
    st.markdown("""
    Welcome to your AI-powered draft companion. This tool uses machine learning to:
    - **Predict player value** based on historical stats and league trends
    - **Rank players** by position with projected avg scores
    - **Track your draft** in real-time with budget management
    - **Recommend picks** to maximize team value
    """)
    
    league = st.session_state.league_manager

    with st.expander("Set team names", expanded=True):
        with st.form("home_rename_teams_form"):
            renamed_teams = {
                team_id: st.text_input(team.name, value=team.name, key=f"home_rename_{team_id}")
                for team_id, team in league.state.teams.items()
            }
            save_names = st.form_submit_button("Save team names")
        if save_names:
            try:
                league.rename_teams(renamed_teams)
                st.success("Team names updated.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))

    standings = pd.DataFrame([
        {
            "Rank": rank,
            "Team": team.name,
            "Total Projected Avg": league.team_projected_points(team_id),
            "Budget Remaining": team.budget_remaining,
        }
        for rank, (team_id, team) in enumerate(
            sorted(
                league.state.teams.items(),
                key=lambda item: league.team_projected_points(item[0]),
                reverse=True,
            ),
            start=1,
        )
    ])
    st.subheader("Projected Standings")
    st.dataframe(standings, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Quick Start")
    st.markdown("""
    1. Go to **Rankings** to see top players by position
    2. Visit **Draft Tracker** to make picks and track budget
    3. Check **Teams** to see all team rosters
    """)


def rankings_page():
    """Show top available players, full statistics, and feature importance by position."""
    st.title("Player Rankings")
    engine = st.session_state.recommendation_engine
    league = st.session_state.league_manager
    top_n = st.slider("Top N suggestions per position", 5, 50, 15, 5, key="top_n_slider")
    season_choice = st.selectbox(
        "Player season",
        ["All seasons"] + sorted(engine.engine.raw_data["season"].dropna().astype(str).unique(), reverse=True),
        key="ranking_season",
    )
    selected_season = None if season_choice == "All seasons" else season_choice
    drafted_player_names = [
        player.name
        for team in league.state.teams.values()
        for player in team.roster.values()
    ]
    st.divider()
    for position in ["FW", "MID", "DEF", "GK"]:
        rankings_df = engine.top_players_by_position(
            position,
            top_n=top_n,
            excluded_player_names=drafted_player_names,
            season=selected_season,
        )
        st.subheader(f"{position} Suggestions")
        if rankings_df.empty:
            st.info(f"No available {position} players remain.")
            continue

        display_df = rankings_df.copy()
        display_df["Rank"] = range(1, len(display_df) + 1)
        display_df = display_df[["Rank"] + [column for column in display_df.columns if column != "Rank"]]
        display_df = display_df.rename(columns={"Avg": "Actual Avg", "projected_avg": "Projected Avg"})

        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.caption("Select a player to open their profile.")
        player_columns = st.columns(min(len(rankings_df), 5))
        for player_index, (_, player_row) in enumerate(rankings_df.iterrows()):
            with player_columns[player_index % len(player_columns)]:
                if st.button(
                    player_row["Player"],
                    key=f"open_profile_{position}_{player_index}",
                    use_container_width=True,
                ):
                    open_player_profile(
                        str(player_row["Player"]),
                        str(player_row["season"]),
                    )

        importance_df = engine.get_feature_importance(position).head(10).reset_index()
        importance_df.columns = ["Feature", "Importance"]
        st.caption(f"Top features for {position}")
        st.bar_chart(importance_df.set_index("Feature"))


def player_profile_page():
    """Show a player's statistics and percentile rank within their peer group."""
    st.title("Player Profile")
    engine = st.session_state.recommendation_engine.engine
    data = engine.raw_data

    target_season = st.session_state.pop("profile_target_season", None)
    target_player = st.session_state.pop("profile_target_player", None)
    season_options = sorted(data["season"].dropna().astype(str).unique(), reverse=True)
    if target_season in season_options:
        st.session_state["profile_season"] = target_season

    season_choice = st.selectbox(
        "Player season",
        season_options,
        key="profile_season",
    )
    season_data = data[data["season"].astype(str) == season_choice].copy()
    player_options = sorted(season_data["Player"].dropna().astype(str).unique())
    if target_player in player_options:
        st.session_state["profile_player"] = target_player
    player_name = st.selectbox(
        "Player",
        player_options,
        key="profile_player",
    )
    player_rows = season_data[season_data["Player"] == player_name]
    player = player_rows.sort_values("Avg", ascending=False).iloc[0]
    position = str(player["Pos"])
    position_data = season_data[season_data["Pos"] == position].copy()

    st.subheader(f"{player_name} | {position} | {player['Club']}")
    st.caption(f"Season: {season_choice} | Peer group: {position} players in {season_choice}")
    st.dataframe(
        pd.DataFrame([{
            "Player": player_name,
            "Position": position,
            "Club": player["Club"],
            "Actual Avg": player["Avg"],
            "Price": player["Price"],
        }]),
        use_container_width=True,
        hide_index=True,
    )

    stat_columns = [
        column for column in position_data.columns
        if column not in {"Player", "Pos", "Club", "Avg", "Price", "sheet_name", "league", "season"}
        and pd.api.types.is_numeric_dtype(position_data[column])
    ]
    position_model = st.session_state.recommendation_engine.engine.position_models.get(position)
    if position_model is None:
        position_model = st.session_state.recommendation_engine.engine.train_position_model(position)
    feature_importance = position_model["feature_importance"]
    total_importance = float(feature_importance.sum())
    profile_stats = []
    for column in ["Avg"] + stat_columns:
        peer_values = pd.to_numeric(position_data[column], errors="coerce").dropna()
        player_value = pd.to_numeric(pd.Series([player[column]]), errors="coerce").iloc[0]
        if pd.isna(player_value) or peer_values.empty:
            percentile = None
        else:
            percentile = float((peer_values <= player_value).mean() * 100)
        raw_importance = float(feature_importance.get(column, 0.0))
        model_weight = (raw_importance / total_importance * 100) if total_importance else None
        profile_stats.append({
            "Statistic": column,
            "Value": player_value,
            "Percentile": percentile,
            "Model Weight": model_weight,
        })

    stats_df = pd.DataFrame(profile_stats)
    st.subheader("Statistics and Percentiles")
    st.dataframe(
        stats_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Value": st.column_config.NumberColumn("Value", format="%.2f"),
            "Percentile": st.column_config.ProgressColumn(
                "Percentile",
                help="Percentile compared with players in the same position and season.",
                min_value=0,
                max_value=100,
                format="%.1f%%",
            ),
            "Model Weight": st.column_config.NumberColumn(
                "Model Weight",
                help="This statistic's share of total LightGBM feature importance for the player's position.",
                format="%.1f%%",
            ),
        },
    )


def best_eleven_page():
    """Build the strongest valid eleven from players not yet picked."""
    st.title("Best Eleven")
    league = st.session_state.league_manager
    team_id = st.selectbox(
        "Team",
        list(league.state.teams.keys()),
        index=0,
        format_func=lambda value: league.state.teams[value].name,
        key="best_eleven_team",
    )
    selected_team = league.state.teams[team_id]
    my_team_players = list(selected_team.roster.values())
    opponent_player_names = [
        player.name
        for other_team_id, team in league.state.teams.items()
        if other_team_id != team_id
        for player in team.roster.values()
    ]
    optimizer = BestElevenOptimizer(st.session_state.recommendation_engine)
    formation_choice = st.selectbox(
        "Formation",
        ["Best formation"] + list(FORMATIONS),
        key="best_eleven_formation",
    )
    season_choice = st.selectbox(
        "Player season",
        ["All seasons"] + sorted(st.session_state.recommendation_engine.engine.raw_data["season"].dropna().astype(str).unique(), reverse=True),
        key="best_eleven_season",
    )
    try:
        result = optimizer.optimize(
            my_team_players,
            opponent_player_names,
            None if formation_choice == "Best formation" else formation_choice,
            None if season_choice == "All seasons" else season_choice,
        )
    except ValueError as error:
        st.warning(str(error))
        return

    st.subheader(f"{league.state.teams[team_id].name}: {result['formation']}")
    st.metric("Total Projected Avg", f"{result['total_projected_avg']:.2f}")
    lineup = result["lineup"].copy()
    lineup["Role"] = lineup["Pos"].map({"GK": "Goalkeeper", "DEF": "Defender", "MID": "Midfielder", "FW": "Forward"})
    lineup = lineup[["Role"] + [column for column in lineup.columns if column != "Role"]]
    lineup = lineup.rename(columns={"Avg": "Actual Avg", "projected_avg": "Projected Avg"})

    st.dataframe(lineup, use_container_width=True, hide_index=True)
    st.caption("Your picked players are included automatically; the remaining positions are filled from players not picked by opponents.")


def save_load_page():
    """Export or restore the current league state as JSON."""
    st.title("Save / Load Draft")
    league = st.session_state.league_manager
    state_json = league.export_state()
    st.download_button(
        "Download current draft",
        data=state_json,
        file_name="fantasy_draft_state.json",
        mime="application/json",
    )
    uploaded_file = st.file_uploader("Load a saved draft", type="json")
    if uploaded_file is not None and st.button("Restore draft", key="restore_draft"):
        try:
            league.import_state(uploaded_file.getvalue().decode("utf-8"))
            st.success("Draft restored.")
            st.rerun()
        except (UnicodeDecodeError, ValueError, KeyError, TypeError) as error:
            st.error(f"Could not restore draft: {error}")


def draft_tracker_page():
    """Select any available player and record the winning auction bid."""
    st.title("Draft Tracker")
    
    engine = st.session_state.recommendation_engine
    league = st.session_state.league_manager
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        position = st.selectbox("Filter by Position", ["All", "FW", "MID", "DEF", "GK"], key="draft_position_select")
    
    with col2:
        team_id = st.selectbox(
            "My Team",
            list(league.state.teams.keys()),
            format_func=lambda x: league.state.teams[x].name,
            key="team_select"
        )
    
    st.divider()
    selected_team = league.state.teams[team_id]
    st.subheader(f"{selected_team.name} - Budget: ${selected_team.budget_remaining:.2f}")
    drafted_player_names = [
        player.name
        for team in league.state.teams.values()
        for player in team.roster.values()
    ]
    
    positions = ["FW", "MID", "DEF", "GK"] if position == "All" else [position]
    available_frames = [
        engine.top_players_by_position(pos, top_n=len(engine.engine.raw_data), excluded_player_names=drafted_player_names)
        for pos in positions
    ]
    available_players = pd.concat(available_frames, ignore_index=True).drop_duplicates("Player")
    search = st.text_input("Search available players")
    if search.strip():
        available_players = available_players[
            available_players["Player"].str.contains(search.strip(), case=False, na=False)
        ]
    if available_players.empty:
        st.info("No available players match your filters.")
        return
    selected_name = st.selectbox("Player to auction", available_players["Player"].tolist(), key="draft_player_select")
    row = available_players[available_players["Player"] == selected_name].iloc[0]
    st.dataframe(pd.DataFrame([row]), use_container_width=True, hide_index=True)
    bid = st.number_input("Winning auction bid", min_value=0.0, max_value=float(selected_team.budget_remaining), value=0.0, step=1.0, key="draft_bid")
    if st.button("Record pick", key="record_pick"):
        if bid <= 0:
            st.error("Enter the winning auction bid first.")
        else:
            player = Player(
                player_id=f"{row['Player']}_{row['Pos']}", name=row["Player"], position=row["Pos"],
                club=row["Club"], season="2026", projected_avg=float(row["projected_avg"]), price=float(bid),
            )
            league.add_pick(team_id, player)
            st.success(f"Picked {row['Player']}!")
            st.rerun()


def teams_page():
    """Show each team's roster, budget, and projected standings."""
    st.title("Teams")
    
    league = st.session_state.league_manager

    st.subheader("Team Rosters")

    standings = pd.DataFrame([
        {
            "Team": team.name,
            "Total Projected Avg": league.team_projected_points(team_id),
            "Budget Remaining": team.budget_remaining,
        }
        for team_id, team in league.state.teams.items()
    ]).sort_values("Total Projected Avg", ascending=False)
    st.subheader("Projected Standings")
    st.dataframe(standings, use_container_width=True, hide_index=True)
    
    for team_id, team in league.state.teams.items():
        with st.expander(f"{team.name} (${team.budget_remaining:.2f} left)"):
            if team.roster:
                roster_data = {
                    "Player": [p.name for p in team.roster.values()],
                    "Position": [p.position for p in team.roster.values()],
                    "Price": [p.price for p in team.roster.values()],
                    "Projected Avg": [p.projected_avg for p in team.roster.values()],
                }
                st.dataframe(pd.DataFrame(roster_data), use_container_width=True, hide_index=True)
            else:
                st.info("No picks yet")


def main():
    """Main app."""
    st.set_page_config(
        page_title="Fantasy Draft Assistant",
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    apply_soccer_field_background()
    
    init_session_state()
    
    nav = sidebar_navigation()
    
    if nav == "home":
        home_page()
    elif nav == "rankings":
        rankings_page()
    elif nav == "player_profile":
        player_profile_page()
    elif nav == "best_eleven":
        best_eleven_page()
    elif nav == "draft_tracker":
        draft_tracker_page()
    elif nav == "teams":
        teams_page()
    elif nav == "save_load":
        save_load_page()


if __name__ == "__main__":
    main()
