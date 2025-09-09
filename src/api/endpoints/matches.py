"""
Matches API Endpoints
API Routen für Match-bezogene Operationen
"""

import time

from fastapi import APIRouter, Depends

from src.analytics.engine import AnalyticsEngine
from src.api.dependencies import get_analytics_engine
from src.api.models import APIResponse, MatchPredictionRequest

router = APIRouter()


@router.post("/matches/predict", response_model=APIResponse)
async def predict_match(
    request: MatchPredictionRequest,
    analytics_engine: AnalyticsEngine = Depends(get_analytics_engine),
):
    """Predict match outcome"""
    start_time = time.time()

    try:
        prediction = await analytics_engine.predict_match_outcome(
            request.home_team_id, request.away_team_id, request.season
        )

        return APIResponse(
            success=True, data=prediction, execution_time_ms=(time.time() - start_time) * 1000
        )

    except Exception as e:
        return APIResponse(
            success=False, error=str(e), execution_time_ms=(time.time() - start_time) * 1000
        )


@router.get("/matches/{match_id}", response_model=APIResponse)
async def get_match(
    match_id: int, analytics_engine: AnalyticsEngine = Depends(get_analytics_engine)
):
    """Get match information"""
    start_time = time.time()

    try:
        # Placeholder for match data retrieval
        match_data = {"id": match_id, "message": "Match data retrieval not yet implemented"}

        return APIResponse(
            success=True, data=match_data, execution_time_ms=(time.time() - start_time) * 1000
        )

    except Exception as e:
        return APIResponse(
            success=False, error=str(e), execution_time_ms=(time.time() - start_time) * 1000
        )
