from fastapi import APIRouter
from pydantic import BaseModel

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
    # Phase 5: wire up context_manager → agent → LLM
    return QueryResponse(
        answer="Backend placeholder — Phase 5 will connect the AI pipeline here.",
        sources=[],
        tools_used=[],
    )


@router.post("/index")
async def index_project(project_path: str):
    # Phase 7: trigger project indexer
    return {"status": "indexing_not_yet_implemented", "path": project_path}


@router.get("/project/structure")
async def get_project_structure(project_path: str):
    # Phase 9: return tree-sitter parsed structure
    return {"structure": None, "message": "Phase 9"}
