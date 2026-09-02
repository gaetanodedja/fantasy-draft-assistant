# Fantasy Draft Assistant

A local Streamlit application for managing a fantasy football auction draft. The app combines historical player data, position-specific LightGBM models, auction budget tracking, and lineup optimization.

## Project Structure

```text
fantasy/
|-- data/
|   |-- fantasy_dataset.csv
|   `-- fantasy_data.xlsx
|-- fantasy_draft_assistant/
|   |-- app.py
|   |-- config.py
|   |-- requirements.txt
|   |-- test_step2.py
|   |-- run_app.bat
|   |-- run_app.sh
|   `-- src/
|       |-- data_loader.py
|       |-- engine.py
|       |-- league.py
|       |-- models.py
|       |-- optimizer.py
|       `-- recommendations.py
```

## Data Pipeline

The application reads `data/fantasy_dataset.csv`.

The loader in `src/data_loader.py`:

- Cleans column names and removes newline or non-breaking-space characters.
- Removes leading jersey numbers from player names.
- Normalizes positions and club names.
- Converts statistical columns to numeric values.
- Removes rows without a player name, position, or Avg value.
- Supports season filtering for `2025` and `2026`.
- Provides position-specific data for FW, MID, DEF, and GK.

The current dataset contains approximately 1,690 usable rows:

- 2026: 859 usable players
- 2025: 831 usable players

One malformed row in the source file is intentionally discarded because it does not contain a player, position, or Avg value.

## Machine Learning

`src/engine.py` contains `DraftModelEngine`.

A separate LightGBM regression model is trained for each position. The target variable is `Avg`.

The following fields are excluded from model features:

- Player
- Pos
- Club
- sheet_name
- league
- season
- Avg
- Price

`Price` is excluded deliberately because it is the auction value entered during the draft. It is not used to predict player performance.

The engine provides:

- Position-specific model training
- RMSE and R2 evaluation metrics
- Feature importance
- Projected Avg values
- Player rankings
- Season-aware ranking queries
- Exclusion of already-picked players

The model is trained lazily when a position is first requested. LightGBM output is configured to remain quiet in the terminal.

## Domain Models

`src/models.py` defines the main data objects:

### Player

Stores player identity, position, club, season, statistics, projected Avg, auction price, and availability.

### Team

Stores team identity, name, remaining budget, roster, starters, bench, and draft picks.

### DraftPick

Represents a recorded draft selection, including team, player, auction price, round, and pick number.

### LeagueState

Stores all teams, draft order, remaining players, draft log, current round, current pick, and league budget configuration.

## Auction and League Management

`src/league.py` contains `LeagueManager`.

The default budget is 1,000 per team. Team names can be renamed from the homepage. Names must be non-empty and unique.

When a player is picked:

1. The entered auction bid is checked.
2. The bid is deducted from the selected team's budget.
3. The player is added to that team's roster.
4. The player is removed from future recommendations and player selection lists.
5. The player's projected Avg remains available for team standings.

The dataset Price is not used for auction accounting. The user enters the winning bid manually.

League state can be exported to and restored from JSON. Saved state includes team names, budgets, rosters, auction prices, projected values, draft order, and draft position.

## Best Eleven Optimizer

`src/optimizer.py` contains `BestElevenOptimizer`.

The optimizer builds a valid starting eleven using the selected team's own players plus players not picked by opponents.

Rules:

- Exactly 11 players
- Exactly 1 goalkeeper
- At least 3 defenders
- Maximum 3 forwards
- The remaining positions are midfielders or forwards according to the selected formation

Supported formations:

- 3-4-3
- 3-5-2
- 4-3-3
- 4-4-2
- 4-5-1
- 5-3-2
- 5-4-1

The `Best formation` option evaluates every valid formation and selects the one with the highest total projected Avg.

If a selected team has already picked a player such as Lamine Yamal, that player is automatically retained in the lineup. The optimizer fills the remaining positions from eligible players. Players picked by other teams are excluded.

The optimizer can also be restricted to a specific season. This ensures that selecting season 2026 produces a complete formation from 2026 players rather than merely hiding rows from a mixed-season lineup.

## Application Pages

### Home

The homepage contains:

- Team renaming controls
- Projected standings
- Total projected Avg for each team
- Remaining budget for each team
- Quick navigation guidance

Standings are ordered from highest to lowest total projected Avg.

### Rankings

The Rankings page shows top N available players for every position:

- FW
- MID
- DEF
- GK

It includes all player statistics, actual Avg, dataset Price for reference, and projected Avg.

The page has a `Player season` selector. Selecting `2026` or `2025` filters the source data before the top N players are selected.

Picked players are removed automatically. Feature importance is displayed for each position.

### Best Eleven

The Best Eleven page:

- Defaults to the first team, which is Team 1 in a new league.
- Allows selection of a team.
- Allows selection of `Best formation` or a specific formation.
- Allows selection of a player season.
- Includes the selected team's drafted players.
- Excludes opponent-drafted players.
- Displays the full optimized lineup and statistics.
- Displays the total projected Avg.

### Draft Tracker

The Draft Tracker is the auction selection page. It is not limited to model suggestions.

It allows the user to:

- Select a team.
- Filter by position or view all positions.
- Search for any available player.
- Enter the winning auction bid.
- Record the pick.

A player selected by any team is removed from the available player list.

### Teams

The Teams page displays:

- Every team
- Remaining budget
- Each team's roster
- Player positions
- Auction prices
- Projected Avg values

### Save / Load Draft

The current draft can be downloaded as a JSON file and restored later through the application.

## Installation

Use Python 3.11 or a compatible Python environment.

From the application directory:

```bat
cd C:\Users\User\Desktop\fantasy\fantasy_draft_assistant
pip install -r requirements.txt
```

Required packages:

- pandas
- scikit-learn
- lightgbm
- numpy
- streamlit

## Running the Application

From Anaconda Prompt or another terminal:

```bat
cd C:\Users\User\Desktop\fantasy\fantasy_draft_assistant
python -m streamlit run app.py
```

The app normally opens at:

```text
http://localhost:8501
```

On Windows, you can also run `run_app.bat`.

If the default port is occupied:

```bat
python -m streamlit run app.py --server.port=8502
```

## Testing

Run the backend test suite:

```bat
cd C:\Users\User\Desktop\fantasy\fantasy_draft_assistant
python test_step2.py
```

The suite tests:

- Data loading and normalization
- Position catalog creation
- LightGBM training for all positions
- Player ranking
- Feature importance
- Recommendation queries
- League creation
- Budget deduction

A focused model check can be run with:

```bat
python -c "from config import DATASET_PATH; from src.data_loader import load_player_dataset, filter_season_2026; df=load_player_dataset(DATASET_PATH); print(df['season'].value_counts()); print('2026 usable rows:', len(filter_season_2026(df)))"
```

## Environment Notes

The project has previously been run successfully with system Python 3.11. Anaconda environments may contain incompatible compiled versions of NumPy, pandas, scikit-learn, or dask.

If Anaconda reports errors such as:

```text
ValueError: numpy.dtype size changed
```

or:

```text
AttributeError: pandas.core.strings has no attribute StringMethods
```

use a clean compatible environment or run with the verified system Python executable:

```bat
C:\Users\User\AppData\Local\Microsoft\WindowsApps\python3.11.exe -m streamlit run app.py
```

## Current Design Boundaries

- LightGBM provides numeric projections and feature importance.
- The application state is authoritative for picks, budgets, and rosters.
- Auction prices are entered by the user.
- The current application does not use an LLM assistant or chat feature.
- The current application does not include a separate Player Comparison page.
