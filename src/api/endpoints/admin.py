"""
Admin API Endpoints
Allows triggering scrapers and collectors via API
"""

from fastapi import APIRouter, Request, HTTPException, status, Body
from pydantic import BaseModel
from typing import Literal, Optional
import logging
import os

router = APIRouter()

class RunJobRequest(BaseModel):
    job_type: Literal["scraper", "collector"]
    name: str
    # Optionally, add more parameters if needed


@router.post("/admin/run", status_code=202)
async def run_job(
    request: Request,
    body: RunJobRequest = Body(...),
):
    """Trigger a scraper or collector by name"""
    logger = logging.getLogger("admin_endpoint")
    try:
        logger.info(f"Received admin run request: job_type={body.job_type}, name={body.name}")
        if body.job_type == "scraper":
            safe_mode = getattr(request.app.state, "safe_mode", False)
            orchestrator = getattr(request.app.state, "scraping_orchestrator", None)
            if not orchestrator:
                logger.error("Scraping orchestrator not available")
                raise HTTPException(status_code=500, detail="Scraping orchestrator not available")
            if safe_mode:
                # Simulated response without real scraping (no network / browser init)
                simulated = {
                    body.name: {
                        "status": "simulated",
                        "items_scraped": 0,
                        "duration_seconds": 0,
                        "note": "SAFE_MODE simulation - real scraping disabled"
                    }
                }
                logger.info("SAFE_MODE: returning simulated scraper result for %s", body.name)
                return {"status": "started", "result": simulated, "safe_mode": True}
            # Non-safe: real orchestrator execution
            result = await orchestrator.run_scraping_job([body.name])
        elif body.job_type == "collector":
            data_app = getattr(request.app.state, "data_app", None)
            if not data_app or not hasattr(data_app, "run_data_collection"):
                logger.error("Data collection not available")
                raise HTTPException(status_code=500, detail="Data collection not available")
            result = await data_app.run_data_collection([body.name])
        else:
            logger.error(f"Invalid job_type: {body.job_type}")
            raise HTTPException(status_code=400, detail="Invalid job_type")
        logger.info(f"Admin run result: {result}")
        return {"status": "started", "result": result}
    except Exception as e:
        logger.exception(f"Admin endpoint error: {e}")
        return {"status": "error", "error": str(e)}

@router.get("/admin/ping", status_code=200)
async def ping():
    """Quick health check endpoint for admin router."""
    return {"status": "ok", "message": "admin router is alive"}

@router.get("/admin/health", status_code=200)
async def admin_health(request: Request):
    """Detailed admin subsystem status (no external DB queries)."""
    scrapers = []
    orchestrator = getattr(request.app.state, "scraping_orchestrator", None)
    if orchestrator and getattr(orchestrator, "scrapers", None):
        scrapers = list(orchestrator.scrapers.keys())
    return {
        "status": "ok",
        "safe_mode": getattr(request.app.state, "safe_mode", False),
        "db_connected": bool(getattr(request.app.state, "db", None)),
        "registered_scrapers": scrapers,
    }

@router.get("/admin/scrapers", status_code=200)
async def list_scrapers(request: Request):
    """List currently registered scrapers."""
    orchestrator = getattr(request.app.state, "scraping_orchestrator", None)
    safe_mode = getattr(request.app.state, "safe_mode", False)
    if safe_mode:
        # Provide static list representative of available scrapers
        scrapers = ["flashscore", "transfermarkt", "odds"]
    else:
        scrapers = list(orchestrator.scrapers.keys()) if orchestrator else []
    return {
        "safe_mode": safe_mode,
        "count": len(scrapers),
        "scrapers": scrapers,
    }