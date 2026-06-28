"""Hub marketplace API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.api.deps import get_current_user
from app.hub import hub_pull, hub_push, record_feedback

router = APIRouter(prefix="/hub", tags=["hub"])


class PullRequest(BaseModel):
    namespace: str
    asset_type: str = "prompt"


class PushRequest(BaseModel):
    namespace: str
    description: str = ""


class FeedbackRequest(BaseModel):
    run_id: str
    score: float
    comment: str = ""


@router.post("/pull")
async def pull_from_hub(data: PullRequest, _=Depends(get_current_user)):
    result = hub_pull(data.namespace, data.asset_type)
    if result is None:
        raise HTTPException(status_code=404, detail="Asset not found on Hub")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "ok", "namespace": data.namespace, "type": data.asset_type}


@router.post("/push")
async def push_to_hub(data: PushRequest, _=Depends(get_current_user)):
    return {"status": "published", "namespace": data.namespace, "description": data.description}


@router.post("/feedback")
async def submit_feedback(data: FeedbackRequest, _=Depends(get_current_user)):
    success = record_feedback(data.run_id, data.score, data.comment)
    return {"status": "ok" if success else "error", "message": "Feedback recorded" if success else "Hub not configured"}
