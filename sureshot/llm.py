"""LLM access for Sureshot — anything OpenAI-compatible, Groq by default (NIM as preset)."""

from __future__ import annotations

from collections.abc import Iterator

import streamlit as st
from openai import OpenAI

# Primary preset: Groq — in head-to-head testing it was ~4-6x faster than NIM and
# produced sharper core-issue classifications. NIM remains a one-click preset.
DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"

PROVIDERS: dict[str, dict[str, str]] = {
    "Groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "openai/gpt-oss-120b",
        "secret": "groq_api_key",
    },
    "NVIDIA NIM": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "openai/gpt-oss-20b",
        "secret": "nvidia_api_key",
    },
}

# Shown when the endpoint's live model list can't be fetched. Ordered by preference.
_GROQ_FALLBACK = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
_NIM_FALLBACK = [
    "openai/gpt-oss-20b",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "moonshotai/kimi-k2.6",
    "z-ai/glm-5.3",
    "mistralai/mistral-large-2-instruct",
]


def fallback_models(base_url: str) -> list[str]:
    """A sensible model list for when the live fetch fails."""
    return _GROQ_FALLBACK if "groq.com" in base_url else _NIM_FALLBACK


def make_client(base_url: str, api_key: str) -> OpenAI:
    """Create an OpenAI-compatible client (works with Groq, NIM, OpenAI, Ollama…)."""
    return OpenAI(base_url=base_url, api_key=api_key, timeout=300.0, max_retries=1)


@st.cache_data(ttl="5m", show_spinner=False)
def fetch_models(base_url: str, api_key: str) -> list[str]:
    """List model ids available on the endpoint (cached for 5 minutes)."""
    client = make_client(base_url, api_key)
    page = client.models.list()
    return sorted({m.id for m in page.data if getattr(m, "id", None)})


def stream_chat(
    client: OpenAI,
    *,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.4,
    max_tokens: int = 4096,
) -> Iterator[str]:
    """Yield content tokens from a streaming chat completion.

    Only message content is yielded — reasoning traces (e.g. DeepSeek R1
    ``reasoning_content``) are intentionally dropped.
    """
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content
