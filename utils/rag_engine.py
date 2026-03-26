"""
RAG Engine — Retrieval-Augmented Generation for VisionGuard AI Assistant

Embeds detection_history logs from MongoDB using sentence-transformers and
stores them in an in-memory FAISS index. On each voice query, retrieves the
top-k most semantically relevant log entries to feed as context to the LLM.
"""

from __future__ import annotations

import numpy as np
from datetime import datetime
from typing import List, Optional, Dict, Any


class RAGEngine:
    """Builds and queries a FAISS vector index over detection history logs."""

    def __init__(self, mongodb_manager: Any, config: Dict[str, Any]) -> None:
        self.mongodb_manager = mongodb_manager
        self.embedding_model_name: str = config.get("embedding_model", "all-MiniLM-L6-v2")
        self.top_k: int = int(config.get("rag_top_k", 5))
        self.max_logs: int = int(config.get("rag_max_logs", 200))
        self.refresh_minutes: int = int(config.get("index_refresh_minutes", 5))

        self._model = None          # lazy-loaded SentenceTransformer
        self._index = None          # faiss.IndexFlatIP
        self._log_texts: List[str] = []
        self._last_built: Optional[datetime] = None

        print(f"🔍 RAGEngine initialised (model={self.embedding_model_name}, top_k={self.top_k})")

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _load_model(self):
        """Lazy-load SentenceTransformer (downloads ~90 MB on first call)."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                print(f"📥 Loading embedding model '{self.embedding_model_name}' …")
                self._model = SentenceTransformer(self.embedding_model_name)
                print("✅ Embedding model ready")
            except ImportError:
                raise RuntimeError(
                    "sentence-transformers is not installed. "
                    "Run: pip install sentence-transformers"
                )

    def _doc_to_text(self, doc: Dict[str, Any]) -> str:
        """Convert a detection_history MongoDB document to a plain sentence."""
        parts: List[str] = []

        ts = doc.get("timestamp")
        if ts:
            try:
                if isinstance(ts, datetime):
                    parts.append(f"[{ts.strftime('%Y-%m-%d %H:%M')}]")
                else:
                    parts.append(f"[{str(ts)[:16]}]")
            except Exception:
                pass

        cam = doc.get("camera_location") or ""
        if cam:
            parts.append(f"Camera: {cam}.")

        num_unknown = doc.get("unknown_faces", 0) or 0
        identities: List[str] = doc.get("detected_identities") or []
        if identities:
            parts.append(f"Identified: {', '.join(str(i) for i in identities)}.")
        if num_unknown:
            parts.append(f"{num_unknown} unknown face(s) detected.")

        if doc.get("deepfake_detected"):
            conf = doc.get("deepfake_confidence")
            if conf is not None:
                parts.append(f"Deepfake detected (confidence {float(conf)*100:.0f}%).")
            else:
                parts.append("Deepfake detected.")

        suspicious: List[str] = doc.get("suspicious_objects") or []
        if suspicious:
            parts.append(f"Suspicious objects: {', '.join(str(s) for s in suspicious[:5])}.")

        risk = str(doc.get("risk_level") or "LOW").upper()
        score = doc.get("risk_score")
        if score is not None:
            parts.append(f"Risk: {risk} ({float(score)*100:.0f}%).")
        else:
            parts.append(f"Risk: {risk}.")

        return " ".join(parts) if parts else "Detection log entry."

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def build_index(self, user_id: str) -> None:
        """Pull recent logs from MongoDB, encode them, and store in FAISS."""
        try:
            import faiss
        except ImportError:
            raise RuntimeError("faiss-cpu is not installed. Run: pip install faiss-cpu")

        self._load_model()

        docs: List[Dict] = []
        try:
            docs = self.mongodb_manager.get_detection_history(
                user_id, limit=self.max_logs
            )
        except Exception as e:
            print(f"[RAG] Could not fetch detection history: {e}")

        if not docs:
            # Build empty index so retrieve() doesn't crash
            dim = 384  # all-MiniLM-L6-v2 output dimension
            self._index = faiss.IndexFlatIP(dim)
            self._log_texts = []
            self._last_built = datetime.now()
            print("[RAG] No detection logs found — empty index built")
            return

        texts = [self._doc_to_text(d) for d in docs]
        embeddings: np.ndarray = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        ).astype("float32")

        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        self._index = index
        self._log_texts = texts
        self._last_built = datetime.now()
        print(f"[RAG] Index built: {len(texts)} logs, dim={dim}")

    def retrieve(self, query: str, k: Optional[int] = None) -> List[str]:
        """Return top-k most relevant log strings for the given query."""
        if self._index is None or not self._log_texts:
            return []

        self._load_model()
        k = k or self.top_k

        vec: np.ndarray = self._model.encode(
            [query], normalize_embeddings=True, show_progress_bar=False
        ).astype("float32")

        n_results = min(k, len(self._log_texts))
        _, indices = self._index.search(vec, n_results)

        results: List[str] = []
        for idx in indices[0]:
            if 0 <= idx < len(self._log_texts):
                results.append(self._log_texts[idx])
        return results

    def add_log(self, doc: Dict[str, Any]) -> None:
        """Add a single new detection log to the in-memory index (live update)."""
        if self._index is None:
            return  # engine not yet built; caller (api/main.py) only calls this when engine exists
        try:
            self._load_model()
            import faiss  # noqa: F401
            text = self._doc_to_text(doc)
            vec = self._model.encode(
                [text], normalize_embeddings=True, show_progress_bar=False
            ).astype("float32")
            self._index.add(vec)
            self._log_texts.append(text)
        except Exception as e:
            print(f"[RAG] add_log failed: {e}")

    def is_stale(self) -> bool:
        """Return True if the index needs to be rebuilt (time-based)."""
        if self._last_built is None:
            return True
        elapsed = (datetime.now() - self._last_built).total_seconds()
        return elapsed > self.refresh_minutes * 60
