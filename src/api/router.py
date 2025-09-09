"""
Aggregated API router for versioned endpoints.
"""

from fastapi import APIRouter

from src.api.endpoints import clubs, matches, players, teams, admin


api_router = APIRouter()

# Register endpoint routers here to keep create_fastapi_app clean
api_router.include_router(players.router, tags=["players"])
api_router.include_router(matches.router, tags=["matches"])
api_router.include_router(teams.router, tags=["teams"])
api_router.include_router(clubs.router, tags=["clubs"])
api_router.include_router(admin.router, tags=["admin"])


