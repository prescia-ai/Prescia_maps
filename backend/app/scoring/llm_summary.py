"""
LLM-powered site insight summaries via Groq.

Uses the OpenAI-compatible Groq API to generate a 2-3 sentence
natural-language assessment of a metal-detecting location based on
nearby historical features.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from app.config import settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Lazy client — only initialised when the first request arrives so that
# startup doesn't fail when GROQ_API_KEY is not configured.
_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            from openai import AsyncOpenAI  # noqa: PLC0415
            _client = AsyncOpenAI(
                api_key=settings.GROQ_API_KEY or "not-set",
                base_url="https://api.groq.com/openai/v1",
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to initialise Groq client: %s", exc)
            return None
    return _client


_SYSTEM_PROMPT = """\
You are a knowledgeable, honest assistant for relic hunters, metal detectorists,
and historical-site enthusiasts. Your job is to write a concise 2-3 sentence
site insight for a specific geographic location based on nearby historical features.

Rules:
- Mention the actual nearby items by name.
- Do NOT invent specific historical events or artifacts not supported by the listed data.
- Do NOT promise treasure or imply guaranteed finds.
- If there is nothing notable nearby, say so honestly in a helpful tone.
- Keep the tone enthusiastic but grounded. Write in plain prose, not bullet points.
"""


async def generate_location_summary(
    lat: float,
    lon: float,
    nearby_locations: list,
    nearby_features: list,
    *,
    timeout_seconds: float = 6.0,
) -> Optional[str]:
    """
    Return a 2-3 sentence prose assessment, or None if unavailable
    (no API key configured, rate-limited, network error, etc.).
    Caller is responsible for caching.
    """
    if not settings.GROQ_API_KEY:
        return None

    client = _get_client()
    if client is None:
        return None

    # Build a structured list of nearby items (cap at 8 nearest)
    item_lines = []
    for loc in nearby_locations[:8]:
        name = loc.get("name") or loc.get("type", "unknown")
        loc_type = loc.get("type", "site")
        year = loc.get("year")
        dist_km = loc.get("distance_km")
        year_str = f" ({year})" if year else ""
        dist_str = f" — {dist_km:.1f} km away" if dist_km is not None else ""
        item_lines.append(f"- {loc_type}: {name}{year_str}{dist_str}")

    for feat in nearby_features[:4]:
        name = feat.get("name") or feat.get("type", "feature")
        feat_type = feat.get("type", "feature")
        item_lines.append(f"- {feat_type}: {name}")

    if not item_lines:
        nearby_text = "No notable historical features found within the search radius."
    else:
        nearby_text = "\n".join(item_lines)

    user_prompt = (
        f"Location: {lat:.4f}, {lon:.4f}\n\n"
        f"Nearby historical features:\n{nearby_text}\n\n"
        "Write a 2-3 sentence site insight for a metal detectorist considering this location."
    )

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=180,
                temperature=0.4,
            ),
            timeout=timeout_seconds,
        )
        text = response.choices[0].message.content
        return text.strip() if text else None
    except asyncio.TimeoutError:
        logger.warning(
            "Groq API timed out generating summary for (%s, %s)", lat, lon
        )
    except Exception as exc:
        logger.warning(
            "Groq API error generating summary for (%s, %s): %s", lat, lon, exc
        )
    return None
