from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from screen.processor import process_screenshot
from ai.context_manager import ask_gemini
from retrieval.tools import get_active_file
from indexing.indexer import index_project_path, get_project_structure

router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    screenshot_b64: str | None = None
    ocr_text: list[str] | None = None
    active_file: str | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[str] = []
    tools_used: list[str] = []


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    screen = None
    if req.screenshot_b64:
        try:
            screen = process_screenshot(req.screenshot_b64)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    active_file = req.active_file or get_active_file().get("path")

    answer, tools_used = ask_gemini(
        question=req.question,
        screen=screen,
        active_file=active_file,
    )

    return QueryResponse(answer=answer, sources=[], tools_used=tools_used)


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
