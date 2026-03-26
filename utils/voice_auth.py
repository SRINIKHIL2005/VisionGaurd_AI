"""Voice authentication utilities using Resemblyzer speaker embeddings."""
import base64
import io
import pickle
from typing import Optional

import numpy as np

# Lazy singleton — loaded once, reused across all requests
_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        try:
            from resemblyzer import VoiceEncoder
            _encoder = VoiceEncoder()
            print("[VoiceAuth] VoiceEncoder loaded ✅")
        except Exception as e:
            print(f"[VoiceAuth] Failed to load VoiceEncoder: {e}")
            _encoder = None
    return _encoder


def get_embedding(audio_bytes: bytes) -> Optional[np.ndarray]:
    """
    Generate a 256-dim speaker embedding from raw audio bytes (WAV or WebM).
    Returns None if resemblyzer is unavailable or audio is too short.
    """
    encoder = _get_encoder()
    if encoder is None:
        return None
    try:
        import soundfile as sf
        wav, sr = sf.read(io.BytesIO(audio_bytes))
        # Stereo → mono
        if wav.ndim > 1:
            wav = wav.mean(axis=1)
        wav = wav.astype(np.float32)
        # Resample to 16kHz if needed
        if sr != 16000:
            try:
                from scipy.signal import resample
                wav = resample(wav, int(len(wav) * 16000 / sr)).astype(np.float32)
            except Exception:
                pass  # try as-is
        from resemblyzer import preprocess_wav
        wav = preprocess_wav(wav, source_sr=16000)
        if len(wav) < 16000 * 0.5:   # reject clips shorter than 0.5 s
            return None
        return encoder.embed_utterance(wav)
    except Exception as e:
        print(f"[VoiceAuth] get_embedding failed: {e}")
        return None


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two embedding vectors (range −1 … 1)."""
    try:
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)
        if a_norm == 0 or b_norm == 0:
            return 0.0
        return float(np.dot(a, b) / (a_norm * b_norm))
    except Exception:
        return 0.0


def embedding_to_b64(embedding: np.ndarray) -> str:
    """Serialize a numpy embedding to a base64 string for MongoDB storage."""
    return base64.b64encode(pickle.dumps(embedding)).decode('utf-8')


def b64_to_embedding(b64: str) -> np.ndarray:
    """Deserialize a base64 string back to a numpy embedding."""
    return pickle.loads(base64.b64decode(b64))
