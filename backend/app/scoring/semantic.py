"""
Semantic relevance scoring using sentence-transformers.

Uses the lightweight all-MiniLM-L6-v2 model (80MB, CPU-friendly) to compute
cosine similarity between a location's name+description and a set of
"ideal metal detecting hotspot" reference phrases.

The resulting score (0–1) is used as a multiplier in the main scoring engine
to boost locations that semantically match high-value detecting scenarios and
downweight locations that are semantically distant (e.g. modern facilities,
administrative entries).

The model is loaded lazily on first use and cached for the process lifetime.
On systems without the sentence-transformers package installed, this module
degrades gracefully — returning a neutral score of 1.0 so the rest of the
engine is unaffected.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Optional

from app.scoring.semantic_cache import _cache, get_cached, save_cache, set_cached, text_hash

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reference phrases — what an ideal metal detecting hotspot looks like
# ---------------------------------------------------------------------------

HOTSPOT_REFERENCE_PHRASES: List[str] = [
    "Civil War battle encampment with heavy troop movement and supply depots",
    "19th century frontier trading post at a river crossing on a wagon trail",
    "stagecoach relay station on the overland mail route",
    "abandoned gold rush mining town with saloons and commerce",
    "Spanish colonial mission with church and settlement",
    "Revolutionary War battlefield encampment",
    "Pony Express station on the western frontier",
    "historic ferry crossing on a major river where travelers paid tolls",
    "frontier fort with soldier barracks and supply wagons",
    "19th century ghost town with abandoned homesteads and general stores",
    "Native American trading post where goods and coins exchanged hands",
    "historic tavern and inn on a well-traveled road",
    "Civil War camp with soldiers dropping coins and personal items",
    "old cemetery near a historic town center",
    "historic river ford crossing where wagons and travelers crossed",
]

# ---------------------------------------------------------------------------
# Low-value anti-phrases — what we want to downweight
# ---------------------------------------------------------------------------

LOW_VALUE_PHRASES: List[str] = [
    "modern national park visitor center with interpretive displays",
    "contemporary recreational area with parking and facilities",
    "administrative government building",
    "modern highway rest stop",
    "active military restricted area",
]


@lru_cache(maxsize=1)
def _load_model():
    """
    Load and cache the sentence-transformers model.

    Returns the SentenceTransformer model or None if not available.
    """
    try:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
        model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Semantic scoring model loaded successfully.")
        return model
    except ImportError:
        logger.warning(
            "sentence-transformers not installed. "
            "Semantic scoring disabled — install with: pip install sentence-transformers"
        )
        return None
    except Exception as exc:
        logger.warning("Failed to load semantic model: %s. Semantic scoring disabled.", exc)
        return None


@lru_cache(maxsize=1)
def _get_reference_embeddings():
    """
    Pre-compute and cache embeddings for all reference phrases.

    Returns (hotspot_embeddings, low_value_embeddings) or (None, None).
    """
    model = _load_model()
    if model is None:
        return None, None

    try:
        hotspot_embs = model.encode(HOTSPOT_REFERENCE_PHRASES, convert_to_numpy=True, show_progress_bar=False)
        low_value_embs = model.encode(LOW_VALUE_PHRASES, convert_to_numpy=True, show_progress_bar=False)
        return hotspot_embs, low_value_embs
    except Exception as exc:
        logger.warning("Failed to compute reference embeddings: %s", exc)
        return None, None


def _cosine_sim(a, b) -> float:
    """Return cosine similarity between two numpy arrays."""
    import numpy as np
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def compute_semantic_score(name: str, description: str = "", location_type: str = "") -> float:
    """
    Compute a semantic relevance score for a location.

    Compares the location's text against ideal detecting hotspot phrases
    and low-value phrases using cosine similarity. Returns a multiplier
    in [0.5, 1.5] where:
    - 1.5 = highly semantically similar to known hotspot descriptions
    - 1.0 = neutral (model unavailable or ambiguous)
    - 0.5 = semantically similar to low-value/blocked-type locations

    This score is applied as a multiplier to the base type weight in the
    scoring engine — it does NOT replace the weight, it adjusts it.

    Args:
        name:          Location name.
        description:   Location description text.
        location_type: Location type string (e.g. "battle", "town").

    Returns:
        Float multiplier in [0.5, 1.5].
    """
    try:
        from app.config import settings
        if not settings.SEMANTIC_SCORING_ENABLED:
            return 1.0
    except Exception:
        pass

    model = _load_model()
    if model is None:
        return 1.0  # neutral — model not available

    hotspot_embs, low_value_embs = _get_reference_embeddings()
    if hotspot_embs is None:
        return 1.0

    try:
        import numpy as np

        # Combine name + description + type into query text
        query_text = f"{name}. {description} Type: {location_type}".strip()
        query_emb = model.encode([query_text], convert_to_numpy=True, show_progress_bar=False)[0]

        # Max similarity to any hotspot phrase
        hotspot_sim = max(_cosine_sim(query_emb, ref) for ref in hotspot_embs)

        # Max similarity to any low-value phrase
        low_value_sim = max(_cosine_sim(query_emb, ref) for ref in low_value_embs)

        # Net relevance: how much more "hotspot-like" than "low-value-like"
        net = hotspot_sim - low_value_sim

        # Map net [-1, 1] to multiplier [0.5, 1.5]
        # net > 0.2  → multiplier > 1.0 (boost)
        # net < -0.2 → multiplier < 1.0 (penalty)
        multiplier = 1.0 + (net * 0.5)
        return round(max(0.5, min(1.5, multiplier)), 4)

    except Exception as exc:
        logger.debug("Semantic scoring error: %s", exc)
        return 1.0


def batch_compute_semantic_scores(
    records: List[dict],
    location_ids: Optional[List[str]] = None,
) -> List[float]:
    """
    Compute semantic scores for a batch of records efficiently.

    Batching is much faster than individual calls since the model
    can process multiple texts in one forward pass.

    If ``location_ids`` is provided (a parallel list of UUID strings), the
    disk cache is consulted before encoding.  Cache hits are returned
    immediately; only misses are sent to the model.  Results for misses are
    then written back to the cache.  When ``location_ids`` is ``None``,
    caching is skipped (backward compatible).

    Args:
        records:      List of dicts with keys: name, description, type
        location_ids: Optional parallel list of UUID strings for caching.

    Returns:
        List of float multipliers, same length as records, in [0.5, 1.5].
    """
    try:
        from app.config import settings
        if not settings.SEMANTIC_SCORING_ENABLED:
            return [1.0] * len(records)
    except Exception:
        pass

    model = _load_model()
    if model is None:
        return [1.0] * len(records)

    hotspot_embs, low_value_embs = _get_reference_embeddings()
    if hotspot_embs is None:
        return [1.0] * len(records)

    # --- Cache-aware path ------------------------------------------------
    use_cache = location_ids is not None
    if use_cache and len(location_ids) != len(records):  # type: ignore[arg-type]
        logger.warning(
            "batch_compute_semantic_scores: location_ids length (%d) does not match "
            "records length (%d) — caching disabled for this call.",
            len(location_ids),  # type: ignore[arg-type]
            len(records),
        )
        use_cache = False

    # Pre-fill results with neutral score; populate from cache where possible
    results: List[float] = [1.0] * len(records)
    miss_indices: List[int] = []

    if use_cache:
        for i, (rec, lid) in enumerate(zip(records, location_ids)):  # type: ignore[zip-arg]
            cached = get_cached(
                lid,
                rec.get("name", ""),
                rec.get("description", ""),
                rec.get("type", ""),
            )
            if cached is not None:
                results[i] = cached
            else:
                miss_indices.append(i)
    else:
        miss_indices = list(range(len(records)))

    if not miss_indices:
        return results

    # --- Encode only the cache-miss records ------------------------------
    try:
        miss_records = [records[i] for i in miss_indices]
        texts = [
            f"{r.get('name', '')}. {r.get('description', '')} Type: {r.get('type', '')}".strip()
            for r in miss_records
        ]

        query_embs = model.encode(texts, convert_to_numpy=True, batch_size=64, show_progress_bar=False)

        for j, (qe, orig_i) in enumerate(zip(query_embs, miss_indices)):
            hotspot_sim = max(_cosine_sim(qe, ref) for ref in hotspot_embs)
            low_value_sim = max(_cosine_sim(qe, ref) for ref in low_value_embs)
            net = hotspot_sim - low_value_sim
            multiplier = round(max(0.5, min(1.5, 1.0 + net * 0.5)), 4)
            results[orig_i] = multiplier

            # Accumulate cache updates; flush to disk once after the loop
            if use_cache:
                rec = records[orig_i]
                _cache[str(location_ids[orig_i])] = {  # type: ignore[index]
                    "multiplier": multiplier,
                    "hash": text_hash(
                        rec.get("name", ""),
                        rec.get("description", ""),
                        rec.get("type", ""),
                    ),
                }

        # Single disk write for the entire batch
        if use_cache and miss_indices:
            save_cache(_cache)

        return results

    except Exception as exc:
        logger.warning("Batch semantic scoring failed: %s", exc)
        return results
