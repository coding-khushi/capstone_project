"""Phase 8: Sentence-transformer embeddings stored as SQLite BLOBs."""
from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from database.models import Embedding, ProjectFile

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _to_bytes(vec: np.ndarray) -> bytes:
    return vec.astype(np.float32).tobytes()


def _from_bytes(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)


def embed_and_store(project_id: int, session: Session) -> int:
    """Generate and persist embeddings for every symbol in a project."""
    model = _get_model()

    files = session.query(ProjectFile).filter_by(project_id=project_id).all()
    file_ids = [f.id for f in files]

    # Clear stale embeddings
    if file_ids:
        session.query(Embedding).filter(Embedding.file_id.in_(file_ids)).delete(
            synchronize_session=False
        )

    count = 0
    for pf in files:
        for sym in pf.symbols:
            text = f"{sym.kind} {sym.name}"
            vec = model.encode(text, normalize_embeddings=True)
            session.add(Embedding(
                file_id=pf.id,
                chunk_text=text,
                chunk_type=sym.kind,
                line_start=sym.line_start,
                line_end=sym.line_end,
                vector=_to_bytes(vec),
            ))
            count += 1

    session.flush()
    return count


def search_embeddings(query: str, session: Session, top_k: int = 5) -> list[dict]:
    """Return the top-k most relevant code chunks for a natural-language query."""
    model = _get_model()
    query_vec = model.encode(query, normalize_embeddings=True)

    rows = session.query(Embedding).all()
    if not rows:
        return []

    scored = []
    for row in rows:
        score = float(np.dot(query_vec, _from_bytes(row.vector)))
        scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        {
            "file": row.file.path if row.file else "unknown",
            "text": row.chunk_text,
            "line_start": row.line_start,
            "line_end": row.line_end,
            "score": round(score, 3),
        }
        for score, row in scored[:top_k]
    ]
