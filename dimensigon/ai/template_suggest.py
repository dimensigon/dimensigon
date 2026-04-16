"""
Template suggestion engine for the orch-library.

Provides a hybrid TF-IDF + fuzzy search over the catalog of 6,302+ templates
hosted in github.com/dimensigon/orch-library. Fetches the catalog lazily,
caches in memory, and ranks templates by relevance to the user's query.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
import time
from collections import Counter
from typing import Dict, List, Optional

import requests

_LOGGER = logging.getLogger('dm.ai.template_suggest')

# Default library source (override via DM_ORCH_LIBRARY_URL)
DEFAULT_CATALOG_URL = (
    "https://raw.githubusercontent.com/dimensigon/orch-library/main/catalog.json"
)
# Cache TTL for the fetched catalog
CATALOG_TTL = 60 * 60  # 1 hour

# Common English stopwords to strip from queries
_STOPWORDS = frozenset("""
a an the and or but if then else for to of in on at by with from as is are was
were be been being do does did have has had i you he she it we they me him her
us them my your his its our their this that these those how what when where why
which who whom whose run do please can could would should help me need want want
get set make create delete remove add update modify change check test new my
""".split())

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS]


class TemplateIndex:
    """In-memory TF-IDF index over the orch-library catalog."""

    def __init__(self):
        self._entries: List[Dict] = []
        self._docs: List[List[str]] = []          # tokenized searchable text per entry
        self._doc_freq: Counter = Counter()       # token -> number of docs containing it
        self._doc_vectors: List[Dict[str, float]] = []  # per-doc tf-idf vectors
        self._doc_norms: List[float] = []
        self._loaded_at: float = 0.0
        self._lock = threading.Lock()

    @property
    def size(self) -> int:
        return len(self._entries)

    def is_stale(self) -> bool:
        return time.time() - self._loaded_at > CATALOG_TTL

    def load_from_catalog(self, catalog: Dict):
        entries = catalog.get("entries", [])
        with self._lock:
            self._entries = entries
            self._docs = [self._build_doc(e) for e in entries]
            self._doc_freq = Counter()
            for tokens in self._docs:
                for t in set(tokens):
                    self._doc_freq[t] += 1
            n = max(len(self._docs), 1)
            self._doc_vectors = []
            self._doc_norms = []
            for tokens in self._docs:
                tf = Counter(tokens)
                vec = {}
                for token, count in tf.items():
                    df = self._doc_freq.get(token, 1)
                    idf = math.log((1 + n) / (1 + df)) + 1.0
                    vec[token] = (count / max(len(tokens), 1)) * idf
                norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
                self._doc_vectors.append(vec)
                self._doc_norms.append(norm)
            self._loaded_at = time.time()
        _LOGGER.info(f"Loaded {len(entries)} templates into index")

    @staticmethod
    def _build_doc(entry: Dict) -> List[str]:
        parts = [
            entry.get("name", ""),
            entry.get("description", ""),
            entry.get("category", ""),
            entry.get("action_type", "") or "",
            entry.get("user_prompt", "") or "",
            " ".join(entry.get("tags", []) or []),
        ]
        return _tokenize(" ".join(parts))

    def search(self, query: str, top_k: int = 10,
               entity_type: Optional[str] = None,
               action_type: Optional[str] = None,
               difficulty: Optional[str] = None) -> List[Dict]:
        """Return top-K matching entries ranked by relevance."""
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        # Build query TF-IDF vector
        n = max(len(self._docs), 1)
        q_tf = Counter(q_tokens)
        q_vec = {}
        for token, count in q_tf.items():
            df = self._doc_freq.get(token, 1)
            idf = math.log((1 + n) / (1 + df)) + 1.0
            q_vec[token] = (count / max(len(q_tokens), 1)) * idf
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        # Score each doc (cosine) + fuzzy bonus
        scored = []
        q_text_lower = query.lower()
        for idx, entry in enumerate(self._entries):
            if entity_type and entry.get("entity_type") != entity_type:
                continue
            if action_type and (entry.get("action_type") or "").upper() != action_type.upper():
                continue
            if difficulty and entry.get("difficulty") != difficulty:
                continue

            d_vec = self._doc_vectors[idx]
            # cosine via dot product of shared terms
            dot = sum(q_vec[t] * d_vec[t] for t in q_vec if t in d_vec)
            score = dot / (q_norm * self._doc_norms[idx]) if dot else 0.0

            # Exact-match boost in name or user_prompt
            if entry.get("name") and q_text_lower in entry["name"].lower():
                score += 0.3
            if entry.get("user_prompt") and q_text_lower in entry["user_prompt"].lower():
                score += 0.2

            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {**entry, "score": round(score, 4)}
            for score, entry in scored[:top_k]
        ]


# Singleton index shared across requests
_index = TemplateIndex()


def get_index() -> TemplateIndex:
    return _index


def refresh_index(force: bool = False, url: Optional[str] = None) -> Dict:
    """Fetch the catalog from the configured URL and rebuild the index."""
    if not force and _index.size > 0 and not _index.is_stale():
        return {"ok": True, "cached": True, "size": _index.size}

    source = url or os.environ.get("DM_ORCH_LIBRARY_URL", DEFAULT_CATALOG_URL)
    try:
        resp = requests.get(source, timeout=15)
        resp.raise_for_status()
        catalog = resp.json()
    except Exception as e:
        _LOGGER.warning(f"Failed to fetch catalog from {source}: {e}")
        return {"ok": False, "error": str(e), "size": _index.size}

    _index.load_from_catalog(catalog)
    return {"ok": True, "cached": False, "size": _index.size, "source": source}


def suggest(query: str, top_k: int = 10, **filters) -> Dict:
    """Suggest templates matching the user's query.

    Returns a dict with the top-K results and metadata.
    """
    if _index.is_stale() or _index.size == 0:
        refresh_index()

    if _index.size == 0:
        return {
            "query": query,
            "results": [],
            "size": 0,
            "error": "Template catalog unavailable. Set DM_ORCH_LIBRARY_URL or "
                     "check network connectivity to github.com/dimensigon/orch-library.",
        }

    results = _index.search(query, top_k=top_k, **filters)
    return {
        "query": query,
        "results": results,
        "size": _index.size,
        "source": os.environ.get("DM_ORCH_LIBRARY_URL", DEFAULT_CATALOG_URL),
    }


def fetch_template(path: str) -> Optional[Dict]:
    """Fetch the full template JSON from the library by its path."""
    base = os.environ.get(
        "DM_ORCH_LIBRARY_RAW_BASE",
        "https://raw.githubusercontent.com/dimensigon/orch-library/main/"
    )
    # Sanitize — no absolute or parent traversal
    if path.startswith("/") or ".." in path:
        return None
    try:
        resp = requests.get(base.rstrip("/") + "/" + path.lstrip("/"), timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        _LOGGER.warning(f"Failed to fetch template {path}: {e}")
        return None
