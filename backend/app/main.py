from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.db.models import get_db, init_db
from app.db.supabase_sync import supabase_sync
from app.ingestion.app_store import fetch_app_store_reviews
from app.ingestion.discourse_web_ingestor import fetch_tradingqna_and_web
from app.ingestion.play_store import fetch_play_store_reviews
from app.ingestion.reddit_ingestor import fetch_reddit_discussions
from app.ingestion.seed_realistic_corpus import seed_baseline_corpus
from app.ingestion.youtube_ingestor import fetch_youtube_comments
from app.llm.extractor import process_pending_micro_batches, run_sandbox_pipeline_test
from app.llm.router import llm_router
from app.synthesis import (
    ask_discovery_engine,
    get_ai_evals_suite,
    get_nine_questions_analysis,
    get_overview_metrics,
    get_pipeline_workspace_data,
    get_segment_comparison_matrix,
    get_unmet_needs_radar,
    search_evidence_corpus,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Groww AI-Powered Behavioral Discovery Engine",
    description="4-Stage Pipeline: Multi-source Scraping & Deduplication, Contextual SIP Cleaning, LLM Semantic Tagging, and Opportunity Area Scoring Engine.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://groww-sip-discovery-engine-xi.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class IngestRequest(BaseModel):
    source: str = "all"  # play_store, app_store, reddit, youtube, tradingqna, all
    limit: int = 120
    auto_extract: bool = False


class AnalyzePipelineRequest(BaseModel):
    row_ids: Optional[List[int]] = None
    reanalyze_all: bool = False


class SandboxCommentRequest(BaseModel):
    content: str
    source: str = "reddit"
    save_to_sheet: bool = False


class AskRequest(BaseModel):
    question: str


@app.get("/")
def root_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "Groww 4-Stage Behavioral Discovery Pipeline API",
        "frontend_url": "http://127.0.0.1:5173",
        "api_docs": "http://127.0.0.1:8000/docs",
        "health_endpoint": "http://127.0.0.1:8000/api/health",
    }


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "Groww 4-Stage Behavioral Discovery Pipeline",
        "supabase": supabase_sync.get_status(),
    }


@app.get("/api/pipeline/sheet")
def api_pipeline_sheet(
    source: str = Query("all"),
    cleaning_status: str = Query("CLEAN_SIP_SIGNAL"),
    trigger: str = Query("all"),
    q: str = Query(""),
) -> Dict[str, Any]:
    return get_pipeline_workspace_data(
        source_filter=source,
        cleaning_filter=cleaning_status,
        trigger_filter=trigger,
        search_query=q,
    )


@app.post("/api/pipeline/analyze")
def api_pipeline_analyze(req: AnalyzePipelineRequest) -> Dict[str, Any]:
    with get_db() as conn:
        if req.row_ids:
            placeholders = ",".join("?" for _ in req.row_ids)
            conn.execute(
                f"UPDATE raw_documents SET processed_by_llm = 0 WHERE id IN ({placeholders})",
                req.row_ids,
            )
        elif req.reanalyze_all:
            conn.execute(
                "UPDATE raw_documents SET processed_by_llm = 0 WHERE cleaning_status = 'CLEAN_SIP_SIGNAL'"
            )
        else:
            # Incremental mode: if all rows are already tagged, refresh only the newest 8 rows in 1 fast batch
            pending_cnt = conn.execute(
                "SELECT COUNT(*) FROM raw_documents WHERE cleaning_status = 'CLEAN_SIP_SIGNAL' AND processed_by_llm = 0"
            ).fetchone()[0]
            if pending_cnt == 0:
                conn.execute(
                    """
                    UPDATE raw_documents
                    SET processed_by_llm = 0
                    WHERE id IN (
                        SELECT id FROM raw_documents
                        WHERE cleaning_status = 'CLEAN_SIP_SIGNAL'
                        ORDER BY id DESC
                        LIMIT 8
                    )
                    """
                )

    batch_summary = process_pending_micro_batches(max_batches=1, force_reprocess=True)
    workspace = get_pipeline_workspace_data()
    return {
        "status": "analyzed",
        "batch_summary": batch_summary,
        "workspace": workspace,
    }


@app.get("/api/overview")
def api_overview() -> Dict[str, Any]:
    return get_overview_metrics()


@app.get("/api/questions")
def api_nine_questions(
    source: str = Query("all"),
    segment: str = Query("all"),
) -> Dict[str, Any]:
    return {
        "questions": get_nine_questions_analysis(source_filter=source, segment_filter=segment),
    }


@app.get("/api/segments")
def api_segments() -> Dict[str, Any]:
    return {"dimensions": get_segment_comparison_matrix()}


@app.get("/api/evals")
def api_ai_evals() -> Dict[str, Any]:
    return get_ai_evals_suite()


@app.post("/api/pipeline/test-comment")
def api_test_sandbox_comment(req: SandboxCommentRequest) -> Dict[str, Any]:
    return run_sandbox_pipeline_test(
        content=req.content,
        source=req.source,
        save_to_sheet=req.save_to_sheet,
    )


@app.get("/api/unmet-needs")
def api_unmet_needs() -> Dict[str, Any]:
    return {"opportunities": get_unmet_needs_radar()}


@app.get("/api/evidence")
def api_evidence(
    q: str = Query(""),
    source: str = Query("all"),
    stage: str = Query("all"),
    question_id: str = Query("all"),
) -> Dict[str, Any]:
    items = search_evidence_corpus(query_str=q, source=source, stage=stage, question_id=question_id)
    return {"count": len(items), "items": items}


@app.post("/api/ingest")
def api_trigger_ingestion(req: IngestRequest) -> Dict[str, Any]:
    results = []
    src = req.source.lower()

    if src in ("play_store", "all"):
        results.append(fetch_play_store_reviews(max_reviews=max(req.limit, 80)))
    if src in ("app_store", "all"):
        results.append(fetch_app_store_reviews(max_pages=8))
    if src in ("reddit", "all"):
        results.append(fetch_reddit_discussions(limit_per_sub=max(25, req.limit // 4)))
    if src in ("tradingqna", "all"):
        results.append(fetch_tradingqna_and_web(max_topics=24))
    if src in ("youtube", "all"):
        results.append(fetch_youtube_comments(max_videos=4, comments_per_video=40))

    extraction_summary = {}
    if req.auto_extract:
        extraction_summary = process_pending_micro_batches(max_batches=4)

    return {
        "ingestion_results": results,
        "extraction_summary": extraction_summary,
        "workspace": get_pipeline_workspace_data(),
    }


@app.post("/api/llm/process-batches")
def api_process_batches(max_batches: int = 5) -> Dict[str, Any]:
    summary = process_pending_micro_batches(max_batches=max_batches)
    return {
        "batch_summary": summary,
        "router_telemetry": llm_router.get_telemetry_summary(),
    }


@app.get("/api/llm/telemetry")
def api_llm_telemetry() -> Dict[str, Any]:
    return llm_router.get_telemetry_summary()


@app.post("/api/ask")
def api_ask_question(req: AskRequest) -> Dict[str, Any]:
    return ask_discovery_engine(req.question)
