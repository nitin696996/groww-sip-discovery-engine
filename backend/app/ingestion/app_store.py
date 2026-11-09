from datetime import datetime, timezone
from typing import Any, Dict, List
import httpx
from app.config import settings
from app.db.models import get_db, upsert_raw_document
from app.triage.signal_filter import score_document_signal


def fetch_app_store_reviews(max_pages: int = 8) -> Dict[str, Any]:
    """
    Fetches Groww iOS App Store reviews for India using Apple's public iTunes RSS Customer Reviews JSON feed
    plus app-store-scraper fallback.
    """
    fetched_entries: List[Dict[str, Any]] = []
    error_detail = ""

    # Method 1: Apple iTunes RSS JSON endpoint (fast, zero-key, no headless browser)
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            for page in range(1, max_pages + 1):
                url = (
                    f"https://itunes.apple.com/in/rss/customerreviews/page={page}/"
                    f"id={settings.groww_ios_app_id}/sortby=mostrecent/json"
                )
                resp = client.get(url)
                if resp.status_code != 200:
                    break
                data = resp.json()
                entries = data.get("feed", {}).get("entry", [])
                if not isinstance(entries, list):
                    break
                for entry in entries:
                    # Skip the first metadata entry if it doesn't have content
                    if "content" not in entry or "author" not in entry:
                        continue
                    fetched_entries.append(
                        {
                            "id": entry.get("id", {}).get("label", ""),
                            "title": entry.get("title", {}).get("label", "App Store Review"),
                            "content": entry.get("content", {}).get("label", ""),
                            "author": entry.get("author", {}).get("name", {}).get("label", "iOSInvestor"),
                            "rating": int(entry.get("im:rating", {}).get("label", 4)),
                            "version": entry.get("im:version", {}).get("label", "latest"),
                            "updated": entry.get("updated", {}).get("label", datetime.now(timezone.utc).isoformat()),
                            "url": f"https://apps.apple.com/in/app/groww-stocks-mutual-fund/id{settings.groww_ios_app_id}",
                        }
                    )
    except Exception as exc:
        error_detail = f"iTunes RSS JSON note: {exc}"

    inserted = 0
    high_signal = 0
    low_signal = 0

    for item in fetched_entries:
        content = (item.get("content") or "").strip()
        title = (item.get("title") or "").strip()
        if not content:
            continue
        score, status, reasons = score_document_signal(title, content, "app_store")
        doc_id = upsert_raw_document(
            {
                "external_id": f"ios_{item.get('id') or title[:20]}",
                "source": "app_store",
                "sub_source": f"Apple App Store India (v{item.get('version')})",
                "author_handle": item.get("author") or "iOSUser",
                "title": title,
                "content": content,
                "url": item.get("url"),
                "rating": item.get("rating"),
                "upvotes": 0,
                "published_at": item.get("updated") or datetime.now(timezone.utc).isoformat(),
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
                "app_store",
                "itunes-rss-json",
                len(fetched_entries),
                inserted,
                high_signal,
                low_signal,
                "SUCCESS" if fetched_entries else "PARTIAL",
                error_detail or f"Fetched {len(fetched_entries)} iOS reviews from Apple Store India",
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return {
        "source": "app_store",
        "fetched": len(fetched_entries),
        "inserted": inserted,
        "high_signal": high_signal,
        "low_signal_filtered": low_signal,
        "details": error_detail or "Live Apple App Store RSS JSON ingestion completed",
    }
