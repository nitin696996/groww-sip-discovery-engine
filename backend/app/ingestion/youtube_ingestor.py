from datetime import datetime, timezone
from typing import Any, Dict, List
import httpx
from app.config import settings
from app.db.models import get_db, upsert_raw_document
from app.triage.signal_filter import score_document_signal

YOUTUBE_QUERIES = [
    "Groww SIP mutual fund beginner India",
    "Groww SIP pause stop mandate NACH",
    "Groww SIP XIRR negative first year",
]


def fetch_youtube_comments(max_videos: int = 4, comments_per_video: int = 40) -> Dict[str, Any]:
    """
    Uses YouTube Data API v3 to search several SIP-related queries and pull top-level comments.
    Search costs 100 quota units per query; commentThreads cost 1 unit each.
    """
    if not settings.youtube_api_key:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO ingestion_runs (source, mode, fetched_count, inserted_count, high_signal_count, low_signal_filtered, status, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "youtube",
                    "youtube-data-api-v3",
                    0,
                    0,
                    0,
                    0,
                    "SKIPPED_NO_KEY",
                    "Set YOUTUBE_API_KEY in Control Center or .env to fetch live YouTube Data API v3 comments (10,000 free units/day).",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return {
            "source": "youtube",
            "fetched": 0,
            "inserted": 0,
            "high_signal": 0,
            "low_signal_filtered": 0,
            "quota_units_used": 0,
            "details": "YOUTUBE_API_KEY not configured yet; using existing corpus comments. Add key in Control Center for live YouTube Data API v3 pulls.",
        }

    comments_collected: List[Dict[str, Any]] = []
    seen_comment_ids = set()
    seen_video_ids = set()
    quota_units_used = 0
    error_detail = ""

    try:
        with httpx.Client(timeout=15.0) as client:
            for query in YOUTUBE_QUERIES:
                search_resp = client.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={
                        "part": "snippet",
                        "q": query,
                        "type": "video",
                        "maxResults": max_videos,
                        "relevanceLanguage": "en",
                        "regionCode": "IN",
                        "key": settings.youtube_api_key,
                    },
                )
                quota_units_used += 100
                if search_resp.status_code != 200:
                    error_detail = f"YouTube API HTTP {search_resp.status_code}: {search_resp.text[:160]}"
                    continue
                for video in search_resp.json().get("items", []):
                    video_id = video.get("id", {}).get("videoId")
                    video_title = video.get("snippet", {}).get("title", "YouTube Personal Finance Video")
                    channel_title = video.get("snippet", {}).get("channelTitle", "Finance Channel")
                    if not video_id or video_id in seen_video_ids:
                        continue
                    seen_video_ids.add(video_id)

                    page_token = None
                    remaining = comments_per_video
                    while remaining > 0:
                        params = {
                            "part": "snippet",
                            "videoId": video_id,
                            "maxResults": min(remaining, 50),
                            "order": "relevance",
                            "textFormat": "plainText",
                            "key": settings.youtube_api_key,
                        }
                        if page_token:
                            params["pageToken"] = page_token
                        c_resp = client.get(
                            "https://www.googleapis.com/youtube/v3/commentThreads",
                            params=params,
                        )
                        quota_units_used += 1
                        if c_resp.status_code != 200:
                            break
                        payload = c_resp.json()
                        for thread in payload.get("items", []):
                            top = thread.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                            text = (top.get("textDisplay") or "").strip()
                            tid = thread.get("id", "")
                            if not text or tid in seen_comment_ids:
                                continue
                            seen_comment_ids.add(tid)
                            comments_collected.append(
                                {
                                    "id": tid,
                                    "video_id": video_id,
                                    "video_title": video_title,
                                    "channel": channel_title,
                                    "author": top.get("authorDisplayName", "YouTubeViewer"),
                                    "content": text,
                                    "upvotes": int(top.get("likeCount") or 0),
                                    "published_at": top.get("publishedAt") or datetime.now(timezone.utc).isoformat(),
                                }
                            )
                            remaining -= 1
                            if remaining <= 0:
                                break
                        page_token = payload.get("nextPageToken")
                        if not page_token:
                            break
    except Exception as exc:
        error_detail = f"YouTube Data API v3 error: {exc}"

    inserted = 0
    high_signal = 0
    low_signal = 0

    for item in comments_collected:
        score, status, reasons = score_document_signal(item["video_title"], item["content"], "youtube")
        doc_id = upsert_raw_document(
            {
                "external_id": f"yt_{item['id']}",
                "source": "youtube",
                "sub_source": f"YouTube ({item['channel']})",
                "author_handle": item["author"],
                "title": f"Comment on: {item['video_title']}",
                "content": item["content"],
                "url": f"https://www.youtube.com/watch?v={item['video_id']}",
                "rating": None,
                "upvotes": item["upvotes"],
                "published_at": item["published_at"],
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
                "youtube",
                "youtube-data-api-v3",
                len(comments_collected),
                inserted,
                high_signal,
                low_signal,
                "SUCCESS" if comments_collected else "ERROR",
                error_detail or f"Used {quota_units_used}/10,000 daily quota units; fetched {len(comments_collected)} comments from {len(seen_video_ids)} videos",
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return {
        "source": "youtube",
        "fetched": len(comments_collected),
        "inserted": inserted,
        "high_signal": high_signal,
        "low_signal_filtered": low_signal,
        "quota_units_used": quota_units_used,
        "details": error_detail or f"YouTube Data API v3 completed ({quota_units_used} quota units used)",
    }
