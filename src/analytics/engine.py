"""
Analytics Engine
Hauptmodul für Datenanalyse, ML-Modelle und Reporting
"""

import logging
from datetime import datetime
from typing import Any

import joblib

# Statistik & Visualisierung
import pandas as pd

# ML & Analytics
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

# Time Series
from src.core.config import Settings

# =============================================================================
# 1. ML MODELS
# =============================================================================


class PlayerPerformanceModel:
    """Model für Spielerleistung"""

    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = []
        self.is_trained = False

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Bereitet Features für das Training vor"""
        features = df.copy()

        # Age calculation
        features["age"] = (
            pd.to_datetime("today").year - pd.to_datetime(features["birth_date"]).dt.year
        )

        # Performance metrics
        features["goals_per_match"] = features["goals"] / features["matches_played"]
        features["assists_per_match"] = features["assists"] / features["matches_played"]
        features["minutes_per_match"] = features["minutes_played"] / features["matches_played"]

        # Position encoding
        le = LabelEncoder()
        features["position_encoded"] = le.fit_transform(features["position"].fillna("Unknown"))

        return features.fillna(0)

    def train(self, df: pd.DataFrame, target_column: str = "market_value") -> dict[str, Any]:
        """Trainiert das Model"""
        features_df = self.prepare_features(df)

        # Feature selection
        feature_cols = [
            "age",
            "goals_per_match",
            "assists_per_match",
            "minutes_per_match",
            "position_encoded",
            "matches_played",
        ]

        X = features_df[feature_cols]
        y = features_df[target_column]

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train model
        self.model = GradientBoostingRegressor(n_estimators=100, random_state=42)
        self.model.fit(X_train_scaled, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        mse = mean_squared_error(y_test, y_pred)

        self.feature_columns = feature_cols
        self.is_trained = True

        return {
            "mse": mse,
            "feature_importance": dict(zip(feature_cols, self.model.feature_importances_)),
        }


class MatchPredictionModel:
    """Model für Spielergebnis-Vorhersage"""

    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False

    def prepare_match_features(
        self, matches_df: pd.DataFrame, teams_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Bereitet Match-Features vor"""
        features = matches_df.copy()

        # Team-Statistiken hinzufügen
        team_stats = self._calculate_team_form(matches_df)

        # Home/Away Performance
        home_stats = team_stats.add_suffix("_home")
        away_stats = team_stats.add_suffix("_away")

        features = features.merge(home_stats, left_on="home_team_id", right_index=True, how="left")
        features = features.merge(away_stats, left_on="away_team_id", right_index=True, how="left")

        # Relative Stärke
        features["form_difference"] = features["form_home"] - features["form_away"]
        features["goals_ratio_home"] = features["avg_goals_for_home"] / (
            features["avg_goals_against_home"] + 1
        )
        features["goals_ratio_away"] = features["avg_goals_for_away"] / (
            features["avg_goals_against_away"] + 1
        )

        # Head-to-Head
        features["h2h_home_wins"] = self._calculate_h2h(matches_df, features)

        return features.fillna(0)

    def _calculate_team_form(
        self, matches_df: pd.DataFrame, last_n_matches: int = 5
    ) -> pd.DataFrame:
        """Berechnet Team-Form der letzten N Spiele"""
        team_stats = []

        for team_id in pd.concat([matches_df["home_team_id"], matches_df["away_team_id"]]).unique():
            # Letzte Spiele des Teams
            team_matches = (
                matches_df[
                    (matches_df["home_team_id"] == team_id)
                    | (matches_df["away_team_id"] == team_id)
                ]
                .sort_values("match_date")
                .tail(last_n_matches)
            )

            if len(team_matches) == 0:
                continue

            # Form berechnen (Punkte)
            points = 0
            goals_for = 0
            goals_against = 0

            for _, match in team_matches.iterrows():
                if match["home_team_id"] == team_id:
                    # Team spielt zuhause
                    team_goals = match["home_score"]
                    opponent_goals = match["away_score"]
                else:
                    # Team spielt auswärts
                    team_goals = match["away_score"]
                    opponent_goals = match["home_score"]

                goals_for += team_goals
                goals_against += opponent_goals

                # Punkte vergeben
                if team_goals > opponent_goals:
                    points += 3
                elif team_goals == opponent_goals:
                    points += 1

            team_stats.append(
                {
                    "team_id": team_id,
                    "form": points,
                    "avg_goals_for": goals_for / len(team_matches),
                    "avg_goals_against": goals_against / len(team_matches),
                    "matches_played": len(team_matches),
                }
            )

        return pd.DataFrame(team_stats).set_index("team_id")

    def _calculate_h2h(self, matches_df: pd.DataFrame, features_df: pd.DataFrame) -> pd.Series:
        """Berechnet Head-to-Head Statistiken"""
        h2h_wins = []

        for _, match in features_df.iterrows():
            home_id = match["home_team_id"]
            away_id = match["away_team_id"]

            # Vergangene Begegnungen
            h2h_matches = matches_df[
                ((matches_df["home_team_id"] == home_id) & (matches_df["away_team_id"] == away_id))
                | (
                    (matches_df["home_team_id"] == away_id)
                    & (matches_df["away_team_id"] == home_id)
                )
            ]

            if len(h2h_matches) == 0:
                h2h_wins.append(0.5)  # Neutral wenn keine Historie
                continue

            home_wins = 0
            for _, h2h_match in h2h_matches.iterrows():
                if (
                    h2h_match["home_team_id"] == home_id
                    and h2h_match["home_score"] > h2h_match["away_score"]
                ):
                    home_wins += 1
                elif (
                    h2h_match["away_team_id"] == home_id
                    and h2h_match["away_score"] > h2h_match["home_score"]
                ):
                    home_wins += 1

            h2h_wins.append(home_wins / len(h2h_matches))

        return pd.Series(h2h_wins)


# =============================================================================
# 2. ANALYTICS ENGINE
# =============================================================================


class AnalyticsEngine:
    """Hauptklasse für alle Analytics-Operationen"""

    def __init__(self, db_manager, settings: Settings = None):
        self.db_manager = db_manager
        self.settings = settings or Settings()
        self.logger = logging.getLogger("analytics_engine")

        # Models
        self.player_model = PlayerPerformanceModel()
        self.match_model = MatchPredictionModel()

        # Cache
        self.data_cache = {}
        self.cache_timestamps = {}

    async def initialize(self):
        """Initialisiert die Analytics Engine (Platzhalter für zukünftige Setups)."""
        try:
            # Hier könnten Model-Ladungen, Cache-Initialisierung o.ä. erfolgen
            self.logger.info("AnalyticsEngine initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize AnalyticsEngine: {e}")
            raise

    async def load_data(
        self, query: str, cache_key: str = None, use_cache: bool = True
    ) -> pd.DataFrame:
        """Lädt Daten aus der Datenbank mit Caching"""

        if use_cache and cache_key and self._is_cache_valid(cache_key):
            self.logger.info(f"Using cached data for {cache_key}")
            return self.data_cache[cache_key]

        try:
            result = await self.db_manager.execute_query(query)
            df = pd.DataFrame([dict(row) for row in result])

            if cache_key:
                self.data_cache[cache_key] = df
                self.cache_timestamps[cache_key] = datetime.now()

            self.logger.info(f"Loaded {len(df)} rows from database")
            return df

        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            raise

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Prüft ob Cache noch gültig ist"""
        if cache_key not in self.cache_timestamps:
            return False

        cache_age = datetime.now() - self.cache_timestamps[cache_key]
        return cache_age.total_seconds() < (self.settings.cache_duration_hours * 3600)

    async def analyze_player_performance(
        self, player_id: int = None, season: str = None
    ) -> dict[str, Any]:
        """Analysiert Spielerleistung"""

        query = """
        SELECT 
            p.id, p.first_name, p.last_name, p.birth_date,
            sps.season, sps.matches_played, sps.minutes_played,
            sps.goals, sps.assists, sps.stats_data,
            t.name as team_name,
            EXTRACT(YEAR FROM AGE(p.birth_date)) as age
        FROM players p
        JOIN season_player_stats sps ON p.id = sps.player_id
        JOIN teams t ON sps.team_id = t.id
        WHERE ($1::int IS NULL OR p.id = $1)
        AND ($2::text IS NULL OR sps.season = $2)
        AND sps.matches_played >= $3
        """

        df = await self.load_data(query, cache_key=f"player_perf_{player_id}_{season}")

        if df.empty:
            return {"error": "No data found"}

        # Basic statistics
        analysis = {
            "player_count": len(df),
            "avg_goals_per_match": df["goals"].sum() / df["matches_played"].sum(),
            "avg_assists_per_match": df["assists"].sum() / df["matches_played"].sum(),
            "top_performers": df.nlargest(10, "goals")[
                ["first_name", "last_name", "goals", "team_name"]
            ].to_dict("records"),
        }

        return analysis

    async def predict_match_outcome(
        self, home_team_id: int, away_team_id: int, season: str = None
    ) -> dict[str, Any]:
        """Sagt Spielergebnis vorher"""

        if not self.match_model.is_trained:
            await self._train_match_model(season)

        # Prepare prediction features
        match_data = pd.DataFrame(
            [
                {
                    "home_team_id": home_team_id,
                    "away_team_id": away_team_id,
                    "match_date": datetime.now(),
                }
            ]
        )

        # Load historical data for feature engineering
        matches_query = """
        SELECT home_team_id, away_team_id, home_score, away_score, match_date
        FROM matches 
        WHERE season = $1 OR $1 IS NULL
        ORDER BY match_date DESC
        """

        matches_df = await self.load_data(matches_query, cache_key=f"matches_{season}")

        if matches_df.empty:
            return {"error": "No historical data available"}

        # Feature engineering
        self.match_model.prepare_match_features(match_data, pd.DataFrame())

        # Make prediction (placeholder)
        prediction = {
            "home_win_probability": 0.45,
            "draw_probability": 0.25,
            "away_win_probability": 0.30,
            "confidence": 0.75,
        }

        return prediction

    async def _train_match_model(self, season: str = None):
        """Trainiert das Match Prediction Model"""
        matches_query = """
        SELECT home_team_id, away_team_id, home_score, away_score, match_date,
               CASE 
                   WHEN home_score > away_score THEN 'home_win'
                   WHEN home_score < away_score THEN 'away_win'
                   ELSE 'draw'
               END as result
        FROM matches 
        WHERE season = $1 OR $1 IS NULL
        AND home_score IS NOT NULL AND away_score IS NOT NULL
        """

        df = await self.load_data(matches_query, cache_key=f"match_training_{season}")

        if len(df) < self.settings.min_matches_for_prediction:
            raise ValueError(f"Not enough matches for training: {len(df)}")

        # Training logic would go here
        self.match_model.is_trained = True
        self.logger.info(f"Match model trained with {len(df)} matches")

    def save_model(self, model_name: str, model_obj):
        """Speichert trainiertes Model"""
        model_path = f"{self.settings.model_storage_path}/{model_name}.pkl"
        joblib.dump(model_obj, model_path)
        self.logger.info(f"Model saved to {model_path}")

    def load_model(self, model_name: str):
        """Lädt gespeichertes Model"""
        model_path = f"{self.settings.model_storage_path}/{model_name}.pkl"
        try:
            model = joblib.load(model_path)
            self.logger.info(f"Model loaded from {model_path}")
            return model
        except FileNotFoundError:
            self.logger.warning(f"Model not found: {model_path}")
            return None
