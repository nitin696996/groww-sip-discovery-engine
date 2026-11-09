import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import httpx
from app.config import settings
from app.db.models import get_db


@dataclass
class ProviderSlot:
    slot_id: str
    provider_type: str  # gemini, mistral, openrouter, grok, groq
    model: str
    api_key: str
    rpm_limit: int
    rpd_limit: int
    request_timestamps: List[float] = field(default_factory=list)
    requests_today: int = 0
    tokens_today: int = 0
    rate_limit_hits: int = 0
    cooldown_until: float = 0.0
    last_status: str = "READY"
    last_used_at: str = ""

    def is_available(self) -> Tuple[bool, str]:
        now = time.time()
        if now < self.cooldown_until:
            remaining = int(self.cooldown_until - now)
            return False, f"COOLDOWN ({remaining}s left)"

        # Purge timestamps older than 60s
        self.request_timestamps = [ts for ts in self.request_timestamps if now - ts < 60.0]
        if len(self.request_timestamps) >= self.rpm_limit:
            return False, f"RPM_CAP_REACHED ({self.rpm_limit}/min)"

        if self.requests_today >= self.rpd_limit:
            return False, f"DAILY_QUOTA_EXHAUSTED ({self.rpd_limit}/day)"

        return True, "READY"

    def record_success(self, tokens_estimated: int) -> None:
        now = time.time()
        self.request_timestamps.append(now)
        self.requests_today += 1
        self.tokens_today += tokens_estimated
        self.last_status = "HEALTHY"
        self.last_used_at = datetime.now(timezone.utc).isoformat()
        self._persist()

    def record_rate_limit(self, retry_after_seconds: int = 65) -> None:
        self.rate_limit_hits += 1
        self.cooldown_until = time.time() + max(retry_after_seconds, 30)
        self.last_status = f"RATE_LIMITED_429 (cooldown {retry_after_seconds}s)"
        self.last_used_at = datetime.now(timezone.utc).isoformat()
        self._persist()

    def _persist(self) -> None:
        cooldown_iso = (
            datetime.fromtimestamp(self.cooldown_until, tz=timezone.utc).isoformat()
            if self.cooldown_until > time.time()
            else ""
        )
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO provider_telemetry (
                    provider_id, provider_name, model_name, rpm_limit, rpd_limit,
                    requests_today, tokens_today, rate_limit_hits, cooldown_until,
                    last_status, last_used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    requests_today=excluded.requests_today,
                    tokens_today=excluded.tokens_today,
                    rate_limit_hits=excluded.rate_limit_hits,
                    cooldown_until=excluded.cooldown_until,
                    last_status=excluded.last_status,
                    last_used_at=excluded.last_used_at
                """,
                (
                    self.slot_id,
                    self.provider_type,
                    self.model,
                    self.rpm_limit,
                    self.rpd_limit,
                    self.requests_today,
                    self.tokens_today,
                    self.rate_limit_hits,
                    cooldown_iso,
                    self.last_status,
                    self.last_used_at,
                ),
            )


class MultiProviderLLMRouter:
    """
    Solves the Free-Tier 429 Too Many Requests bottleneck by:
    1. Pooling multiple keys across Gemini, Mistral, OpenRouter (:free models), Grok (xAI), and Groq.
    2. Enforcing per-slot token-bucket RPM & RPD quotas before sending requests.
    3. Reading Retry-After headers on 429 responses, placing exhausted slots into circuit-breaker
       cooldown, and seamlessly failing over to the next healthy provider.
    """

    def __init__(self) -> None:
        self.slots: List[ProviderSlot] = []
        self.rebuild_pool()

    def rebuild_pool(self) -> None:
        self.slots = []

        # 1. Groq High-Speed Inference Tier (~1-2s latency, 30 RPM, 1,000 RPD)
        groq_models = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
        for idx, key in enumerate(settings.groq_api_keys):
            for m_slug in groq_models:
                short_m = m_slug.split("/")[-1]
                self.slots.append(
                    ProviderSlot(
                        slot_id=f"groq_{idx+1}_{short_m}",
                        provider_type="groq",
                        model=m_slug,
                        api_key=key,
                        rpm_limit=28,
                        rpd_limit=1000,
                    )
                )

        # 2. Google Gemini Free Tier (15 RPM, 1,500 RPD per key)
        for idx, key in enumerate(settings.gemini_api_keys):
            self.slots.append(
                ProviderSlot(
                    slot_id=f"gemini_key_{idx+1}",
                    provider_type="gemini",
                    model="gemini-2.5-flash",
                    api_key=key,
                    rpm_limit=15,
                    rpd_limit=1500,
                )
            )

        # 3. Mistral Free / La Plateforme Tier (1 RPS / ~30 RPM, 1,000 RPD)
        for idx, key in enumerate(settings.mistral_api_keys):
            self.slots.append(
                ProviderSlot(
                    slot_id=f"mistral_key_{idx+1}",
                    provider_type="mistral",
                    model="mistral-small-latest",
                    api_key=key,
                    rpm_limit=25,
                    rpd_limit=1000,
                )
            )

        # 4. OpenRouter :free Model Rotation (20 RPM, 200-1000 RPD across distinct free models)
        openrouter_free_models = [
            "nvidia/nemotron-3.5-lightning:free",
            "thinkingmachines/inkling:free",
            "poolside/laguna-s-2.1:free",
        ]
        for idx, key in enumerate(settings.openrouter_api_keys):
            for m_idx, model_slug in enumerate(openrouter_free_models):
                short_name = model_slug.split("/")[1].split(":")[0]
                self.slots.append(
                    ProviderSlot(
                        slot_id=f"openrouter_{idx+1}_{short_name}",
                        provider_type="openrouter",
                        model=model_slug,
                        api_key=key,
                        rpm_limit=18,
                        rpd_limit=200,
                    )
                )

        # 5. Grok (xAI) API
        for idx, key in enumerate(settings.grok_api_keys):
            self.slots.append(
                ProviderSlot(
                    slot_id=f"grok_xai_{idx+1}",
                    provider_type="grok",
                    model="grok-2-latest",
                    api_key=key,
                    rpm_limit=20,
                    rpd_limit=500,
                )
            )

    def get_telemetry_summary(self) -> Dict[str, Any]:
        configured_slots = []
        for s in self.slots:
            avail, reason = s.is_available()
            configured_slots.append(
                {
                    "slot_id": s.slot_id,
                    "provider": s.provider_type,
                    "model": s.model,
                    "rpm_limit": s.rpm_limit,
                    "rpd_limit": s.rpd_limit,
                    "requests_last_minute": len(s.request_timestamps),
                    "requests_today": s.requests_today,
                    "tokens_today": s.tokens_today,
                    "rate_limit_hits": s.rate_limit_hits,
                    "available": avail,
                    "status": reason if not avail else s.last_status,
                    "last_used_at": s.last_used_at,
                }
            )

        # Also include provider architectural blueprints if user hasn't entered keys yet
        default_blueprints = [
            {
                "provider": "gemini",
                "model": "gemini-2.0-flash",
                "free_tier_limits": "15 RPM / 1,500 RPD per key",
                "configured_keys": len(settings.gemini_api_keys),
                "strategy": "Primary high-context micro-batcher (up to 20 docs/call)",
            },
            {
                "provider": "mistral",
                "model": "mistral-small-latest",
                "free_tier_limits": "1 RPS (~30 RPM) / 500k TPM on La Plateforme",
                "configured_keys": len(settings.mistral_api_keys),
                "strategy": "Secondary structured JSON extractor & synthesis engine",
            },
            {
                "provider": "openrouter",
                "model": "llama-3.3-70b:free / gemma-3-27b:free / qwen-2.5-72b:free",
                "free_tier_limits": "20 RPM / 200-1,000 RPD across 4 :free model endpoints",
                "configured_keys": len(settings.openrouter_api_keys),
                "strategy": "Multi-model rotation when primary providers hit RPM caps",
            },
            {
                "provider": "grok",
                "model": "grok-2-latest / grok-3-mini",
                "free_tier_limits": "20 RPM / xAI tier quota",
                "configured_keys": len(settings.grok_api_keys),
                "strategy": "Social/Reddit slang & Hinglish nuance comprehension",
            },
            {
                "provider": "local_behavioral_engine",
                "model": "Deterministic Indian SIP Behavioral Lexicon + Heuristic Extractor",
                "free_tier_limits": "Unlimited (0 Latency, 0 Cost, Never 429s)",
                "configured_keys": 1,
                "strategy": "Always-on Stage 1 Triage (filters 75% noise) + Zero-key Fallback Extractor",
            },
        ]

        total_daily_capacity = sum(s.rpd_limit for s in self.slots)
        effective_docs_capacity = total_daily_capacity * settings.micro_batch_size

        return {
            "active_provider_slots": len(self.slots),
            "micro_batch_size": settings.micro_batch_size,
            "total_daily_requests_capacity": total_daily_capacity,
            "effective_daily_documents_capacity": effective_docs_capacity,
            "slots": configured_slots,
            "provider_blueprints": default_blueprints,
        }

    def complete_json(self, system_prompt: str, user_prompt: str) -> Tuple[Optional[str], str, str]:
        """
        Attempts to execute a JSON completion across all available provider slots.
        If a slot hits HTTP 429, it records the Retry-After cooldown and immediately fails over
        to the next healthy provider slot.
        Returns (raw_json_response_or_None, provider_used, model_used).
        """
        for slot in self.slots:
            avail, _ = slot.is_available()
            if not avail:
                continue

            try:
                raw_text = self._call_slot(slot, system_prompt, user_prompt)
                est_tokens = (len(system_prompt) + len(user_prompt) + len(raw_text)) // 4
                slot.record_success(est_tokens)
                return raw_text, slot.provider_type, slot.model
            except httpx.HTTPStatusError as http_err:
                if http_err.response.status_code == 429:
                    retry_hdr = http_err.response.headers.get("Retry-After", "65")
                    retry_sec = int(retry_hdr) if retry_hdr.isdigit() else 65
                    slot.record_rate_limit(retry_sec)
                    continue
                slot.last_status = f"HTTP_{http_err.response.status_code}"
                continue
            except Exception as exc:
                slot.last_status = f"ERROR: {str(exc)[:60]}"
                continue

        return None, "local_behavioral_engine", "deterministic-indian-sip-extractor"

    def _call_slot(self, slot: ProviderSlot, system_prompt: str, user_prompt: str) -> str:
        with httpx.Client(timeout=40.0) as client:
            if slot.provider_type == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{slot.model}:generateContent"
                resp = client.post(
                    url,
                    params={"key": slot.api_key},
                    json={
                        "systemInstruction": {"parts": [{"text": system_prompt}]},
                        "contents": [{"parts": [{"text": user_prompt}]}],
                        "generationConfig": {
                            "temperature": 0.15,
                            "responseMimeType": "application/json",
                        },
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]

            elif slot.provider_type == "mistral":
                resp = client.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {slot.api_key}"},
                    json={
                        "model": slot.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.15,
                        "response_format": {"type": "json_object"},
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]

            elif slot.provider_type == "openrouter":
                resp = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {slot.api_key}",
                        "HTTP-Referer": "https://groww-discovery-engine.local",
                        "X-Title": "Groww Behavioral Discovery Engine",
                    },
                    json={
                        "model": slot.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.15,
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]

            elif slot.provider_type == "grok":
                resp = client.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {slot.api_key}"},
                    json={
                        "model": slot.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.15,
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]

            elif slot.provider_type == "groq":
                payload: Dict[str, Any] = {
                    "model": slot.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.15,
                }
                if "gpt-oss" in slot.model:
                    payload["response_format"] = {"type": "json_object"}
                resp = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {slot.api_key}"},
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]

            raise ValueError(f"Unsupported provider_type: {slot.provider_type}")


llm_router = MultiProviderLLMRouter()
