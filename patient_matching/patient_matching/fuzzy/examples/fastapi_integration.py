"""FastAPI integration example for fuzzy.

Run with: uvicorn examples.fastapi_integration:app --reload
Requires: pip install fastapi uvicorn
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from patient_matching.fuzzy.fuzzy_db import (
    DatabaseBackend,
    FuzzySearchConfig,
    FuzzySearchManager,
    SimilarityAlgorithm,
)

# ── Setup ────────────────────────────────────────────────────────────
# In production you would read these from config or env vars.

manager = FuzzySearchManager(
    backend_type=DatabaseBackend.DUCKDB,
    connection_params={"database": ":memory:"},
    default_config=FuzzySearchConfig(
        algorithm=SimilarityAlgorithm.JARO_WINKLER,
        threshold=0.6,
        limit=20,
    ),
)


def _seed_data() -> None:
    """Insert sample data for the demo."""
    backend = manager.backend
    backend.connect()
    backend._connection.execute(  # type: ignore[attr-defined]
        "CREATE TABLE IF NOT EXISTS patients (id INTEGER, name VARCHAR)"
    )
    for i, name in enumerate(
        [
            "John Smith",
            "Jon Smyth",
            "Jonathan Smith",
            "Jane Doe",
            "Janet Doe",
            "James Johnson",
            "Jim Johnson",
            "Robert Williams",
            "Bob Williams",
            "Elizabeth Taylor",
        ],
        start=1,
    ):
        backend._connection.execute("INSERT INTO patients VALUES (?, ?)", [i, name])  # type: ignore[attr-defined]
    backend.disconnect()


_seed_data()

# ── FastAPI app ──────────────────────────────────────────────────────

try:
    from fastapi import FastAPI, Query
    from pydantic import BaseModel

    app = FastAPI(title="fuzzy Demo API")

    class SearchResponse(BaseModel):
        id: str
        value: str
        similarity_score: float
        metadata: Optional[Dict[str, Any]] = None

    @app.get("/search", response_model=List[SearchResponse])
    def search(
        q: str = Query(..., description="Search query"),
        field: str = Query("name", description="Field to search"),
        table: str = Query("patients", description="Table to search"),
        algorithm: str = Query("jaro_winkler", description="Algorithm"),
        threshold: float = Query(0.6, ge=0.0, le=1.0),
        limit: int = Query(10, ge=1, le=100),
    ) -> List[Dict[str, Any]]:
        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm(algorithm),
            threshold=threshold,
            limit=limit,
        )
        results = manager.search(q, field, table, config)
        return [
            {
                "id": str(r.id),
                "value": r.value,
                "similarity_score": r.similarity_score,
                "metadata": r.metadata,
            }
            for r in results
        ]

    @app.get("/algorithms")
    def list_algorithms() -> Dict[str, bool]:
        return {
            algo.value: manager.supports_algorithm(algo) for algo in SimilarityAlgorithm
        }

except ImportError:
    print("FastAPI not installed. Run: pip install fastapi uvicorn")
