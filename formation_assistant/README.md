# Formation Assistant

A local Streamlit app for reviewing your fantasy squad's next fixtures and building
a starting XI. It uses the roster in `..\data\fantasy_data.xlsx`, loads the last
successful gameweek refresh on startup, and fetches current ESPN schedules/lineups,
WhoScored availability reports, and Understat xG when you select **Refresh gameweek**.

## Run locally on Windows

1. Open PowerShell in this folder.
2. Create and activate a virtual environment if you do not already have one:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install the app requirements:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Start the app:

   ```powershell
   python -m streamlit run app.py
   ```

   Alternatively, double-click `run_app.bat`.

Streamlit opens the app in your browser, normally at `http://localhost:8501`.
The first refresh needs internet access and may take a little while while the
football data sources respond. The app stores the last successful table locally
in `.cache\gameweek.json` so it can display it immediately the next time you open
the app. Click **Refresh gameweek** to fetch the latest fixtures and availability.

## Using the formation builder

- Choose a formation and select players by position.
- Select a captain and super sub.
- Use **Download my formation** to save the selected XI as a JSON file.
- Open **Squad & fixtures** to compare expected-to-play percentages, xG averages,
  opponents and difficulty.

Expected-to-play is a recent-appearance frequency, not a calibrated forecast.
An unavailable-player listing overrides it to 0%. Team and opponent xG each
use that team's average from its latest five matches, regardless of venue.
Difficulty ranks the opponent's latest-five-match average within the same
league; higher opponent xG is considered harder.

The workbook currently has no club/position mapping for Matija Katic, so he
appears in the squad list but cannot be assigned to a formation slot until the
workbook includes his roster information.
