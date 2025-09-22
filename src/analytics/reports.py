"""
Report Generator für die Sport Data Pipeline

Erstellt verschiedene Reports und Visualisierungen basierend auf Analytics-Daten.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import plotly.offline as pyo

from ..core.config import Settings
from .engine import AnalyticsEngine


class ReportGenerator:
    """Erstellt verschiedene Reports und Visualisierungen"""

    def __init__(self, analytics_engine: AnalyticsEngine, settings: Settings):
        self.analytics = analytics_engine
        self.settings = settings
        self.logger = logging.getLogger("report_generator")

        # Erstelle Report-Verzeichnis falls nicht vorhanden
        os.makedirs(self.settings.report_output_path, exist_ok=True)

    async def generate_player_report(self, player_id: int, season: str = None) -> str:
        """Erstellt detaillierten Spieler-Report"""

        analysis = await self.analytics.analyze_player_performance(player_id, season)

        if "error" in analysis:
            return f"Error generating report: {analysis['error']}"

        # HTML Report erstellen
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Player Performance Report - {analysis['summary']['player_name']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f4f4f4; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px; background-color: #e9e9e9; border-radius: 3px; }}
                .positive {{ color: green; }}
                .negative {{ color: red; }}
                .neutral {{ color: orange; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Player Performance Report</h1>
                <h2>{analysis['summary']['player_name']} - {analysis['summary']['team']}</h2>
                <p>Age: {analysis['summary']['age']} | Seasons Analyzed: {analysis['summary']['seasons_analyzed']}</p>
            </div>
            
            <div class="section">
                <h3>Performance Summary</h3>
                <div class="metric">Matches: {analysis['summary']['total_matches']}</div>
                <div class="metric">Goals: {analysis['summary']['total_goals']}</div>
                <div class="metric">Assists: {analysis['summary']['total_assists']}</div>
                <div class="metric">Goals/Match: {analysis['summary']['goals_per_match']}</div>
                <div class="metric">Performance Score: {analysis['summary']['performance_score']}</div>
            </div>
            
            <div class="section">
                <h3>Trend Analysis</h3>
                <p>Trend Direction: <span class="{'positive' if analysis['trends']['trend_direction'] == 'improving' else 'negative' if analysis['trends']['trend_direction'] == 'declining' else 'neutral'}">{analysis['trends']['trend_direction']}</span></p>
                <div class="metric">Goals Trend: {analysis['trends']['goals_trend']}</div>
                <div class="metric">Assists Trend: {analysis['trends']['assists_trend']}</div>
                <div class="metric">Consistency Score: {analysis['trends']['consistency']}</div>
            </div>
            
            <div class="section">
                <h3>Peer Comparison</h3>
                <p>Compared with {analysis['comparisons']['peer_group_size']} similar players</p>
                <div class="metric">Player Goals/Match: {analysis['comparisons']['player_goals_per_match']}</div>
                <div class="metric">Peer Average: {analysis['comparisons']['peer_avg_goals']}</div>
                <div class="metric">Percentile Rank: {analysis['comparisons']['percentile_rank']}%</div>
                <p>Performance: <span class="{'positive' if analysis['comparisons']['above_average'] else 'negative'}">{'Above Average' if analysis['comparisons']['above_average'] else 'Below Average'}</span></p>
            </div>
            
            <div class="section">
                <h3>Future Predictions</h3>
                {f"<p>Predicted Goals Next Season: {analysis['predictions']['predicted_goals_next_season']} (Range: {analysis['predictions']['confidence_lower']} - {analysis['predictions']['confidence_upper']})</p>" if 'predicted_goals_next_season' in analysis['predictions'] else "<p>Insufficient data for predictions</p>"}
            </div>
            
            <div class="section">
                <p><small>Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
            </div>
        </body>
        </html>
        """

        # Report speichern
        filename = f"{self.settings.report_output_path}/player_report_{player_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            self.logger.info(f"Player report saved to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to save report: {e}")

        return html_content

    async def generate_league_dashboard(self, league_id: int, season: str) -> dict[str, str]:
        """Erstellt interaktives Liga-Dashboard"""

        analytics = await self.analytics.generate_league_analytics(league_id, season)

        if "error" in analytics:
            return {"error": analytics["error"]}

        # Plotly Visualisierungen erstellen
        visualizations = {}

        # 1. Standings Chart
        standings_html = self._create_standings_chart(analytics)
        visualizations["standings"] = standings_html

        # 2. Goals Analysis
        goals_html = self._create_goals_analysis(analytics)
        visualizations["goals"] = goals_html

        # 3. Form Analysis
        form_html = self._create_form_analysis(analytics)
        visualizations["form"] = form_html

        # Haupt-Dashboard HTML
        dashboard_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>League Analytics Dashboard</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .dashboard {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
                .widget {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .full-width {{ grid-column: 1 / -1; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
                .stat-card {{ background: #007bff; color: white; padding: 15px; border-radius: 5px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>League Analytics Dashboard</h1>
                <h2>Season {season}</h2>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>{analytics['league_summary']['total_teams']}</h3>
                    <p>Teams</p>
                </div>
                <div class="stat-card">
                    <h3>{analytics['league_summary']['matches_played']}</h3>
                    <p>Matches Played</p>
                </div>
                <div class="stat-card">
                    <h3>{analytics['league_summary']['total_goals']}</h3>
                    <p>Total Goals</p>
                </div>
                <div class="stat-card">
                    <h3>{analytics['league_summary']['avg_goals_per_match']}</h3>
                    <p>Goals/Match</p>
                </div>
                <div class="stat-card">
                    <h3>{analytics['league_summary']['leader']}</h3>
                    <p>League Leader</p>
                </div>
            </div>
            
            <div class="dashboard">
                <div class="widget">
                    <h3>Current Standings</h3>
                    {standings_html}
                </div>
                
                <div class="widget">
                    <h3>Goals Analysis</h3>
                    {goals_html}
                </div>
                
                <div class="widget full-width">
                    <h3>Team Form Analysis</h3>
                    {form_html}
                </div>
                
                <div class="widget">
                    <h3>Key Statistics</h3>
                    <ul>
                        <li>Home Win Rate: {analytics['statistical_insights']['home_advantage']['home_win_rate']}%</li>
                        <li>Away Win Rate: {analytics['statistical_insights']['home_advantage']['away_win_rate']}%</li>
                        <li>Draw Rate: {analytics['statistical_insights']['home_advantage']['draw_rate']}%</li>
                        <li>High-Scoring Matches: {analytics['statistical_insights']['scoring']['high_scoring_percentage']}%</li>
                    </ul>
                </div>
                
                <div class="widget">
                    <h3>Top Performers</h3>
                    <ul>
                        <li><strong>Champion:</strong> {analytics['top_performers']['champion']}</li>
                        <li><strong>Top Scoring Team:</strong> {analytics['top_performers']['top_scorer_team']}</li>
                        <li><strong>Best Defense:</strong> {analytics['top_performers']['best_defense']}</li>
                        <li><strong>Most Efficient:</strong> {analytics['top_performers']['most_efficient']}</li>
                    </ul>
                </div>
            </div>
            
            <div class="widget" style="margin-top: 20px;">
                <p><small>Dashboard generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
            </div>
        </body>
        </html>
        """

        # Dashboard speichern
        filename = f"{self.settings.report_output_path}/league_dashboard_{league_id}_{season}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(dashboard_html)
            self.logger.info(f"League dashboard saved to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to save dashboard: {e}")

        return {"dashboard": dashboard_html, "filename": filename}

    def _create_standings_chart(self, analytics: dict) -> str:
        """Erstellt Tabellen-Chart"""
        # Dummy-Daten für Demo (normalerweise aus analytics)
        teams = ["Team A", "Team B", "Team C", "Team D", "Team E"]
        points = [45, 42, 38, 35, 30]

        fig = go.Figure(data=go.Bar(x=teams, y=points, marker_color="lightblue"))

        fig.update_layout(
            title="Current League Standings", xaxis_title="Teams", yaxis_title="Points", height=400
        )

        return pyo.plot(fig, output_type="div", include_plotlyjs=False)

    def _create_goals_analysis(self, analytics: dict) -> str:
        """Erstellt Goals-Analyse Chart"""
        # Dummy-Daten für Demo
        categories = ["Goals For", "Goals Against", "Goal Difference"]
        values = [65, 25, 40]

        fig = go.Figure(data=go.Bar(x=categories, y=values, marker_color=["green", "red", "blue"]))

        fig.update_layout(title="Goals Analysis", height=400)

        return pyo.plot(fig, output_type="div", include_plotlyjs=False)

    def _create_form_analysis(self, analytics: dict) -> str:
        """Erstellt Form-Analyse Chart"""
        # Dummy-Daten für Demo
        teams = ["Team A", "Team B", "Team C", "Team D", "Team E"]
        form_ratings = [85, 72, 68, 55, 45]

        fig = go.Figure(
            data=go.Scatter(
                x=teams,
                y=form_ratings,
                mode="lines+markers",
                line=dict(color="orange", width=3),
                marker=dict(size=8),
            )
        )

        fig.update_layout(
            title="Team Form Analysis (Last 5 Games)",
            xaxis_title="Teams",
            yaxis_title="Form Rating (%)",
            height=400,
        )

        return pyo.plot(fig, output_type="div", include_plotlyjs=False)

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------
    def _save_html(self, filename: str, content: str) -> str:
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            self.logger.info(f"Saved report: {filename}")
        except Exception as e:  # noqa: BLE001
            self.logger.error(f"Failed to save {filename}: {e}")
        return filename

    async def generate_top_performers_report(self, season: str, limit: int = 20) -> dict[str, Any]:
        """Erstellt HTML Report der Top-Performer einer Saison.

        Diese Funktion ersetzt die frühere private Implementierung in
        `SportsAnalyticsApp` und reduziert Code-Duplikation.
        """
        df = await self.analytics.get_top_performers(season, limit=limit)
        if df.empty:
            return {"error": "No data"}
        html = [
            "<html><head><title>Top Performers Report</title></head><body>",
            f"<h1>Top Performers - Season {season}</h1>",
            "<table border='1'>",
            "<tr><th>Player</th><th>Team</th><th>Goals</th><th>Assists</th><th>Contributions</th><th>Goals/Match</th></tr>",
        ]
        for _, r in df.iterrows():
            html.append(
                f"<tr><td>{r['player_name']}</td><td>{r['team_name']}</td><td>{r['goals']}</td><td>{r['assists']}</td><td>{r['goal_contributions']}</td><td>{r['goals_per_match']:.2f}</td></tr>"
            )
        html.append("</table></body></html>")
        content = "".join(html)
        filename = f"{self.settings.report_output_path}/top_performers_{season}_{datetime.now().strftime('%Y%m%d')}.html"
        self._save_html(filename, content)
        return {"file": filename, "rows": len(df), "season": season}

    async def generate_transfer_analysis(self) -> dict[str, Any]:
        """Erstellt Transfer-Markt Analyse"""

        # Hole aktuelle Transfer-Daten
        query = """
        SELECT 
            p.first_name || ' ' || p.last_name as player_name,
            t.name as current_team,
            p.market_value,
            p.contract_end,
            EXTRACT(YEAR FROM AGE(p.birth_date)) as age,
            pos.name as position
        FROM players p
        JOIN teams t ON p.current_team_id = t.id
        JOIN positions pos ON p.position_id = pos.id
        WHERE p.contract_end <= CURRENT_DATE + INTERVAL '6 months'
        AND p.market_value > 1000000
        ORDER BY p.market_value DESC
        LIMIT 50
        """

        try:
            transfer_data = await self.analytics.load_data(query, cache_key="transfer_candidates")

            if transfer_data.empty:
                return {"error": "No transfer data available"}

            # Analyse durchführen
            analysis = {
                "hot_prospects": self._identify_hot_prospects(transfer_data),
                "bargain_deals": self._identify_bargain_deals(transfer_data),
                "position_analysis": self._analyze_positions(transfer_data),
                "age_distribution": self._analyze_age_distribution(transfer_data),
                "market_trends": self._analyze_market_trends(transfer_data),
            }

            # HTML Report erstellen
            html_report = self._create_transfer_html_report(analysis, transfer_data)

            # Speichern
            filename = f"{self.settings.report_output_path}/transfer_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_report)

            self.logger.info(f"Transfer analysis saved to {filename}")

            return {
                "analysis": analysis,
                "report_file": filename,
                "total_players": len(transfer_data),
            }

        except Exception as e:
            self.logger.error(f"Transfer analysis failed: {e}")
            return {"error": str(e)}

    def _identify_hot_prospects(self, df: pd.DataFrame) -> list[dict]:
        """Identifiziert vielversprechende Transfer-Kandidaten"""
        # Junge Spieler mit hohem Marktwert
        hot_prospects = df[(df["age"] <= 25) & (df["market_value"] >= 5000000)].head(10)

        return hot_prospects.to_dict("records")

    def _identify_bargain_deals(self, df: pd.DataFrame) -> list[dict]:
        """Identifiziert potenzielle Schnäppchen"""
        # Erfahrene Spieler mit niedrigerem Marktwert
        bargains = df[(df["age"] >= 28) & (df["market_value"] <= 3000000)].head(10)

        return bargains.to_dict("records")

    def _analyze_positions(self, df: pd.DataFrame) -> dict[str, int]:
        """Analysiert Positionen der Transfer-Kandidaten"""
        return df["position"].value_counts().to_dict()

    def _analyze_age_distribution(self, df: pd.DataFrame) -> dict[str, int]:
        """Analysiert Altersverteilung"""
        age_groups = pd.cut(
            df["age"],
            bins=[0, 23, 27, 30, 35, 100],
            labels=["Under 23", "23-27", "27-30", "30-35", "35+"],
        )
        return age_groups.value_counts().to_dict()

    def _analyze_market_trends(self, df: pd.DataFrame) -> dict[str, Any]:
        """Analysiert Markttrends"""
        return {
            "avg_market_value": df["market_value"].mean(),
            "median_market_value": df["market_value"].median(),
            "total_market_value": df["market_value"].sum(),
            "most_valuable_position": df.groupby("position")["market_value"].mean().idxmax(),
        }

    def _create_transfer_html_report(self, analysis: dict, data: pd.DataFrame) -> str:
        """Erstellt HTML Transfer Report"""

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Transfer Market Analysis</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f4f4f4; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .player-list {{ list-style: none; padding: 0; }}
                .player-item {{ background: #f9f9f9; margin: 5px 0; padding: 10px; border-radius: 3px; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
                .stat-box {{ background: #e9e9e9; padding: 15px; border-radius: 5px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Transfer Market Analysis</h1>
                <p>Analysis of {len(data)} transfer candidates</p>
                <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="section">
                <h3>Market Overview</h3>
                <div class="stats">
                    <div class="stat-box">
                        <h4>€{analysis['market_trends']['avg_market_value']:,.0f}</h4>
                        <p>Average Market Value</p>
                    </div>
                    <div class="stat-box">
                        <h4>€{analysis['market_trends']['total_market_value']:,.0f}</h4>
                        <p>Total Market Value</p>
                    </div>
                    <div class="stat-box">
                        <h4>{analysis['market_trends']['most_valuable_position']}</h4>
                        <p>Most Valuable Position</p>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h3>Hot Prospects (Young & Valuable)</h3>
                <ul class="player-list">
        """

        for player in analysis["hot_prospects"][:5]:
            html += f"""
                    <li class="player-item">
                        <strong>{player['player_name']}</strong> - {player['current_team']}<br>
                        Age: {player['age']} | Position: {player['position']} | Value: €{player['market_value']:,}
                    </li>
            """

        html += """
                </ul>
            </div>
            
            <div class="section">
                <h3>Bargain Deals (Experience & Value)</h3>
                <ul class="player-list">
        """

        for player in analysis["bargain_deals"][:5]:
            html += f"""
                    <li class="player-item">
                        <strong>{player['player_name']}</strong> - {player['current_team']}<br>
                        Age: {player['age']} | Position: {player['position']} | Value: €{player['market_value']:,}
                    </li>
            """

        html += """
                </ul>
            </div>
        </body>
        </html>
        """

        return html

    async def generate_weekly_summary(self) -> dict[str, Any]:
        """Erstellt wöchentliche Zusammenfassung"""

        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        try:
            # Sammle Daten der letzten Woche
            matches_query = """
            SELECT COUNT(*) as match_count,
                   AVG(home_score + away_score) as avg_goals
            FROM matches 
            WHERE match_date BETWEEN $1 AND $2
            AND status = 'finished'
            """

            matches_data = await self.analytics.load_data(
                matches_query,
                params=[start_date, end_date],
                cache_key=f"weekly_matches_{start_date.strftime('%Y%m%d')}",
            )

            # Top-Performer der Woche
            top_performers_query = """
            SELECT p.first_name || ' ' || p.last_name as player_name,
                   t.name as team_name,
                   SUM(ms.goals) as goals_scored,
                   SUM(ms.assists) as assists
            FROM match_stats ms
            JOIN players p ON ms.player_id = p.id
            JOIN teams t ON p.current_team_id = t.id
            JOIN matches m ON ms.match_id = m.id
            WHERE m.match_date BETWEEN $1 AND $2
            GROUP BY p.id, p.first_name, p.last_name, t.name
            ORDER BY (SUM(ms.goals) + SUM(ms.assists)) DESC
            LIMIT 10
            """

            performers_data = await self.analytics.load_data(
                top_performers_query,
                params=[start_date, end_date],
                cache_key=f"weekly_performers_{start_date.strftime('%Y%m%d')}",
            )

            summary = {
                "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                "matches_played": (
                    int(matches_data.iloc[0]["match_count"]) if not matches_data.empty else 0
                ),
                "avg_goals_per_match": (
                    round(float(matches_data.iloc[0]["avg_goals"]), 2)
                    if not matches_data.empty
                    else 0
                ),
                "top_performers": (
                    performers_data.to_dict("records") if not performers_data.empty else []
                ),
                "generated_at": datetime.now().isoformat(),
            }

            # HTML Summary erstellen
            html_summary = self._create_weekly_summary_html(summary)

            # Speichern
            filename = f"{self.settings.report_output_path}/weekly_summary_{start_date.strftime('%Y%m%d')}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_summary)

            self.logger.info(f"Weekly summary saved to {filename}")

            return {"summary": summary, "report_file": filename}

        except Exception as e:
            self.logger.error(f"Weekly summary generation failed: {e}")
            return {"error": str(e)}

    def _create_weekly_summary_html(self, summary: dict) -> str:
        """Erstellt HTML für wöchentliche Zusammenfassung"""

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Weekly Football Summary</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f4f4f4; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
                .stat-box {{ background: #007bff; color: white; padding: 15px; border-radius: 5px; text-align: center; }}
                .player-list {{ list-style: none; padding: 0; }}
                .player-item {{ background: #f9f9f9; margin: 5px 0; padding: 10px; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Weekly Football Summary</h1>
                <p>{summary['period']}</p>
            </div>
            
            <div class="section">
                <h3>Week Statistics</h3>
                <div class="stats">
                    <div class="stat-box">
                        <h4>{summary['matches_played']}</h4>
                        <p>Matches Played</p>
                    </div>
                    <div class="stat-box">
                        <h4>{summary['avg_goals_per_match']}</h4>
                        <p>Average Goals per Match</p>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h3>Top Performers of the Week</h3>
                <ul class="player-list">
        """

        for i, performer in enumerate(summary["top_performers"][:5], 1):
            html += f"""
                    <li class="player-item">
                        <strong>#{i} {performer['player_name']}</strong> - {performer['team_name']}<br>
                        Goals: {performer['goals_scored']} | Assists: {performer['assists']}
                    </li>
            """

        html += f"""
                </ul>
            </div>
            
            <div class="section">
                <p><small>Report generated on {summary['generated_at']}</small></p>
            </div>
        </body>
        </html>
        """

        return html
