from datetime import datetime, timezone
from typing import Any, Dict, List
import httpx
from app.config import settings
from app.db.models import get_db, upsert_raw_document
from app.triage.signal_filter import score_document_signal

REDDIT_SEARCH_QUERY = "Groww SIP OR mandate OR XIRR OR NACH OR pause OR autopay OR OTM"


def _post_record(
    post_id: str,
    sub_name: str,
    author: str,
    title: str,
    body: str,
    url: str,
    upvotes: int,
    published_at: str,
    is_comment: bool = False,
) -> Dict[str, Any]:
    return {
        "id": post_id,
        "sub_source": f"r/{sub_name}",
        "author": author or "redditor",
        "title": title,
        "content": f"{title}\n\n{body}".strip() if not is_comment else body,
        "url": url,
        "upvotes": upvotes,
        "published_at": published_at,
    }


def _fetch_thread_comments(
    client: httpx.Client,
    post_id: str,
    sub_name: str,
    post_title: str,
    post_url: str,
    limit: int = 12,
) -> List[Dict[str, Any]]:
    comments: List[Dict[str, Any]] = []
    try:
        resp = client.get(
            f"https://old.reddit.com/comments/{post_id}.json",
            params={"limit": limit, "sort": "top", "depth": 1},
        )
        if resp.status_code != 200:
            return comments
        payload = resp.json()
        if not isinstance(payload, list) or len(payload) < 2:
            return comments
        children = payload[1].get("data", {}).get("children", [])
        for child in children:
            if child.get("kind") != "t1":
                continue
            d = child.get("data", {})
            body = (d.get("body") or "").strip()
            if len(body.split()) < 8:
                continue
            cid = d.get("id") or ""
            created_utc = d.get("created_utc") or datetime.now(timezone.utc).timestamp()
            permalink = d.get("permalink") or ""
            comments.append(
                _post_record(
                    post_id=f"{post_id}_{cid}",
                    sub_name=sub_name,
                    author=d.get("author") or "redditor",
                    title=f"Comment on: {post_title}",
                    body=body,
                    url=f"https://www.reddit.com{permalink}" if permalink else post_url,
                    upvotes=int(d.get("ups") or d.get("score") or 0),
                    published_at=datetime.fromtimestamp(float(created_utc), tz=timezone.utc).isoformat(),
                    is_comment=True,
                )
            )
    except Exception:
        return comments
    return comments


def fetch_reddit_discussions(limit_per_sub: int = 25) -> Dict[str, Any]:
    """
    Ingests posts AND top comments from Indian investing subreddits.
    Uses PRAW if Reddit OAuth is configured; otherwise public .json, then Tavily as a supplement.
    """
    posts_collected: List[Dict[str, Any]] = []
    seen_ids = set()
    mode_used = "public-json-api"
    error_detail = ""
    subs = settings.target_subreddits

    def add_post(record: Dict[str, Any]) -> None:
        rid = str(record.get("id") or "")
        if not rid or rid in seen_ids:
            return
        seen_ids.add(rid)
        posts_collected.append(record)

    if settings.reddit_client_id and settings.reddit_client_secret:
        try:
            import praw

            mode_used = "praw-oauth"
            reddit = praw.Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent,
            )
            for sub_name in subs:
                subreddit = reddit.subreddit(sub_name)
                for submission in subreddit.search(REDDIT_SEARCH_QUERY, sort="new", limit=limit_per_sub):
                    body = (submission.selftext or "").strip()
                    if not body and not submission.title:
                        continue
                    add_post(
                        _post_record(
                            post_id=submission.id,
                            sub_name=sub_name,
                            author=str(submission.author or "redditor"),
                            title=submission.title,
                            body=body,
                            url=f"https://www.reddit.com{submission.permalink}",
                            upvotes=int(submission.score or 0),
                            published_at=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc).isoformat(),
                        )
                    )
                    submission.comments.replace_more(limit=0)
                    for comment in submission.comments[:12]:
                        cbody = (getattr(comment, "body", None) or "").strip()
                        if len(cbody.split()) < 8:
                            continue
                        add_post(
                            _post_record(
                                post_id=f"{submission.id}_{comment.id}",
                                sub_name=sub_name,
                                author=str(getattr(comment, "author", None) or "redditor"),
                                title=f"Comment on: {submission.title}",
                                body=cbody,
                                url=f"https://www.reddit.com{comment.permalink}",
                                upvotes=int(getattr(comment, "score", 0) or 0),
                                published_at=datetime.fromtimestamp(
                                    float(getattr(comment, "created_utc", 0) or datetime.now(timezone.utc).timestamp()),
                                    tz=timezone.utc,
                                ).isoformat(),
                                is_comment=True,
                            )
                        )
        except Exception as exc:
            error_detail = f"PRAW fallback to public JSON ({exc})"
            mode_used = "public-json-fallback"

    if not posts_collected or mode_used.startswith("public"):
        headers = {
            "User-Agent": "python:groww.behavioral.discovery.engine:v1.0.0 (by /u/groww_research)",
            "Accept": "application/json",
        }
        try:
            with httpx.Client(timeout=15.0, headers=headers, follow_redirects=True) as client:
                for sub_name in subs:
                    for domain in ("https://old.reddit.com", "https://www.reddit.com"):
                        url = (
                            f"{domain}/r/{sub_name}/search.json"
                            f"?q=Groww+SIP+OR+mandate+OR+XIRR+OR+NACH+OR+pause"
                            f"&restrict_sr=1&sort=new&limit={limit_per_sub}"
                        )
                        resp = client.get(url)
                        if resp.status_code != 200:
                            continue
                        children = resp.json().get("data", {}).get("children", [])
                        for child in children:
                            d = child.get("data", {})
                            selftext = (d.get("selftext") or "").strip()
                            title = (d.get("title") or "").strip()
                            if not selftext and len(title) < 25:
                                continue
                            created_utc = d.get("created_utc") or datetime.now(timezone.utc).timestamp()
                            add_post(
                                _post_record(
                                    post_id=d.get("id", ""),
                                    sub_name=sub_name,
                                    author=d.get("author", "redditor"),
                                    title=title,
                                    body=selftext,
                                    url=f"https://www.reddit.com{d.get('permalink', '')}",
                                    upvotes=int(d.get("ups") or d.get("score") or 0),
                                    published_at=datetime.fromtimestamp(float(created_utc), tz=timezone.utc).isoformat(),
                                )
                            )
                        break

                ranked = sorted(
                    [p for p in posts_collected if "_" not in str(p.get("id", ""))],
                    key=lambda p: int(p.get("upvotes") or 0),
                    reverse=True,
                )[:18]
                for post in ranked:
                    sub_name = (post.get("sub_source") or "r/MutualfundsIndia").replace("r/", "", 1)
                    for comment in _fetch_thread_comments(
                        client,
                        post["id"],
                        sub_name,
                        post["title"],
                        post["url"],
                    ):
                        add_post(comment)
                if ranked:
                    mode_used = f"{mode_used}+thread-comments"
        except Exception as exc:
            error_detail = f"Reddit JSON fetch warning: {exc}"

    if settings.tavily_api_key:
        tavily_added = 0
        reddit_queries = [
            "site:reddit.com/r/MutualfundsIndia Groww SIP pause stop mandate NACH",
            "site:reddit.com/r/IndiaInvestments Groww SIP XIRR negative NAV allotment",
            "site:reddit.com/r/personalfinanceindia Groww mutual fund SIP autopay bounce",
        ]
        try:
            with httpx.Client(timeout=20.0) as client:
                for rq in reddit_queries:
                    t_resp = client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": settings.tavily_api_key,
                            "query": rq,
                            "search_depth": "basic",
                            "max_results": 8,
                        },
                    )
                    if t_resp.status_code != 200:
                        continue
                    for idx, res in enumerate(t_resp.json().get("results", [])):
                        content = (res.get("content") or "").strip()
                        title = (res.get("title") or "Reddit India SIP Discussion").strip()
                        url = res.get("url", "")
                        if len(content) <= 35:
                            continue
                        sub_match = "MutualfundsIndia"
                        if "indiainvestments" in url.lower():
                            sub_match = "IndiaInvestments"
                        elif "personalfinanceindia" in url.lower():
                            sub_match = "personalfinanceindia"
                        elif "indianstreetbets" in url.lower():
                            sub_match = "IndianStreetBets"
                        add_post(
                            _post_record(
                                post_id=f"tav_rd_{abs(hash(url)) % 1000000}",
                                sub_name=sub_match,
                                author="redditor_india",
                                title=title,
                                body=content,
                                url=url,
                                upvotes=15 + (idx * 7),
                                published_at=datetime.now(timezone.utc).isoformat(),
                            )
                        )
                        tavily_added += 1
            if tavily_added:
                mode_used = f"{mode_used}+tavily-reddit"
        except Exception as exc:
            error_detail = f"Tavily Reddit search warning: {exc}"

    inserted = 0
    high_signal = 0
    low_signal = 0

    for post in posts_collected:
        score, status, reasons = score_document_signal(post["title"], post["content"], "reddit")
        doc_id = upsert_raw_document(
            {
                "external_id": f"rd_{post['id']}",
                "source": "reddit",
                "sub_source": post["sub_source"],
                "author_handle": f"u/{post['author']}",
                "title": post["title"],
                "content": post["content"],
                "url": post["url"],
                "rating": None,
                "upvotes": post["upvotes"],
                "published_at": post["published_at"],
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
                "reddit",
                mode_used,
                len(posts_collected),
                inserted,
                high_signal,
                low_signal,
                "SUCCESS" if posts_collected else "PARTIAL",
                error_detail or f"Fetched {len(posts_collected)} Reddit posts+comments via {mode_used}",
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return {
        "source": "reddit",
        "mode": mode_used,
        "fetched": len(posts_collected),
        "inserted": inserted,
        "high_signal": high_signal,
        "low_signal_filtered": low_signal,
        "details": error_detail or f"Reddit ingestion via {mode_used} completed",
    }
