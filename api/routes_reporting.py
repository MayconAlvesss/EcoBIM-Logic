from fastapi import APIRouter, Depends, HTTPException
from security.auth import verify_api_key
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/reports",
    tags=["ESG Reporting"],
    dependencies=[Depends(verify_api_key)]
)

@router.get("/{project_id}/executive-summary")
async def get_executive_summary(project_id: str):
    # logger.info(f"generating report for: {project_id}")

    # FIXME: still waiting for the DB team to finish the persistence layer.
    # returning a hardcoded mock for now so the frontend doesn't get blocked.
    if project_id == "unknown":
        raise HTTPException(status_code=404, detail="project not found")

    return {
        "project_id": project_id,
        "status": "pending_db_integration",
        "message": "this is a mock. db integration is WIP."
    }
