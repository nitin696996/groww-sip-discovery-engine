import re
from typing import Any, Dict, List, Tuple
from app.config import settings

# Lexicons mapped to Indian retail investing & SIP behavioral dimensions
BEHAVIORAL_LEXICONS: Dict[str, List[str]] = {
    "q1_trigger_expectation": [
        "started sip", "first sip", "new to investing", "beginner", "expected",
        "fd return", "fixed deposit", "15%", "20%", "double money", "tax saving",
        "elss", "80c", "first salary", "finfluencer", "warikoo", "rachana", "akshat",
        "pranjal", "colleague", "friend suggested", "inflation", "compounding",
    ],
    "q2_post_start_behavior": [
        "after 3 months", "after 6 months", "switched", "added more funds",
        "too many funds", "8 funds", "10 funds", "overlap", "small cap", "mid cap",
        "thematic", "nfo", "sector fund", "rebalanced", "step up", "increased sip",
    ],
    "q3_pause_stop_drivers": [
        "paused", "stopped sip", "cancel sip", "redeemed", "withdrew", "skip",
        "emi", "cash crunch", "emergency", "medical", "job loss", "negative return",
        "in red", "loss", "market crash", "falling", "all time high", "ath",
        "bounce charge", "penalty", "ecs bounce", "nach penalty",
    ],
    "q4_checking_habits": [
        "check daily", "every day", "1d return", "day change", "xirr", "cagr",
        "absolute return", "portfolio value", "nav update", "10 pm", "9 pm",
        "morning", "obsessed", "uninstall", "Refresh",
    ],
    "q5_in_app_confusion": [
        "nav", "allotment", "units not allotted", "money deducted", "bank debited",
        "order in progress", "t+1", "t+2", "cut off", "2 pm", "3 pm", "autopay",
        "mandate", "otm", "nach", "upi autopay", "exit load", "stcg", "ltcg",
        "stamp duty", "folio", "external fund", "import", "karvy", "cams", "kfintech",
        "direct vs regular", "expense ratio",
    ],
    "q6_external_validation": [
        "review my portfolio", "rate my portfolio", "am i doing right",
        "please suggest", "should i hold or sell", "valueresearch", "morningstar",
        "tickertape", "et money", "advisor", "youtube video", "telegram",
        "reddit", "quora", "tradingqna", "asked my friend", "ca told",
    ],
    "q7_retention_vs_dropoff": [
        "5 years", "7 years", "10 years", "long term", "goal", "retirement",
        "house downpayment", "automated", "set and forget", "ignored crash",
        "quietly stopped", "never restarted", "gave up", "back to fd",
    ],
    "q8_segmentation_markers": [
        "salaried", "salary", "it engineer", "fresher", "21 yo", "22M", "23F",
        "24M", "25M", "28M", "30M", "student", "internship", "stipend",
        "pocket money", "freelance", "freelancer", "business", "irregular income",
        "parents", "father", "bonus",
    ],
}

LOW_SIGNAL_EXACT_PATTERNS = re.compile(
    r"^(good|nice|best|awesome|super|great|ok|okay|bad|worst|useless|bakwas|love it|nice app|good app|best app|very good|5 stars|1 star|update issue|login issue|otp not coming)[\s.!]*$",
    re.IGNORECASE,
)

SPAM_PROMO_PATTERNS = re.compile(
    r"(referral code|promo code|use my code|join telegram|whatsapp group link|free signal|guaranteed profit|earn ₹\d+ daily|signup bonus|refer and earn)",
    re.IGNORECASE,
)


def classify_cleaning_status(title: str, content: str, triage_status: str, reasons: List[str]) -> Tuple[str, str]:
    """
    Stage 2 Contextual Enrichment & Cleaning:
    Categorizes each ingested document into:
    - CLEAN_SIP_SIGNAL: Relevant SIP behavioral feedback kept for spreadsheet & AI tagging
    - FILTERED_SPAM_PROMO: Spam, referral codes, promotional links
    - FILTERED_NON_SIP: Short app praise, OTP/login bugs, or non-SIP stock grievances
    """
    full_text = f"{title or ''} {content or ''}".strip()
    if SPAM_PROMO_PATTERNS.search(full_text):
        return "FILTERED_SPAM_PROMO", "Removed promo code / referral spam"
    if triage_status != "HIGH_SIGNAL":
        if "too_short_or_generic_praise" in reasons:
            return "FILTERED_NON_SIP", "Removed 1-4 word generic app store praise/one-liner"
        return "FILTERED_NON_SIP", "Removed non-SIP grievance (login/OTP/F&O noise)"
    return "CLEAN_SIP_SIGNAL", "Verified SIP behavioral narrative"


def score_document_signal(title: str, content: str, source: str = "") -> Tuple[float, str, List[str]]:
    """
    Deterministic zero-token behavioral signal scorer.
    Returns (score 0.0..1.0, triage_status, matched_reasons).
    Strips 1-6 word generic Play/App store reviews, YouTube greetings ("Radhe Radhe", "Nice video"),
    and promo spam before they ever touch an LLM.
    """
    body_text = (content or "").strip()
    body_words = body_text.split()
    body_word_count = len(body_words)

    # For YouTube comments and store reviews, score strictly on the comment body (do not let video title inflate score)
    if source in ("youtube", "play_store", "app_store"):
        eval_text = body_text
    else:
        eval_text = f"{title or ''} {body_text}".strip()

    if SPAM_PROMO_PATTERNS.search(eval_text):
        return 0.02, "LOW_SIGNAL_NOISE", ["spam_or_promo_code"]

    if body_word_count < 6 or LOW_SIGNAL_EXACT_PATTERNS.match(body_text):
        return 0.05, "LOW_SIGNAL_NOISE", ["too_short_or_generic_praise"]

    lower_text = eval_text.lower()
    matched_dimensions: List[str] = []
    keyword_hits = 0

    for dimension, phrases in BEHAVIORAL_LEXICONS.items():
        dim_hits = [p for p in phrases if p in lower_text]
        if dim_hits:
            matched_dimensions.append(f"{dimension}({len(dim_hits)})")
            keyword_hits += len(dim_hits)

    # Check general SIP / mutual fund core anchor terms (English + Hinglish)
    core_anchors = [
        "sip", "mutual fund", "mf", "groww", "nav", "xirr", "mandate", "autopay",
        "folio", "elss", "nifty", "index fund", "lumpsum", "lumsum", "redeem",
        "withdrawal", "direct", "regular plan", "demat", "soa",
    ]
    anchor_hits = sum(1 for a in core_anchors if a in lower_text)

    if anchor_hits == 0 and keyword_hits == 0:
        return 0.12, "LOW_SIGNAL_NOISE", ["no_investing_or_sip_context"]

    # Calculate richness score from body word count, multi-dimension matches, and narrative markers
    length_bonus = min(body_word_count / 70.0, 0.30)
    dimension_bonus = min(len(matched_dimensions) * 0.14, 0.56)
    anchor_bonus = min(anchor_hits * 0.06, 0.24)

    # First-person behavioral narrative markers (English + Hinglish)
    narrative_markers = [
        "i started", "my sip", "i paused", "i stopped", "confused", "worried",
        "scared", "deducted", "expect", "should i", "maine", "mera", "mere",
        "kaise", "kya", "plz reply", "batao",
    ]
    narrative_bonus = 0.12 if any(m in lower_text for m in narrative_markers) else 0.0

    raw_score = round(min(length_bonus + dimension_bonus + anchor_bonus + narrative_bonus, 0.99), 3)

    if raw_score >= settings.min_triage_score_for_llm:
        return raw_score, "HIGH_SIGNAL", matched_dimensions or ["core_investing_narrative"]
    return raw_score, "LOW_SIGNAL_NOISE", matched_dimensions or ["low_behavioral_depth"]


def extract_best_verbatim_quote(content: str) -> str:
    """Extracts the highest-signal 1-2 sentences from a longer post for verbatim citation."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", content.strip()) if len(s.strip()) > 18]
    if not sentences:
        return content.strip()[:280]

    scored: List[Tuple[int, str]] = []
    priority_terms = [
        "sip", "pause", "stop", "mandate", "autopay", "nav", "xirr", "deduct",
        "red", "loss", "crash", "check", "expect", "fd", "confus", "worry",
        "scared", "penalty", "bounce", "reddit", "youtube", "salary",
    ]
    for idx, sent in enumerate(sentences):
        s_low = sent.lower()
        hits = sum(2 for t in priority_terms if t in s_low)
        if 40 <= len(sent) <= 240:
            hits += 2
        scored.append((hits, sent))

    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0][1]
    return best[:300]
