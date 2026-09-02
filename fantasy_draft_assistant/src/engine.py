from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .data_loader import load_player_dataset


class DraftModelEngine:
    """Train and score fantasy players for live draft recommendations."""

    def __init__(self, dataset_path: str | Path):
        self.dataset_path = Path(dataset_path)
        self.raw_data = load_player_dataset(self.dataset_path)
        self.position_models: Dict[str, dict] = {}

    def _numeric_feature_columns(self, frame: pd.DataFrame) -> List[str]:
        excluded = {"Player", "Pos", "Club", "sheet_name", "league", "season", "Avg", "Price"}
        feature_columns: List[str] = []
        for column in frame.columns:
            if column in excluded:
                continue
            if pd.api.types.is_numeric_dtype(frame[column]):
                feature_columns.append(column)
        return feature_columns

    def prepare_training_data(self, position: str | None = None) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
        frame = self.raw_data.copy()
        if position is not None:
            frame = frame[frame["Pos"].str.upper() == str(position).upper()].copy()

        if frame.empty:
            raise ValueError(f"No players found for position: {position}")

        numeric_columns = self._numeric_feature_columns(frame)
        encoded_position = pd.get_dummies(frame[["Pos"]], prefix="pos")
        X = pd.concat([frame[numeric_columns], encoded_position], axis=1)
        y = frame["Avg"].astype(float)
        return X.fillna(0), y, frame

    def train_position_model(self, position: str) -> dict:
        X, y, frame = self.prepare_training_data(position)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    LGBMRegressor(
                        objective="regression",
                        n_estimators=500,
                        learning_rate=0.05,
                        num_leaves=31,
                        subsample=0.9,
                        colsample_bytree=0.9,
                        random_state=42,
                        verbosity=-1,
                    ),
                ),
            ]
        )

        pipeline.fit(X_train, y_train)
        predictions = pipeline.predict(X_test)
        rmse = float((mean_squared_error(y_test, predictions)) ** 0.5)
        model_score = float(r2_score(y_test, predictions))

        feature_importances = pd.Series(
            pipeline.named_steps["model"].feature_importances_,
            index=X.columns,
        ).sort_values(ascending=False)

        result = {
            "position": position.upper(),
            "model": pipeline,
            "rmse": rmse,
            "r2": model_score,
            "feature_importance": feature_importances,
            "frame": frame,
            "X": X,
            "y": y,
        }
        self.position_models[position.upper()] = result
        return result

    def rank_players(self, position: str, top_n: int = 10) -> pd.DataFrame:
        result = self.position_models.get(position.upper())
        if result is None:
            result = self.train_position_model(position)

        frame = result["frame"].copy()
        X = result["X"].copy().fillna(0)
        projected_avg = result["model"].predict(X)

        ranked = frame.assign(projected_avg=projected_avg)
        ranked = ranked.sort_values(["projected_avg", "Avg"], ascending=[False, False])
        return ranked.head(top_n).reset_index(drop=True)

    def train_all_positions(self) -> Dict[str, dict]:
        positions = sorted(self.raw_data["Pos"].dropna().astype(str).str.upper().unique())
        for position in positions:
            if position and position not in self.position_models:
                self.train_position_model(position)
        return self.position_models
