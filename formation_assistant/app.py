from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from data_service import FORMATIONS, POSITION_ORDER, load_gameweek_data


APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
WORKBOOK_PATH = PROJECT_DIR / "data" / "fantasy_data.xlsx"
CACHE_PATH = APP_DIR / ".cache" / "gameweek.json"
SEASON = datetime.now().year if datetime.now().month >= 7 else datetime.now().year - 1
POSITION_LABELS = {"GK": "Goalkeeper", "DEF": "Defence", "MID": "Midfield", "FW": "Attack"}
ROLE_COLORS = {"GK": "#f6bd4b", "DEF": "#4d91ff", "MID": "#35c58a", "FW": "#ff825e"}
DIFFICULTY_CLASSES = {
    "very easy": "difficulty-very-easy",
    "easy": "difficulty-easy",
    "average": "difficulty-average",
    "hard": "difficulty-hard",
    "very hard": "difficulty-very-hard",
}

st.set_page_config(
    page_title="Formation Assistant",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def load_styles() -> None:
    css = (APP_DIR / "styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def safe(value: object) -> str:
    return html.escape(str(value))


def player_label(player: dict) -> str:
    return f"{player['player_name']} · {player['team'] or 'Club unknown'}"


def render_squad_table(players: pd.DataFrame) -> str:
    cards = []
    for row in players.to_dict(orient="records"):
        position = row.get("position") or "?"
        position_color = ROLE_COLORS.get(position, "#92a9c8")
        probability = row.get("expected_to_play")
        if probability is None or pd.isna(probability):
            percentage = None
            probability_text = "N/A"
        else:
            percentage = max(0, min(100, round(float(probability) * 100)))
            probability_text = f"{percentage}%"
        probability_bar = (
            f'<div class="probability-track"><div class="probability-fill" '
            f'style="width:{percentage}%"></div><b>{probability_text}</b></div>'
            if percentage is not None
            else '<div class="probability-track probability-unavailable"><b>N/A</b></div>'
        )
        difficulty = row.get("opposition_difficulty")
        difficulty_class = DIFFICULTY_CLASSES.get(difficulty, "difficulty-unavailable")
        difficulty_text = safe(difficulty.title()) if difficulty else "N/A"
        team_xg = row.get("team_xg")
        opponent_xg = row.get("opponent_xg")
        team_xg_text = f"{float(team_xg):.2f}" if pd.notna(team_xg) else "—"
        opponent_xg_text = f"{float(opponent_xg):.2f}" if pd.notna(opponent_xg) else "—"
        fixture = safe(row.get("fixture_time") or "Fixture pending")
        team = safe(row.get("team_full_name") or row.get("team") or "Team unknown")
        opponent = safe(row.get("opponent") or "TBD")
        cards.append(
            f"""
            <article class="squad-row">
              <div class="player-identity">
                <span class="role-mark" style="--role-color:{position_color}">{safe(position)}</span>
                <span class="player-name">{safe(row["player_name"])}</span>
                <span class="player-team">{team}</span>
              </div>
              <div class="fixture-cell">
                <span class="fixture-opponent">{safe(row.get("venue") or "—")} · {opponent}</span>
                <span class="fixture-time">{fixture}</span>
              </div>
              <div class="xg-cell"><span>{team_xg_text}</span><small>TEAM xG</small></div>
              <div class="xg-cell"><span>{opponent_xg_text}</span><small>OPP. xG</small></div>
              <div class="probability-cell">
                <div class="cell-heading"><small>EXPECTED TO PLAY</small></div>
                {probability_bar}
              </div>
              <div class="difficulty-cell"><small>OPPOSITION</small>
                <span class="difficulty-pill {difficulty_class}">{difficulty_text}</span>
              </div>
            </article>
            """
        )
    return '<div class="squad-list">' + "".join(cards) + "</div>"


def render_pitch(
    formation: str,
    selected_by_position: dict[str, list[str]],
    player_by_name: dict[str, dict],
) -> str:
    groups = []
    for position in ("FW", "MID", "DEF", "GK"):
        members = selected_by_position[position]
        if not members:
            continue
        badges = []
        for name in members:
            player = player_by_name[name]
            probability = player.get("expected_to_play")
            probability_text = (
                f"{float(probability):.0%}"
                if probability is not None and pd.notna(probability)
                else "N/A"
            )
            badges.append(
                f'<div class="pitch-player"><b>{safe(name)}</b>'
                f'<span>{safe(player.get("opponent") or "Fixture pending")} · {probability_text}</span></div>'
            )
        groups.append(
            f'<div class="pitch-line pitch-line-{position.lower()}">'
            + "".join(badges)
            + "</div>"
        )
    return (
        f'<div class="pitch-board"><div class="pitch-caption">YOUR {safe(formation)} STARTING XI</div>'
        + "".join(groups)
        + "</div>"
    )


def render_page_header(team_name: str, updated_at: str | None) -> None:
    season_label = f"{SEASON}/{str(SEASON + 1)[-2:]}"
    subtitle = f"SEASON {season_label}" + (
        f"  ·  UPDATED {updated_at}" if updated_at else ""
    )
    st.markdown(
        f"""
        <div class="topline">
          <div class="club-badge">⚽</div>
          <div><div class="club-name">{safe(team_name)}</div>
            <div class="club-subtitle">{safe(subtitle)}</div></div>
          <div class="header-tag">FORMATION LAB <span>● LIVE DATA</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


load_styles()

if "team_name" not in st.session_state:
    st.session_state.team_name = "My Fantasy XI"
if "squad_data" not in st.session_state:
    st.session_state.squad_data = None
if "data_issues" not in st.session_state:
    st.session_state.data_issues = []
if "updated_at" not in st.session_state:
    st.session_state.updated_at = None

header_left, header_right = st.columns([5, 1], vertical_alignment="center")
with header_left:
    st.session_state.team_name = st.text_input(
        "Team name",
        value=st.session_state.team_name,
        label_visibility="collapsed",
        placeholder="Name your team",
    )
with header_right:
    refresh_clicked = st.button("↻  Refresh gameweek", use_container_width=True)

header_slot = st.empty()

if (
    st.session_state.squad_data is None
    and CACHE_PATH.is_file()
    and not refresh_clicked
):
    try:
        cached_data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        required_columns = {
            "player_name",
            "position",
            "team",
            "expected_to_play",
            "opposition_difficulty",
        }
        if not required_columns.issubset(cached_data["players"][0]):
            raise ValueError("Saved gameweek data is missing required player fields.")
        if cached_data.get("xg_method") != "last_five_any_venue":
            raise ValueError(
                "Saved xG values use an older calculation; refreshing current data."
            )
        st.session_state.squad_data = pd.DataFrame(cached_data["players"])
        st.session_state.data_issues = cached_data["issues"]
        st.session_state.updated_at = cached_data["updated_at"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, IndexError) as exc:
        st.warning(f"Saved gameweek data could not be loaded: {exc}")

should_load = refresh_clicked or st.session_state.squad_data is None
if should_load:
    with st.spinner("Updating fixtures, availability and xG from the data sources…"):
        try:
            squad_data, data_issues = load_gameweek_data(
                WORKBOOK_PATH,
                season=SEASON,
                force_refresh=True,
            )
            updated_at = datetime.now(ZoneInfo("Europe/Rome")).strftime(
                "%d %b, %H:%M %Z"
            )
            st.session_state.squad_data = squad_data
            st.session_state.data_issues = data_issues
            st.session_state.updated_at = updated_at
            cache_payload = {
                "players": json.loads(squad_data.to_json(orient="records")),
                "issues": data_issues,
                "updated_at": updated_at,
                "xg_method": "last_five_any_venue",
            }
            temporary_cache = CACHE_PATH.with_suffix(".tmp")
            try:
                CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
                temporary_cache.write_text(
                    json.dumps(cache_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                temporary_cache.replace(CACHE_PATH)
            except OSError as exc:
                st.error(f"Gameweek data was refreshed but could not be saved locally: {exc}")
                st.exception(exc)
        except Exception as exc:
            st.session_state.load_error = str(exc)
            st.error(f"Could not refresh gameweek data: {exc}")
            st.exception(exc)

with header_slot:
    render_page_header(st.session_state.team_name, st.session_state.updated_at)

if st.session_state.squad_data is None:
    st.info(
        "The player table will appear after a successful refresh. Check your internet "
        "connection and the data workbook, then try again."
    )
    st.stop()

if hasattr(st, "session_state") and "load_error" in st.session_state:
    del st.session_state["load_error"]

squad = st.session_state.squad_data.copy()
playable_squad = squad[squad["position"].isin(POSITION_ORDER)].copy()
playable_squad["position"] = pd.Categorical(
    playable_squad["position"], categories=POSITION_ORDER, ordered=True
)
playable_squad = playable_squad.sort_values(
    ["position", "expected_to_play", "player_name"],
    ascending=[True, False, True],
    na_position="last",
)
player_by_name = {
    player["player_name"]: player
    for player in playable_squad.to_dict(orient="records")
}

if st.session_state.data_issues:
    with st.expander(f"Data coverage notes · {len(st.session_state.data_issues)}"):
        for issue in st.session_state.data_issues:
            st.write(f"• {issue}")

lineup_tab, squad_tab = st.tabs(["⚽  Formation builder", "☷  Squad & fixtures"])

with lineup_tab:
    lead_left, lead_right = st.columns([1.2, 1], gap="large")
    with lead_left:
        st.markdown('<div class="section-kicker">01 / BUILD YOUR XI</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Pick your formation</div>', unsafe_allow_html=True)
        selected_formation = st.selectbox(
            "Formation",
            options=list(FORMATIONS),
            index=list(FORMATIONS).index("4-4-2"),
            label_visibility="collapsed",
        )
        if st.session_state.get("previous_formation") != selected_formation:
            for position, count in FORMATIONS[selected_formation].items():
                key = f"starter_{position}"
                if key in st.session_state:
                    st.session_state[key] = st.session_state[key][:count]
            st.session_state.previous_formation = selected_formation

        st.markdown(
            f'<div class="formation-summary">Choose {sum(FORMATIONS[selected_formation].values())} starters '
            f'· {selected_formation} · Select players by position</div>',
            unsafe_allow_html=True,
        )
        selected_by_position: dict[str, list[str]] = {}
        slot_columns = st.columns(2)
        for index, position in enumerate(POSITION_ORDER):
            options = [
                row["player_name"]
                for row in playable_squad.to_dict(orient="records")
                if row["position"] == position
            ]
            title = f"{POSITION_LABELS[position]} · {FORMATIONS[selected_formation][position]}"
            with slot_columns[index % 2]:
                selected_by_position[position] = st.multiselect(
                    title,
                    options=options,
                    max_selections=FORMATIONS[selected_formation][position],
                    format_func=lambda name: f"{name}  ·  {player_by_name[name].get('team') or 'Club unknown'}",
                    key=f"starter_{position}",
                    placeholder=f"Select {POSITION_LABELS[position].lower()}",
                )

        starters = [
            name for position in POSITION_ORDER for name in selected_by_position[position]
        ]
        bench = [
            name for name in player_by_name if name not in set(starters)
        ]
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        metric_col1.metric("STARTERS", f"{len(starters)} / 11")
        metric_col2.metric("BENCH OPTIONS", len(bench))
        expected_values = [
            player_by_name[name]["expected_to_play"]
            for name in starters
            if player_by_name[name].get("expected_to_play") is not None
            and pd.notna(player_by_name[name]["expected_to_play"])
        ]
        mean_expected = (
            sum(float(value) for value in expected_values) / len(expected_values)
            if expected_values
            else None
        )
        metric_col3.metric(
            "XI AVAILABILITY",
            f"{mean_expected:.0%}" if mean_expected is not None else "—",
        )

        control_col1, control_col2 = st.columns(2)
        with control_col1:
            captain = st.selectbox(
                "Captain",
                options=starters,
                index=None,
                placeholder="Choose your captain",
                disabled=not starters,
            )
        with control_col2:
            super_sub = st.selectbox(
                "Super sub",
                options=bench,
                index=None,
                placeholder="Choose a bench player",
                disabled=not bench,
            )
        if len(starters) == 11 and captain and super_sub:
            export_data = {
                "team": st.session_state.team_name,
                "season": SEASON,
                "formation": selected_formation,
                "starters": {
                    position: selected_by_position[position]
                    for position in POSITION_ORDER
                },
                "captain": captain,
                "super_sub": super_sub,
                "bench": [name for name in bench if name != super_sub],
                "updated_at": st.session_state.updated_at,
            }
            st.download_button(
                "Download my formation",
                data=json.dumps(export_data, ensure_ascii=False, indent=2),
                file_name="fantasy-formation.json",
                mime="application/json",
                use_container_width=True,
            )
        elif starters:
            st.caption("Select a full starting XI, captain and super sub to export the formation.")

    with lead_right:
        st.markdown('<div class="section-kicker">02 / SEE THE SHAPE</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Your pitch</div>', unsafe_allow_html=True)
        st.markdown(
            render_pitch(selected_formation, selected_by_position, player_by_name),
            unsafe_allow_html=True,
        )
        if captain:
            st.markdown(
                f'<div class="pitch-note"><span>CAPTAIN</span><b>{safe(captain)}</b>'
                f'<span class="pitch-note-separator">·</span><span>SUPER SUB</span>'
                f'<b>{safe(super_sub or "Not chosen")}</b></div>',
                unsafe_allow_html=True,
            )

with squad_tab:
    st.markdown('<div class="section-kicker">03 / MATCHWEEK SCOUTING</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Squad outlook</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="table-legend"><span><i class="legend-dot dot-green"></i>Strong availability</span>'
        '<span><i class="legend-dot dot-red"></i>Hard opposition</span>'
        '<span>xG averages use each team\'s last five matches, home or away.</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="squad-header">
          <span>PLAYER / ROLE</span><span>NEXT FIXTURE</span><span>TEAM xG</span>
          <span>OPP. xG</span><span>EXPECTED TO PLAY</span><span>DIFFICULTY</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.html(render_squad_table(squad))

    unmapped = squad[squad["position"].isna() | squad["team"].isna()]
    if not unmapped.empty:
        names = ", ".join(unmapped["player_name"].astype(str))
        st.warning(
            f"{names} could not be assigned a position or club from the workbook and "
            "cannot be placed in the formation until that roster data is available."
        )
