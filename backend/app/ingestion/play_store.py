from datetime import datetime, timezone
from typing import Any, Dict, List
from app.config import settings
from app.db.models import get_db, upsert_raw_document
from app.triage.signal_filter import score_document_signal


def _pull_play_reviews(reviews_fn, sort, max_reviews: int) -> List[Dict[str, Any]]:
    fetched: List[Dict[str, Any]] = []
    continuation_token = None
    batch_size = min(max_reviews, 100)
    while len(fetched) < max_reviews:
        result, continuation_token = reviews_fn(
            settings.groww_play_app_id,
            lang="en",
            country="in",
            sort=sort,
            count=batch_size,
            continuation_token=continuation_token,
        )
        if not result:
            break
        fetched.extend(result)
        if not continuation_token:
            break
    return fetched[:max_reviews]


def fetch_play_store_reviews(max_reviews: int = 150) -> Dict[str, Any]:
    """
    Fetches Groww Play Store reviews (India) using google-play-scraper.
    Pulls both newest and most-relevant so short 5-star praise does not crowd out
    longer SIP / mandate complaints.
    """
    fetched: List[Dict[str, Any]] = []
    error_detail = ""
    try:
        from google_play_scraper import Sort, reviews

        per_sort = max(max_reviews, 80)
        newest = _pull_play_reviews(reviews, Sort.NEWEST, per_sort)
        relevant = _pull_play_reviews(reviews, Sort.MOST_RELEVANT, per_sort)
        seen = set()
        for item in newest + relevant:
            rid = str(item.get("reviewId") or "")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            fetched.append(item)
    except Exception as exc:
        error_detail = f"google-play-scraper warning: {exc}"

    inserted = 0
    high_signal = 0
    low_signal = 0

    for item in fetched:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        score, status, reasons = score_document_signal("", content, "play_store")
        at_dt = item.get("at")
        pub_iso = at_dt.isoformat() if hasattr(at_dt, "isoformat") else datetime.now(timezone.utc).isoformat()
        review_id = str(item.get("reviewId") or "")

        doc_id = upsert_raw_document(
            {
                "external_id": f"gp_{review_id[:24]}",
                "source": "play_store",
                "sub_source": f"Google Play India (v{item.get('reviewCreatedVersion') or 'latest'})",
                "author_handle": item.get("userName") or "PlayStoreUser",
                "title": f"{item.get('score', 4)}★ Google Play Review",
                "content": content,
                "url": f"https://play.google.com/store/apps/details?id={settings.groww_play_app_id}&reviewId={review_id}",
                "rating": item.get("score"),
                "upvotes": int(item.get("thumbsUpCount") or 0),
                "published_at": pub_iso,
                "triage_score": score,
                "triage_status": status,
                "triage_reasons": reasons,
            }
        )
        if doc_id is not None:
            inserted += 1
            if status == "HIGH_SIGNAL":
                high_signal += 1
            else:
                low_signal += 1

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO ingestion_runs (source, mode, fetched_count, inserted_count, high_signal_count, low_signal_filtered, status, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "play_store",
                "google-play-scraper",
                len(fetched),
                inserted,
                high_signal,
                low_signal,
                "SUCCESS" if fetched else "PARTIAL",
                error_detail or f"Fetched {len(fetched)} unique reviews (newest + most relevant) from {settings.groww_play_app_id}",
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return {
        "source": "play_store",
        "fetched": len(fetched),
        "inserted": inserted,
        "high_signal": high_signal,
        "low_signal_filtered": low_signal,
        "details": error_detail or "Live Google Play Store scrape completed",
    }
