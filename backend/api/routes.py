from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from screen.processor import process_screenshot
from ai.context_manager import ask_gemini
from retrieval.tools import get_active_file
from indexing.indexer import index_project_path, get_project_structure
from debug_logger import log_interaction

router = APIRouter()


class ChatHistoryItem(BaseModel):
    role: str
    text: str


class QueryRequest(BaseModel):
    question: str
    screenshot_b64: str | None = None
    ocr_text: list[str] | None = None
    active_file: str | None = None
    permitted_files: list[str] = []
    history: list[ChatHistoryItem] = []


class QueryResponse(BaseModel):
    answer: str
    sources: list[str] = []
    tools_used: list[str] = []
    permission_required: list[str] = []
    suggested_files: list[str] = []


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    screen = None
    if req.screenshot_b64:
        try:
            screen = process_screenshot(req.screenshot_b64)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    active_file = req.active_file or get_active_file().get("path")

    answer, tools_used, sources, suggested_files = ask_gemini(
        question=req.question,
        screen=screen,
        active_file=active_file,
        permitted_files=req.permitted_files,
        history=[{"role": h.role, "text": h.text} for h in req.history],
    )

    permission_required = suggested_files if answer == "__permission_required__" else []
    if answer == "__permission_required__":
        answer = "I need file access to answer this fully."

    log_interaction(
        question=req.question,
        screenshot_b64=req.screenshot_b64,
        permitted_files=req.permitted_files,
        history=[{"role": h.role, "text": h.text} for h in req.history],
        answer=answer,
        tools_used=tools_used,
        sources=sources,
        suggested_files=suggested_files if not permission_required else [],
        permission_required=permission_required,
    )

    return QueryResponse(
        answer=answer,
        sources=sources,
        tools_used=tools_used,
        permission_required=permission_required,
        suggested_files=suggested_files if not permission_required else [],
    )


@router.post("/index")
async def index_project(project_path: str):
    try:
        stats = index_project_path(project_path)
        return {"status": "ok", "path": project_path, **stats}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/project/structure")
async def get_structure(project_path: str):
    try:
        structure = get_project_structure(project_path)
        return {"structure": structure}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
