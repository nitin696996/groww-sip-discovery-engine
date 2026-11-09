from typing import Any, Dict, List
import httpx
from app.config import settings


class SupabaseSyncManager:
    """
    Secure backend-only Supabase PostgREST synchronizer.
    All credentials stay strictly on the server (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY).
    Mirrors cleaned & AI-tagged pipeline rows to Supabase when configured, while keeping
    local SQLite in sync for zero-latency reads and offline resilience.
    """

    def __init__(self) -> None:
        self.last_sync_status: str = (
            "CONNECTED_READY" if settings.is_supabase_configured else "LOCAL_SQLITE_MIRROR"
        )
        self.last_synced_rows: int = 0
        self.last_error: str = ""

    def _headers(self) -> Dict[str, str]:
        key = settings.supabase_service_role_key
        headers = {
            "apikey": key,
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }
        # New 2026 Supabase secret keys start with 'sb_secret_'; legacy service_role keys are JWTs
        if not key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {key}"
        else:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def get_status(self) -> Dict[str, Any]:
        configured = settings.is_supabase_configured
        return {
            "configured": configured,
            "mode": "Supabase Cloud + Local Mirror" if configured else "Local Secure Vault (Supabase Ready)",
            "table": settings.supabase_table,
            "status": self.last_sync_status if configured else "LOCAL_READY",
            "last_synced_rows": self.last_synced_rows,
            "keys_exposed_to_frontend": False,
        }

    def upsert_pipeline_rows(self, rows: List[Dict[str, Any]]) -> bool:
        """Upserts a batch of pipeline rows into Supabase via PostgREST."""
        if not settings.is_supabase_configured or not rows:
            return False

        endpoint = f"{settings.supabase_url}/rest/v1/{settings.supabase_table}?on_conflict=content_hash"
        payload = []
        for r in rows:
            payload.append(
                {
                    "content_hash": r["content_hash"],
                    "external_id": str(r.get("external_id") or ""),
                    "source": r.get("source") or "unknown",
                    "sub_source": r.get("sub_source") or "",
                    "author_handle": r.get("author_handle") or "anonymous",
                    "title": r.get("title") or "",
                    "content": r.get("content") or "",
                    "url": r.get("url") or "",
                    "rating": r.get("rating"),
                    "upvotes": int(r.get("upvotes") or 0),
                    "published_at": r.get("published_at"),
                    "ingested_at": r.get("ingested_at"),
                    "triage_score": float(r.get("triage_score") or 0.0),
                    "triage_status": r.get("triage_status") or "HIGH_SIGNAL",
                    "cleaning_status": r.get("cleaning_status") or "CLEAN_SIP_SIGNAL",
                    "cleaning_reason": r.get("cleaning_reason") or "",
                    "processed_by_llm": bool(r.get("processed_by_llm")),
                    "behavioral_trigger": r.get("behavioral_trigger") or "",
                    "sentiment_polarity": float(r.get("sentiment_polarity") or 0.0),
                    "sentiment_label": r.get("sentiment_label") or "",
                    "emotional_intensity": float(r.get("emotional_intensity") or 0.0),
                    "segment_proxy_ticket": r.get("segment_proxy_ticket") or "",
                    "segment_proxy_tenure": r.get("segment_proxy_tenure") or "",
                    "retention_dropoff_bucket": r.get("retention_dropoff_bucket") or "",
                    "opportunity_score": int(r.get("opportunity_score") or 0),
                    "recommended_action": r.get("recommended_action") or "",
                    "verbatim_quote": r.get("verbatim_quote") or "",
                    "extracted_by_provider": r.get("extracted_by_provider") or "",
                    "analyzed_at": r.get("analyzed_at"),
                }
            )

        try:
            with httpx.Client(timeout=12.0) as client:
                resp = client.post(endpoint, headers=self._headers(), json=payload)
                if resp.status_code in (200, 201, 204):
                    self.last_sync_status = "SYNCED"
                    self.last_synced_rows += len(payload)
                    self.last_error = ""
                    return True
                self.last_sync_status = f"HTTP_{resp.status_code}"
                self.last_error = resp.text[:200]
                return False
        except Exception as exc:
            self.last_sync_status = "OFFLINE_FALLBACK"
            self.last_error = str(exc)[:200]
            return False


supabase_sync = SupabaseSyncManager()
