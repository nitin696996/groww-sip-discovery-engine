import os
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = Path(os.getenv("DB_PATH", "/tmp/discovery_engine.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _split_keys(env_var: str) -> List[str]:
    raw = os.getenv(env_var, "").strip()
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]


class Settings:
    """Centralized runtime settings with runtime key injection support."""

    def __init__(self) -> None:
        self.db_path: Path = DB_PATH
        self.groww_play_app_id: str = os.getenv("GROWW_PLAY_APP_ID", "com.nextbillion.groww")
        self.groww_ios_app_id: str = os.getenv("GROWW_IOS_APP_ID", "1404871703")
        self.groww_ios_app_name: str = os.getenv("GROWW_IOS_APP_NAME", "groww-stocks-mutual-fund")

        # Multi-key pools per LLM provider
        self.gemini_api_keys: List[str] = _split_keys("GEMINI_API_KEYS")
        if os.getenv("GEMINI_API_KEY") and os.getenv("GEMINI_API_KEY") not in self.gemini_api_keys:
            self.gemini_api_keys.append(os.getenv("GEMINI_API_KEY", "").strip())

        self.mistral_api_keys: List[str] = _split_keys("MISTRAL_API_KEYS")
        if os.getenv("MISTRAL_API_KEY") and os.getenv("MISTRAL_API_KEY") not in self.mistral_api_keys:
            self.mistral_api_keys.append(os.getenv("MISTRAL_API_KEY", "").strip())

        self.openrouter_api_keys: List[str] = _split_keys("OPENROUTER_API_KEYS")
        if os.getenv("OPENROUTER_API_KEY") and os.getenv("OPENROUTER_API_KEY") not in self.openrouter_api_keys:
            self.openrouter_api_keys.append(os.getenv("OPENROUTER_API_KEY", "").strip())

        self.grok_api_keys: List[str] = _split_keys("GROK_API_KEYS")
        if os.getenv("XAI_API_KEY") and os.getenv("XAI_API_KEY") not in self.grok_api_keys:
            self.grok_api_keys.append(os.getenv("XAI_API_KEY", "").strip())

        self.groq_api_keys: List[str] = _split_keys("GROQ_API_KEYS")
        if os.getenv("GROQ_API_KEY") and os.getenv("GROQ_API_KEY") not in self.groq_api_keys:
            self.groq_api_keys.append(os.getenv("GROQ_API_KEY", "").strip())

        # Ingestion API keys
        self.youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "").strip()
        self.reddit_client_id: str = os.getenv("REDDIT_CLIENT_ID", "").strip()
        self.reddit_client_secret: str = os.getenv("REDDIT_CLIENT_SECRET", "").strip()
        self.reddit_user_agent: str = os.getenv(
            "REDDIT_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) groww-discovery-research/1.0"
        )
        self.tavily_api_key: str = os.getenv("TAVILY_API_KEY", "").strip()
        self.firecrawl_api_key: str = os.getenv("FIRECRAWL_API_KEY", "").strip()

        # Target subreddits for Indian retail investing & SIP conversations
        self.target_subreddits: List[str] = [
            "MutualfundsIndia",
            "IndiaInvestments",
            "personalfinanceindia",
            "IndianStreetBets",
        ]

        # Target search queries across Reddit, YouTube, TradingQ&A, and Web
        self.discovery_queries: List[str] = [
            "Groww SIP pause stop mandate",
            "started first SIP expectation XIRR negative",
            "Groww mutual fund NAV allotment delayed bank deducted",
            "stopped SIP market crash panic India",
            "Groww autopay OTM mandate bank charge",
            "how often check mutual fund portfolio Groww",
            "too many mutual funds SIP overlap beginner",
            "direct vs regular mutual fund Groww confusion",
        ]

        # Micro-batching parameters
        self.micro_batch_size: int = int(os.getenv("MICRO_BATCH_SIZE", "15"))
        self.min_triage_score_for_llm: float = float(os.getenv("MIN_TRIAGE_SCORE", "0.32"))

        # Backend-only Supabase configuration (Never exposed to frontend)
        # Supports both the new 2026 Secret Key (sb_secret_...) and legacy service_role JWT
        self.supabase_url: str = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        self.supabase_service_role_key: str = (
            os.getenv("SUPABASE_SECRET_KEY", "").strip()
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.getenv("SUPABASE_KEY", "").strip()
        )
        self.supabase_table: str = os.getenv("SUPABASE_TABLE", "sip_pipeline_rows").strip()

    @property
    def is_supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)


settings = Settings()
