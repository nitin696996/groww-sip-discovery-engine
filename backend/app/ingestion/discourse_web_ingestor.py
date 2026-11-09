import re
from datetime import datetime, timezone
from typing import Any, Dict, List
import httpx
from app.config import settings
from app.db.models import get_db, upsert_raw_document
from app.triage.signal_filter import score_document_signal


def _strip_html(raw_html: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", raw_html or "")
    return " ".join(clean.split())


def fetch_tradingqna_and_web(max_topics: int = 12) -> Dict[str, Any]:
    """
    Ingests Indian retail investor threads from TradingQ&A (Discourse public .json API at zero cost)
    plus optional Tavily / Firecrawl search if API keys are provided.
    """
    collected: List[Dict[str, Any]] = []
    modes_used: List[str] = ["tradingqna-discourse-json"]
    errors: List[str] = []

    # 1. Native Discourse JSON endpoint on TradingQ&A (Zero cost, no API key required)
    queries = settings.discovery_queries[:5] or [
        "SIP pause stop mutual fund",
        "Groww mutual fund mandate",
        "first SIP XIRR negative",
    ]
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True, headers={"User-Agent": settings.reddit_user_agent}) as client:
            for q in queries:
                resp = client.get("https://tradingqna.com/search.json", params={"q": q})
                if resp.status_code != 200:
                    continue
                data = resp.json()
                posts = data.get("posts", [])
                topics = {t["id"]: t for t in data.get("topics", []) if "id" in t}
                for post in posts[: max_topics // len(queries) + 2]:
                    blurb = _strip_html(post.get("blurb") or "")
                    topic_id = post.get("topic_id")
                    topic_info = topics.get(topic_id, {})
                    title = topic_info.get("title") or post.get("topic_title_headline") or "TradingQ&A Discussion"
                    title = _strip_html(title)
                    if len(blurb) < 25:
                        continue
                    slug = topic_info.get("slug", "topic")
                    collected.append(
                        {
                            "external_id": f"tq_{post.get('id', topic_id)}",
                            "source": "tradingqna",
                            "sub_source": "TradingQ&A (Discourse Forum)",
                            "author": post.get("username", "tqna_member"),
                            "title": title,
                            "content": f"{title}\n\n{blurb}",
                            "url": f"https://tradingqna.com/t/{slug}/{topic_id}",
                            "upvotes": int(post.get("like_count") or 0),
                            "published_at": post.get("created_at") or datetime.now(timezone.utc).isoformat(),
                        }
                    )
    except Exception as exc:
        errors.append(f"TradingQ&A JSON note: {exc}")

    # 2. Optional Tavily Search API for broader Indian investing forums & blogs
    if settings.tavily_api_key:
        modes_used.append("tavily-search")
        try:
            with httpx.Client(timeout=20.0) as client:
                tavily_queries = [
                    "Groww mutual fund SIP pause stop mandate NAV allotment experience India forum",
                    "Groww SIP NACH bounce UPI autopay failed India",
                    "site:tradingqna.com Groww SIP XIRR negative",
                ]
                for tq_idx, tq in enumerate(tavily_queries):
                    t_resp = client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": settings.tavily_api_key,
                            "query": tq,
                            "search_depth": "basic",
                            "max_results": 8,
                        },
                    )
                    if t_resp.status_code != 200:
                        continue
                    for idx, res in enumerate(t_resp.json().get("results", [])):
                        content = (res.get("content") or "").strip()
                        title = (res.get("title") or "Web Discussion").strip()
                        if len(content) > 40:
                            collected.append(
                                {
                                    "external_id": f"tav_{tq_idx}_{idx}_{hash(res.get('url', ''))}",
                                    "source": "tradingqna",
                                    "sub_source": "Tavily Web Discovery",
                                    "author": "web_investor",
                                    "title": title,
                                    "content": f"{title}\n\n{content}",
                                    "url": res.get("url", ""),
                                    "upvotes": 1,
                                    "published_at": datetime.now(timezone.utc).isoformat(),
                                }
                            )
        except Exception as exc:
            errors.append(f"Tavily error: {exc}")

    # 3. Optional Firecrawl scrape if configured
    if settings.firecrawl_api_key:
        modes_used.append("firecrawl-scrape")
        try:
            with httpx.Client(timeout=25.0) as client:
                f_resp = client.post(
                    "https://api.firecrawl.dev/v1/search",
                    headers={"Authorization": f"Bearer {settings.firecrawl_api_key}"},
                    json={
                        "query": "site:tradingqna.com OR site:reddit.com Groww SIP pause stop XIRR",
                        "limit": 8,
                    },
                )
                if f_resp.status_code == 200:
                    for idx, item in enumerate(f_resp.json().get("data", [])):
                        md = (item.get("markdown") or item.get("description") or "").strip()
                        title = (item.get("title") or "Firecrawl Forum Extract").strip()
                        if len(md) > 40:
                            collected.append(
                                {
                                    "external_id": f"fc_{idx}_{hash(item.get('url', ''))}",
                                    "source": "tradingqna",
                                    "sub_source": "Firecrawl Deep Forum Crawl",
                                    "author": "forum_investor",
                                    "title": title,
                                    "content": f"{title}\n\n{md[:1200]}",
                                    "url": item.get("url", ""),
                                    "upvotes": 1,
                                    "published_at": datetime.now(timezone.utc).isoformat(),
                                }
                            )
        except Exception as exc:
            errors.append(f"Firecrawl error: {exc}")

    inserted = 0
    high_signal = 0
    low_signal = 0

    for item in collected:
        score, status, reasons = score_document_signal(item["title"], item["content"], item["source"])
        doc_id = upsert_raw_document(
            {
                "external_id": item["external_id"],
                "source": item["source"],
                "sub_source": item["sub_source"],
                "author_handle": item["author"],
                "title": item["title"],
                "content": item["content"],
                "url": item["url"],
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

    mode_str = "+".join(modes_used)
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO ingestion_runs (source, mode, fetched_count, inserted_count, high_signal_count, low_signal_filtered, status, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "tradingqna",
                mode_str,
                len(collected),
                inserted,
                high_signal,
                low_signal,
                "SUCCESS" if collected else "PARTIAL",
                "; ".join(errors) if errors else f"Fetched {len(collected)} threads via {mode_str}",
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return {
        "source": "tradingqna",
        "mode": mode_str,
        "fetched": len(collected),
        "inserted": inserted,
        "high_signal": high_signal,
        "low_signal_filtered": low_signal,
        "details": "; ".join(errors) if errors else f"TradingQ&A + Web ingestion completed via {mode_str}",
    }
