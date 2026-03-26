"""
FastAPI Backend for VisionGuard AI

Provides REST API endpoints for:
- Image upload and analysis
- Video upload and processing
- Real-time camera feed processing
- Face database management
- Health checks and status

Endpoints:
- POST /analyze/image - Analyze single image
- POST /analyze/video - Process video file
- POST /face/add - Add identity to database
- GET /face/list - List all identities
- DELETE /face/{name} - Remove identity
- GET /health - Health check
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import sys
import os
import asyncio
import tempfile
import threading
import concurrent.futures
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import io
import json
import base64
import yaml

try:
    import edge_tts  # Microsoft neural TTS (free, online)
except Exception:
    edge_tts = None

try:
    import pyttsx3  # pyright: ignore[reportMissingImports]  # offline TTS fallback
except Exception:
    pyttsx3 = None

VOICE_SIMILARITY_THRESHOLD = 0.30  # cosine similarity cutoff for same-speaker

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from utils.voice_auth import get_embedding, cosine_similarity, embedding_to_b64, b64_to_embedding
    _voice_auth_available = True
except Exception as _va_err:
    get_embedding = None  # type: ignore
    cosine_similarity = None  # type: ignore
    embedding_to_b64 = None  # type: ignore
    b64_to_embedding = None  # type: ignore
    _voice_auth_available = False
    print(f"[VoiceAuth] Import skipped (resemblyzer not installed): {_va_err}")

# RAG + Gemini assistant (imported AFTER sys.path is set so 'utils' resolves)
try:
    from utils.rag_engine import RAGEngine
    from utils.llm_client import GeminiClient
except Exception as _rag_import_err:
    RAGEngine = None  # type: ignore
    GeminiClient = None  # type: ignore
    print(f"[Assistant] RAG/LLM import failed: {_rag_import_err}")

from pipeline.vision_pipeline import VisionPipeline
from utils.telegram_notifier import get_notifier, initialize_notifier, shutdown_notifier
from utils.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_current_user_optional,
)

# ===== Initialize FastAPI App =====
app = FastAPI(
    title="VisionGuard AI API",
    description="Unified computer vision system for deepfake detection, face recognition, and object detection",
    version="1.0.0"
)

# ===== CORS Configuration =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://n6ftzfnm-3000.inc1.devtunnels.ms",  # dev tunnel
        "https://*.devtunnels.ms",
        ],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== Global Pipeline Instance =====
pipeline: Optional[VisionPipeline] = None

# ── Edge TTS (primary) ───────────────────────────────────────────────────────
EDGE_VOICES = {
    'male':   'en-US-ChristopherNeural',   # deep, unambiguously male
    'female': 'en-US-JennyNeural',          # clear American female
}

async def _synthesize_edge_tts(text: str, voice_pref: str = 'male') -> Optional[bytes]:
    """Synthesize speech using Microsoft Edge TTS. Returns MP3 bytes."""
    if edge_tts is None or not text:
        return None
    voice = EDGE_VOICES.get(voice_pref, EDGE_VOICES['male'])
    try:
        communicate = edge_tts.Communicate(text, voice)
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        data = b"".join(chunks)
        return data if data else None
    except Exception as e:
        print(f"[TTS] edge_tts failed: {e}")
        return None

# ── pyttsx3 (offline fallback) ────────────────────────────────────────────────
_tts_engine = None
_tts_lock = threading.Lock()
_tts_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="vg_tts")

# Live notification throttle (per user)
_last_live_telegram_enqueue_at: dict = {}

# Live CCTV can POST frames very fast; bound concurrent analysis so
# background tasks (Telegram sends) don't get starved.
_ANALYZE_CONCURRENCY = int(os.getenv("VG_ANALYZE_CONCURRENCY", "1"))
_analyze_semaphore = asyncio.Semaphore(max(1, _ANALYZE_CONCURRENCY))

# Module-level RAG + Gemini — one engine per user, created on first query
rag_engines: dict = {}   # user_id → RAGEngine
_assistant_cfg: dict = {}
gemini_client = None


# ===== Startup Event =====
@app.on_event("startup")
async def startup_event():
    """Initialize pipeline, RAG engine, and Gemini client on startup"""
    global pipeline, rag_engines, _assistant_cfg, gemini_client
    print("\n🚀 Starting VisionGuard AI API...")
    pipeline = VisionPipeline(config_path="config/settings.yaml")

    # ── RAG + Gemini assistant ─────────────────────────────────────────────
    try:
        assistant_cfg = pipeline.config.get('assistant', {})
        _assistant_cfg = assistant_cfg
        api_key = (assistant_cfg.get('gemini_api_key') or '').strip()
        if api_key and RAGEngine is not None and GeminiClient is not None:
            model_name = assistant_cfg.get('gemini_model', 'gemini-2.0-flash')
            gemini_client = GeminiClient(api_key, model_name)
            print("✅ RAG engine ready (per-user indexes built on first query)")
        else:
            if not api_key:
                print("⚠️  No Gemini API key in settings.yaml — assistant uses fallback responses")
    except Exception as _e:
        print(f"⚠️  Assistant init failed: {_e}")
    # ──────────────────────────────────────────────────────────────────────

    print("✅ API Ready!\n")

    # Telegram is initialized on-demand per user via /user/telegram-settings
    # (avoids multiple instances and ensures user-specific credentials)


def _get_rag_for_user(user_id: str) -> "RAGEngine":
    """Return (and lazily create/refresh) the per-user RAGEngine instance."""
    if user_id not in rag_engines:
        rag_engines[user_id] = RAGEngine(pipeline.mongodb_manager, _assistant_cfg)
    engine = rag_engines[user_id]
    if engine.is_stale():
        engine.build_index(user_id)
    return engine


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown Telegram bot on API shutdown"""
    print("\n🛑 Shutting down...")
    await shutdown_notifier()
    print("✅ Cleanup complete")


# ===== Pydantic Models =====
class AnalysisResponse(BaseModel):
    """Response model for image/video analysis"""
    deepfake: dict
    face_recognition: dict
    objects: List[dict]
    suspicious_objects: List[str]
    risk_assessment: dict
    summary: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    models_loaded: dict


# ===== Authentication Models =====
class RegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str
    full_name: str


class LoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Authentication token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    """User information response"""
    user_id: str
    email: str
    full_name: str
    created_at: str


class RefreshRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class TelegramSettingsRequest(BaseModel):
    """Telegram settings update request"""
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""
    cooldown_minutes: int = 3
    retention_days: int = 10


class TelegramMessageRequest(BaseModel):
    """Simple Telegram message request"""
    message: str
    
class AssistantSettingsRequest(BaseModel):
    """AI Assistant settings update request"""
    enabled: bool = False
    name: str = "Jarvis"  # kept for backward compatibility; ignored
    voice: str = "male"  # 'male' | 'female'
    web_control_enabled: bool = False
    voice_lock_enabled: bool = False   # require owner voice verification after wake word


class VoiceEnrollRequest(BaseModel):
    """Audio bytes (WAV or WebM) encoded as base64 for voice enrollment."""
    audio_base64: str


class VoiceVerifyRequest(BaseModel):
    """Audio bytes (WAV or WebM) encoded as base64 for speaker verification."""
    audio_base64: str


class AssistantNarrateRequest(BaseModel):
    """Request for generating a short narration from an analysis result."""
    analysis: dict
    user_query: Optional[str] = ""
    page_context: Optional[dict] = None  # { current_page, live_cctv_active, web_control_enabled }
    frame_base64: Optional[str] = None  # annotated JPEG frame as base64 (from live CCTV)


# ===== Helper Functions =====
def convert_numpy_types(obj):
    """Convert numpy types to Python native types for JSON serialization"""
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        # DON'T convert numpy arrays to list (should already be encoded as base64 strings)
        print(f"⚠️ WARNING: Found numpy array in response that should have been encoded!")
        return obj.tolist()
    elif isinstance(obj, str):
        # Strings (like base64) should pass through unchanged
        return obj
    else:
        return obj


def decode_image(file_bytes: bytes) -> np.ndarray:
    """Decode uploaded image file to numpy array"""
    nparr = np.frombuffer(file_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Invalid image file")
    return image


def encode_image(image: np.ndarray) -> str:
    """Encode numpy array to base64 string"""
    _, buffer = cv2.imencode('.jpg', image)
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    return img_base64


def _get_tts_engine():
    global _tts_engine
    if _tts_engine is None:
        if pyttsx3 is None:
            return None
        _tts_engine = pyttsx3.init()
    return _tts_engine


def _synthesize_speech_wav_bytes(text: str) -> Optional[bytes]:
    """Synthesize speech to WAV bytes (offline)."""
    return _synthesize_speech_wav_bytes_with_voice(text, "male")


def _select_voice_id(engine, preference: str) -> Optional[str]:
    """Pick a voice id from installed voices based on a coarse preference."""
    try:
        voices = engine.getProperty('voices') or []
    except Exception:
        voices = []

    if not voices:
        return None

    pref = (preference or 'male').strip().lower()
    if pref not in {'male', 'female'}:
        pref = 'male'

    def voice_text(v):
        try:
            return f"{getattr(v, 'name', '')} {getattr(v, 'id', '')}".lower()
        except Exception:
            return ""

    # Broad keyword lists — covers desktop, mobile, and Win11 online voices
    MALE_HINTS = [
        'david', 'mark', 'mark mobile', 'george', 'james', 'guy', 'ryan',
        'richard', 'christopher', 'eric', 'brian', 'andrew', 'liam',
        'microsoft guy', 'microsoft david', 'microsoft mark',
    ]
    FEMALE_HINTS = [
        'zira', 'hazel', 'susan', 'helen', 'catherine', 'eva',
        'jenny', 'aria', 'emma', 'ava', 'sonia', 'natasha', 'linda',
        'microsoft zira', 'microsoft hazel',
    ]

    preferred_hints = MALE_HINTS if pref == 'male' else FEMALE_HINTS
    opposite_hints  = FEMALE_HINTS if pref == 'male' else MALE_HINTS

    # Pass 1: find a voice that matches the preferred gender keywords
    for hint in preferred_hints:
        for v in voices:
            if hint in voice_text(v):
                vid = getattr(v, 'id', None)
                if vid:
                    print(f"[TTS] Selected {pref} voice: {getattr(v, 'name', vid)}")
                    return vid

    # Pass 2: find a voice that is NOT a known opposite-gender voice
    #          (better than silently using the wrong gender)
    opposite_ids = set()
    for hint in opposite_hints:
        for v in voices:
            if hint in voice_text(v):
                vid = getattr(v, 'id', None)
                if vid:
                    opposite_ids.add(vid)

    for v in voices:
        vid = getattr(v, 'id', None)
        if vid and vid not in opposite_ids:
            print(f"[TTS] No {pref} voice found; using: {getattr(v, 'name', vid)}")
            return vid

    # Pass 3: absolute fallback — at least something speaks
    first_id = getattr(voices[0], 'id', None)
    print(f"[TTS] Fallback: using first available voice: {getattr(voices[0], 'name', first_id)}")
    return first_id


def _synthesize_speech_wav_bytes_with_voice(text: str, preference: str) -> Optional[bytes]:
    if not text:
        return None
    if pyttsx3 is None:
        return None

    with _tts_lock:
        engine = _get_tts_engine()
        if engine is None:
            return None

        # IMPORTANT: Per project constraint, do not delete temp files via os.remove.
        # Use a deterministic temp path and overwrite it each time.
        tmp_path = os.path.join(tempfile.gettempdir(), f"visionguard_tts_{os.getpid()}.wav")
        try:
            try:
                voice_id = _select_voice_id(engine, preference)
                if voice_id:
                    engine.setProperty('voice', voice_id)
            except Exception:
                pass

            try:
                engine.stop()
            except Exception:
                pass

            engine.save_to_file(text, tmp_path)
            engine.runAndWait()

            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            # Intentionally do not delete tmp_path
            pass


# ===== API Endpoints =====

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "VisionGuard AI API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "register": "POST /auth/register",
            "login": "POST /auth/login",
            "analyze_image": "POST /analyze/image",
            "analyze_video": "POST /analyze/video",
            "add_face": "POST /face/add",
            "list_faces": "GET /face/list",
            "health": "GET /health"
        }
    }


# ===== Authentication Endpoints =====

@app.post("/auth/register", response_model=TokenResponse, tags=["Authentication"])
async def register(request: RegisterRequest):
    """
    Register a new user account.
    
    Args:
        request: Registration data (email, password, full_name)
        
    Returns:
        Access token, refresh token, and user info
    """
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # Check if user already exists
    existing_user = pipeline.mongodb_manager.get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    hashed_password = hash_password(request.password)
    
    # Create user
    user_id = pipeline.mongodb_manager.create_user(
        email=request.email,
        hashed_password=hashed_password,
        full_name=request.full_name
    )
    
    if not user_id:
        raise HTTPException(status_code=500, detail="Failed to create user")
    
    # Create tokens
    access_token = create_access_token(data={
        "sub": user_id,
        "email": request.email,
        "full_name": request.full_name
    })
    refresh_token = create_refresh_token(data={"sub": user_id})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "user_id": user_id,
            "email": request.email,
            "full_name": request.full_name
        }
    }


@app.post("/auth/login", response_model=TokenResponse, tags=["Authentication"])
async def login(request: LoginRequest):
    """
    Login with email and password.
    
    Args:
        request: Login credentials (email, password)
        
    Returns:
        Access token, refresh token, and user info
    """
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # Get user from database
    user = pipeline.mongodb_manager.get_user_by_email(request.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Verify password
    if not verify_password(request.password, user['password']):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Check if user is active
    if not user.get('is_active', True):
        raise HTTPException(status_code=401, detail="Account is disabled")
    
    user_id = str(user['_id'])
    
    # Create tokens
    access_token = create_access_token(data={
        "sub": user_id,
        "email": user['email'],
        "full_name": user['full_name']
    })
    refresh_token = create_refresh_token(data={"sub": user_id})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "user_id": user_id,
            "email": user['email'],
            "full_name": user['full_name']
        }
    }


@app.post("/auth/refresh", tags=["Authentication"])
async def refresh_token(request: RefreshRequest):
    """Refresh access token using refresh token."""
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")

    payload = decode_token(request.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = pipeline.mongodb_manager.get_user_by_id(user_id)
    if not user:
        # Distinguish: DB is down vs user genuinely missing
        if not pipeline.mongodb_manager.is_connected:
            raise HTTPException(status_code=503, detail="Database temporarily unavailable — try again shortly")
        raise HTTPException(status_code=404, detail="User not found")

    access_token = create_access_token(data={
        "sub": str(user['_id']),
        "email": user['email'],
        "full_name": user['full_name'],
    })
    new_refresh_token = create_refresh_token(data={"sub": str(user['_id'])})

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


# ===== User Settings (Telegram) =====

@app.get("/user/telegram-settings", tags=["User"])
async def get_telegram_settings(current_user: dict = Depends(get_current_user)):
    """Get current user's Telegram settings."""
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")

    user = pipeline.mongodb_manager.get_user_by_id(current_user['user_id'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    settings = user.get('telegram_settings') or {
        'enabled': False,
        'bot_token': None,
        'chat_id': None,
        'cooldown_minutes': 3,
        'retention_days': 10,
    }

    # Normalize to frontend expected shapes
    return {
        "settings": {
            "enabled": bool(settings.get('enabled', False)),
            "bot_token": settings.get('bot_token') or "",
            "chat_id": str(settings.get('chat_id') or ""),
            "cooldown_minutes": int(settings.get('cooldown_minutes', 3)),
            "retention_days": int(settings.get('retention_days', 10)),
        }
    }

# ===== User Settings (AI Assistant) =====

@app.get("/user/assistant-settings", tags=["User"])
async def get_assistant_settings(current_user: dict = Depends(get_current_user)):
    """Get current user's AI assistant settings."""
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")

    user = pipeline.mongodb_manager.get_user_by_id(current_user['user_id'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    settings = user.get('assistant_settings') or {
        'enabled': False,
        'name': 'Jarvis',
        'voice': 'male',
    }

    name = 'Jarvis'
    voice = (settings.get('voice') or 'male').strip().lower()
    if voice not in {'male', 'female'}:
        voice = 'male'

    voice_lock_enabled = bool(settings.get('voice_lock_enabled', False))
    enrolled = bool(user.get('voice_enrolled', False))

    return {
        "settings": {
            "enabled": bool(settings.get('enabled', False)),
            "name": name,
            "voice": voice,
            "web_control_enabled": bool(settings.get('web_control_enabled', False)),
            "voice_lock_enabled": voice_lock_enabled,
            "voice_enrolled": enrolled,
        }
    }


@app.put("/user/assistant-settings", tags=["User"])
async def update_assistant_settings(
    request: AssistantSettingsRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update current user's AI assistant settings."""
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")

    name = "Jarvis"

    voice = (request.voice or 'male').strip().lower()
    if voice not in {'male', 'female'}:
        raise HTTPException(status_code=400, detail="voice must be 'male' or 'female'")

    settings_doc = {
        'enabled': bool(request.enabled),
        'name': name,
        'voice': voice,
        'web_control_enabled': bool(request.web_control_enabled),
        'voice_lock_enabled': bool(request.voice_lock_enabled),
    }

    ok = pipeline.mongodb_manager.update_assistant_settings(current_user['user_id'], settings_doc)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update assistant settings")

    return {"message": "Assistant settings updated", "settings": settings_doc}


# ===== Voice Lock Endpoints =====

@app.post("/user/enroll-voice", tags=["User"])
async def enroll_voice(
    request: VoiceEnrollRequest,
    current_user: dict = Depends(get_current_user),
):
    """Enroll the owner's voice. Stores a speaker embedding in the user document."""
    if not _voice_auth_available or get_embedding is None:
        raise HTTPException(status_code=503, detail="Voice auth not available — install resemblyzer")
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        audio_bytes = base64.b64decode(request.audio_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 audio data")
    embedding = get_embedding(audio_bytes)
    if embedding is None:
        raise HTTPException(status_code=422, detail="Could not extract voice embedding — audio may be too short or unsupported")
    b64 = embedding_to_b64(embedding)
    ok = pipeline.mongodb_manager.store_voice_embedding(current_user['user_id'], b64)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to store voice embedding")
    return {"success": True, "message": "Voice enrolled successfully"}


@app.delete("/user/enroll-voice", tags=["User"])
async def delete_voice_enrollment(current_user: dict = Depends(get_current_user)):
    """Remove the owner's voice embedding and disable voice lock."""
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")
    pipeline.mongodb_manager.delete_voice_embedding(current_user['user_id'])
    # Also turn off voice_lock_enabled in assistant_settings
    user = pipeline.mongodb_manager.get_user_by_id(current_user['user_id'])
    if user:
        settings = dict(user.get('assistant_settings') or {})
        settings['voice_lock_enabled'] = False
        pipeline.mongodb_manager.update_assistant_settings(current_user['user_id'], settings)
    return {"success": True, "message": "Voice enrollment removed"}


@app.get("/user/voice-status", tags=["User"])
async def get_voice_status(current_user: dict = Depends(get_current_user)):
    """Return whether the user has a voice enrolled and whether voice lock is on."""
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")
    user = pipeline.mongodb_manager.get_user_by_id(current_user['user_id'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    enrolled = bool(user.get('voice_enrolled', False))
    settings = user.get('assistant_settings') or {}
    lock_enabled = bool(settings.get('voice_lock_enabled', False))
    return {"enrolled": enrolled, "lock_enabled": lock_enabled}


@app.post("/assistant/verify-voice", tags=["Assistant"])
async def verify_voice(
    request: VoiceVerifyRequest,
    current_user: dict = Depends(get_current_user),
):
    """Compare incoming audio against the owner's stored voice embedding."""
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")
    stored_b64 = pipeline.mongodb_manager.get_voice_embedding(current_user['user_id'])
    if not stored_b64:
        return {"authorized": True, "enrolled": False, "confidence": 1.0}
    if not _voice_auth_available or get_embedding is None:
        return {"authorized": True, "enrolled": True, "confidence": 1.0}
    try:
        audio_bytes = base64.b64decode(request.audio_base64)
    except Exception:
        return {"authorized": False, "enrolled": True, "confidence": 0.0}
    incoming = get_embedding(audio_bytes)
    if incoming is None:
        return {"authorized": False, "enrolled": True, "confidence": 0.0}
    stored = b64_to_embedding(stored_b64)
    sim = cosine_similarity(incoming, stored)
    authorized = sim >= VOICE_SIMILARITY_THRESHOLD
    print(f"[VoiceAuth] user={current_user['user_id']} similarity={sim:.3f} authorized={authorized}")
    return {"authorized": authorized, "enrolled": True, "confidence": round(sim, 3)}


@app.post("/assistant/narrate", tags=["Assistant"])
async def assistant_narrate(
    request: AssistantNarrateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate a short Jarvis-style narration from the current live analysis.

    Note: This is template-based (no LLM). It is designed so we can later
    swap in a local LLM using the same structured summary.
    """
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")

    mgr = pipeline.mongodb_manager
    user = mgr.get_user_by_id(current_user['user_id'])
    if not user:
        if not mgr.is_connected:
            # DB is temporarily unreachable — degrade gracefully with defaults
            assistant_settings = {'enabled': True, 'name': 'Jarvis', 'voice': 'male'}
        else:
            raise HTTPException(status_code=404, detail="User not found")
    else:
        assistant_settings = user.get('assistant_settings') or {'enabled': False, 'name': 'Jarvis'}
    if not assistant_settings.get('enabled', False):
        raise HTTPException(status_code=400, detail="AI Assistant is disabled in Settings")

    assistant_name = (assistant_settings.get('name') or 'Jarvis').strip() or 'Jarvis'
    assistant_voice = (assistant_settings.get('voice') or 'male').strip().lower()
    if assistant_voice not in {'male', 'female'}:
        assistant_voice = 'male'

    user_query = (request.user_query or "").strip()
    analysis   = request.analysis or {}
    frame_b64  = (request.frame_base64 or "").strip() or None

    # ── Web UI Action Detection ───────────────────────────────────────────────────
    page_ctx      = request.page_context or {}
    current_page  = page_ctx.get('current_page', '/')
    live_active   = bool(page_ctx.get('live_cctv_active', False))
    # Use DB value as source of truth (so stale frontend sessions still work)
    web_ctrl      = bool(assistant_settings.get('web_control_enabled', page_ctx.get('web_control_enabled', False)))

    _PAGE_NAMES = {
        '/': 'Dashboard', '/image': 'Image Analysis', '/video': 'Video Analysis',
        '/live': 'Live CCTV', '/database': 'Face Database', '/settings': 'Settings',
    }
    _PAGES = {
        'dashboard': '/', 'home': '/',
        'image analysis': '/image', 'image': '/image',
        'video analysis': '/video', 'video': '/video',
        'live cctv': '/live', 'live': '/live', 'cctv': '/live', 'camera': '/live',
        'face database': '/database', 'database': '/database', 'faces': '/database', 'face': '/database',
        'settings': '/settings', 'setting': '/settings',
    }
    _NAV_VERBS = ['go to', 'navigate to', 'open', 'show me', 'take me to', 'switch to', 'launch', 'visit']
    _LIVE_ON   = [
        'start live', 'turn on live', 'on the live', 'enable live', 'activate live',
        'begin live', 'start cctv', 'start monitoring', 'turn on cctv', 'start camera',
        'start the live', 'on live', 'open live cctv',
        # common spoken variants
        'on the cctv', 'on cctv', 'ok on the cctv', 'turn on the cctv', 'turn on the live',
        'open the live', 'start the cctv', 'open cctv', 'begin cctv', 'activate cctv',
        'enable cctv', 'on camera', 'start camera feed', 'start the camera',
    ]
    _LIVE_OFF  = [
        'stop live', 'turn off live', 'off the live', 'disable live',
        'stop monitoring', 'stop cctv', 'turn off cctv', 'stop camera',
        'off the cctv', 'off cctv', 'turn off the cctv', 'close cctv',
        'close live', 'stop the live', 'stop the cctv', 'disable cctv',
    ]

    jarvis_action = {"type": "none"}
    action_desc   = ""

    if web_ctrl and user_query:
        q = user_query.lower()
        has_nav_verb = any(kw in q for kw in _NAV_VERBS)

        # Live CCTV start/stop takes priority (most explicit intent)
        if any(p in q for p in _LIVE_ON):
            jarvis_action = {"type": "navigate_and_start_live"}
            action_desc   = "Navigating to Live CCTV and starting the monitoring feed."
        elif any(p in q for p in _LIVE_OFF):
            jarvis_action = {"type": "stop_live_cctv"}
            action_desc   = "Stopping the Live CCTV monitoring feed."
        elif has_nav_verb:
            # Try longest page keywords first to avoid 'image' matching in 'image analysis'
            for page_kw in sorted(_PAGES, key=len, reverse=True):
                if page_kw in q:
                    path = _PAGES[page_kw]
                    jarvis_action = {"type": "navigate", "path": path}
                    action_desc   = f"Navigating to {_PAGE_NAMES.get(path, path)}."
                    break
        else:
            # Bare page name with no verb (e.g. "live cctv", "settings")
            for page_kw in sorted(_PAGES, key=len, reverse=True):
                if page_kw == q.strip() or (page_kw in q and len(q.split()) <= 4):
                    path = _PAGES[page_kw]
                    jarvis_action = {"type": "navigate", "path": path}
                    action_desc   = f"Navigating to {_PAGE_NAMES.get(path, path)}."
                    break

    def _build_ui_context() -> str:
        lines = [
            "=== WEB INTERFACE STATE ===",
            f"Current page the user is viewing: {_PAGE_NAMES.get(current_page, current_page)}",
            f"Live CCTV monitoring: {'ACTIVE — camera feed is running and analysis data below is LIVE' if live_active else 'INACTIVE — camera feed is NOT running, NO real scene data available'}",
            "Pages available in the app: Dashboard, Image Analysis, Video Analysis, Live CCTV, Face Database, Settings.",
        ]
        if not live_active:
            lines.append(
                "IMPORTANT: Since Live CCTV is NOT active, the camera analysis data below is empty/stale. "
                "Do NOT describe any scene or say 'the area is clear' — you have no real visual data. "
                "If the user asks what you see, say the camera isn't on yet."
            )
        if web_ctrl:
            lines.append("Web Control Mode: ENABLED — you CAN navigate pages and toggle Live CCTV for the user.")
            if action_desc:
                lines.append(f"Action you are performing right now: {action_desc}")
            else:
                lines.append("No UI action needed for this query.")
        else:
            lines.append(
                "Web Control Mode: DISABLED — if the user asks to navigate pages or control the UI, "
                "tell them to go to Settings → AI Assistant and enable 'Web Control Mode' first."
            )
        return "\n".join(lines)

    # ── Build rich scene context (structured data for Gemini scene understanding) ───
    risk          = analysis.get('risk_assessment') or {}
    threats       = risk.get('threats') or {}
    risk_level    = str(risk.get('risk_level') or 'LOW').upper()
    overall_score = risk.get('overall_score')
    face          = analysis.get('face_recognition') or {}
    identity      = (face.get('identity') or '').strip()
    objects       = analysis.get('objects') or []
    suspicious    = analysis.get('suspicious_objects') or []
    threat_cat    = risk.get('threat_category') or 'NONE'
    deepfake      = analysis.get('deepfake_detection') or {}

    # Count and collect all detected object labels
    object_labels = []
    for obj in objects:
        lbl = (obj.get('label') or obj.get('class') or '').strip().lower()
        if lbl:
            object_labels.append(lbl)

    from collections import Counter
    label_counts = Counter(object_labels)
    num_people = label_counts.get('person', 0)

    # Separate persons and weapons with their bboxes for spatial association
    person_objs  = [o for o in objects if (o.get('label') or o.get('class') or '').lower() == 'person']
    weapon_labels_set = {'grenade', 'knife', 'pistol', 'rifle', 'gun', 'weapon'}
    weapon_objs  = [
        o for o in objects
        if (o.get('label') or o.get('class') or '').lower() in weapon_labels_set
        or o.get('is_weapon')
    ]

    def _bbox_center(bbox):
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    def _point_in_expanded_bbox(cx, cy, bbox, expand=0.35):
        """Check if point (cx,cy) falls within a person bbox expanded by `expand` fraction."""
        x1, y1, x2, y2 = bbox
        w, h  = max(1, x2 - x1), max(1, y2 - y1)
        ex1   = x1 - w * expand
        ey1   = y1 - h * expand
        ex2   = x2 + w * expand
        ey2   = y2 + h * expand
        return ex1 <= cx <= ex2 and ey1 <= cy <= ey2

    def _associate_weapons_to_persons():
        """Return list of (weapon_label, person_index_or_None) associations."""
        associations = []
        for w_obj in weapon_objs:
            w_lbl  = (w_obj.get('label') or w_obj.get('class') or 'weapon').strip()
            w_bbox = w_obj.get('bbox')
            matched_person = None
            if w_bbox and person_objs:
                cx, cy = _bbox_center(w_bbox)
                for p_idx, p_obj in enumerate(person_objs):
                    p_bbox = p_obj.get('bbox')
                    if p_bbox and _point_in_expanded_bbox(cx, cy, p_bbox):
                        matched_person = p_idx + 1   # 1-based
                        break
                if matched_person is None:
                    # Fall back: nearest person by center distance
                    def _dist(p_obj):
                        pb = p_obj.get('bbox')
                        if not pb:
                            return float('inf')
                        px, py = _bbox_center(pb)
                        return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
                    nearest = min(person_objs, key=_dist)
                    dist_px = _dist(nearest)
                    if dist_px < 250:   # within ~250 pixels consider nearby
                        matched_person = person_objs.index(nearest) + 1
            associations.append((w_lbl, matched_person))
        return associations

    weapon_associations = _associate_weapons_to_persons() if weapon_objs else []

    # Accident / distress indicators from detected labels
    ACCIDENT_LABELS = {
        'fire', 'smoke', 'flame', 'blood', 'ambulance', 'accident',
        'fall', 'crash', 'explosion', 'collapsed'
    }
    accident_indicators = [
        lbl for lbl in label_counts
        if any(a in lbl for a in ACCIDENT_LABELS)
    ]

    # Build a human-readable object inventory string
    def _object_inventory():
        if not label_counts:
            return "No objects detected in frame."
        exclude = weapon_labels_set | {'person'}
        parts = []
        for label, count in label_counts.most_common(15):
            if label in exclude:
                continue
            parts.append(f"{count}x {label}" if count > 1 else label)
        return ", ".join(parts) if parts else "No additional objects."

    def camera_summary():
        """Rich structured scene description passed to Gemini as observation data."""
        lines = []

        # --- People & identity ---
        if num_people == 0:
            lines.append("PEOPLE: None visible in frame.")
        elif num_people == 1:
            lines.append("PEOPLE: 1 person in frame.")
        else:
            lines.append(f"PEOPLE: {num_people} people in frame.")

        if identity and identity.lower() not in {'unknown', 'n/a', ''}:
            lines.append(f"IDENTIFIED FACE: {identity} (recognised in database).")
        elif threats.get('is_unknown_person'):
            lines.append("IDENTIFIED FACE: Unknown person — not in the authorised database.")

        if threats.get('has_mask'):
            lines.append("FACE COVERING: Individual is wearing a mask or face covering.")

        # --- Weapon detections with specifics ---
        if weapon_associations:
            for w_lbl, p_idx in weapon_associations:
                if p_idx is not None:
                    who = identity if (identity and identity.lower() not in {'unknown', 'n/a', ''}
                                       and p_idx == 1 and num_people == 1) else f"Person {p_idx}"
                    lines.append(f"WEAPON ALERT: {w_lbl} detected — {who} appears to be holding it.")
                else:
                    lines.append(f"WEAPON ALERT: {w_lbl} detected in the scene — no person directly associated.")
        elif threats.get('has_weapon'):
            raw = threats.get('weapons_detected') or suspicious
            lines.append("WEAPON ALERT: " + (", ".join(str(w) for w in raw[:5]) if raw else "Unknown weapon type") + " detected.")
        elif suspicious:
            lines.append("SUSPICIOUS ITEMS: " + ", ".join(str(s) for s in suspicious[:5]))

        # --- Accident / distress scene indicators ---
        if accident_indicators:
            lines.append("ACCIDENT/DISTRESS INDICATORS: " + ", ".join(accident_indicators) + " detected in frame.")

        # --- All other visible objects (activity inference) ---
        inv = _object_inventory()
        lines.append(f"OTHER OBJECTS IN SCENE: {inv}")

        # --- Deepfake ---
        if deepfake.get('is_deepfake'):
            conf = deepfake.get('confidence')
            pct  = f" ({float(conf)*100:.0f}% confidence)" if conf is not None else ""
            lines.append(f"DEEPFAKE ALERT{pct}: Synthetic or manipulated media detected.")

        # --- Risk (background, not the headline) ---
        try:
            score_pct = f", score {float(overall_score)*100:.0f}%" if overall_score is not None else ""
        except Exception:
            score_pct = ""
        lines.append(f"RISK LEVEL: {risk_level}{score_pct}")

        if threat_cat and str(threat_cat).upper() not in {'NONE', 'NORMAL', ''}:
            lines.append(f"THREAT CATEGORY: {threat_cat}")

        return "\n".join(lines)

    # ── RAG + Gemini response ─────────────────────────────────────────────────
    effective_query = user_query or "Give me the current status."

    # If camera is off and no real analysis data, don't pass a misleading scene summary to Gemini
    has_real_analysis = bool(analysis.get('objects') or analysis.get('face_recognition') or analysis.get('risk_assessment'))
    effective_camera_summary = camera_summary() if (live_active or has_real_analysis) else "CAMERA STATUS: Live CCTV is currently OFF — no feed is streaming. No scene data is available."

    if gemini_client is not None and RAGEngine is not None:
        try:
            user_rag = _get_rag_for_user(current_user['user_id'])
            context_logs = user_rag.retrieve(effective_query, k=user_rag.top_k)
            text = gemini_client.generate(
                assistant_name,
                effective_camera_summary,
                effective_query,
                context_logs,
                ui_context=_build_ui_context(),
                frame_base64=frame_b64,
            )
        except Exception as _llm_err:
            print(f"[Gemini RAG] failed: {_llm_err}")
            text = f"I'm monitoring the situation. {effective_camera_summary}"
    else:
        # Fallback — no API key or packages not installed
        text = f"I'm online and monitoring. {effective_camera_summary}"

    audio_base64 = None
    mime = None
    try:
        # Primary: edge-tts (Microsoft neural voices — always works when online)
        mp3_bytes = await _synthesize_edge_tts(text, assistant_voice)
        if mp3_bytes and len(mp3_bytes) > 0:
            audio_base64 = base64.b64encode(mp3_bytes).decode("utf-8")
            mime = "audio/mpeg"
        else:
            # Fallback: pyttsx3 offline
            loop = asyncio.get_running_loop()
            wav_bytes = await loop.run_in_executor(
                _tts_executor,
                _synthesize_speech_wav_bytes_with_voice,
                text,
                assistant_voice,
            )
            if wav_bytes and len(wav_bytes) > 0:
                audio_base64 = base64.b64encode(wav_bytes).decode("utf-8")
                mime = "audio/wav"
    except Exception as e:
        print(f"[TTS] synthesis failed: {e}")
        audio_base64 = None
        mime = None

    return {
        "assistant": {
            "name": assistant_name,
        },
        "jarvis": {
            "text": text,
            "audio_base64": audio_base64,
            "mime": mime,
            "action": jarvis_action,
        }
    }


@app.get("/assistant/voices", tags=["Assistant"])
async def assistant_list_voices(current_user: dict = Depends(get_current_user)):
    """List installed offline TTS voices (pyttsx3/SAPI)."""
    if pyttsx3 is None:
        return {"voices": [], "available": False}

    with _tts_lock:
        engine = _get_tts_engine()
        if engine is None:
            return {"voices": [], "available": False}

        try:
            voices = engine.getProperty('voices') or []
        except Exception:
            voices = []

    out = []
    for v in voices:
        try:
            out.append({
                "id": getattr(v, 'id', None),
                "name": getattr(v, 'name', None),
            })
        except Exception:
            continue

    return {"voices": out, "available": True}


@app.put("/user/telegram-settings", tags=["User"])
async def update_telegram_settings(
    request: TelegramSettingsRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update current user's Telegram settings and (de)initialize notifier."""
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")

    # Validate required fields if enabling
    if request.enabled:
        if not request.bot_token or not request.chat_id:
            raise HTTPException(status_code=400, detail="bot_token and chat_id are required when enabled")
        try:
            int(request.chat_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="chat_id must be numeric")

    settings_doc = {
        'enabled': bool(request.enabled),
        'bot_token': request.bot_token or None,
        'chat_id': request.chat_id or None,
        'cooldown_minutes': int(request.cooldown_minutes or 3),
        'retention_days': int(request.retention_days or 10),
    }

    ok = pipeline.mongodb_manager.update_telegram_settings(current_user['user_id'], settings_doc)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update settings")

    # Start or stop notifier
    if settings_doc['enabled']:
        await initialize_notifier(
            bot_token=settings_doc['bot_token'],
            owner_chat_id=int(settings_doc['chat_id']),
            config={
                'cooldown_minutes': settings_doc['cooldown_minutes'],
                'retention_days': settings_doc['retention_days'],
            },
            face_recognizer=pipeline.face_recognizer,
            user_id=current_user['user_id'],
        )
    else:
        await shutdown_notifier(user_id=current_user['user_id'])

    return {"success": True}


@app.post("/user/test-telegram", tags=["User"])
async def test_telegram(current_user: dict = Depends(get_current_user)):
    """Send a test Telegram message using saved credentials."""
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")

    user = pipeline.mongodb_manager.get_user_by_id(current_user['user_id'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    settings = user.get('telegram_settings') or {}
    if not settings.get('enabled'):
        raise HTTPException(status_code=400, detail="Telegram notifications are disabled")

    bot_token = settings.get('bot_token')
    chat_id = settings.get('chat_id')
    if not bot_token or not chat_id:
        raise HTTPException(status_code=400, detail="Missing bot_token or chat_id")

    notifier = get_notifier(user_id=current_user['user_id'])
    if notifier is None:
        notifier = await initialize_notifier(
            bot_token=bot_token,
            owner_chat_id=int(chat_id),
            config={
                'cooldown_minutes': int(settings.get('cooldown_minutes', 3)),
                'retention_days': int(settings.get('retention_days', 10)),
            },
            face_recognizer=pipeline.face_recognizer,
            user_id=current_user['user_id'],
        )

    try:
        await notifier.send_startup_message()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send test message: {str(e)}")

    return {"success": True, "message": "Test message sent! Check your Telegram app."}


@app.post("/user/send-telegram", tags=["User"])
async def send_telegram_message(
    request: TelegramMessageRequest,
    current_user: dict = Depends(get_current_user),
):
    """Send a normal Telegram text message using saved credentials (debug helper)."""
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")

    user = pipeline.mongodb_manager.get_user_by_id(current_user['user_id'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    settings = user.get('telegram_settings') or {}
    if not settings.get('enabled'):
        raise HTTPException(status_code=400, detail="Telegram notifications are disabled")

    bot_token = settings.get('bot_token')
    chat_id = settings.get('chat_id')
    if not bot_token or not chat_id:
        raise HTTPException(status_code=400, detail="Missing bot_token or chat_id")

    notifier = get_notifier(user_id=current_user['user_id'])
    if notifier is None:
        notifier = await initialize_notifier(
            bot_token=bot_token,
            owner_chat_id=int(chat_id),
            config={
                'cooldown_minutes': int(settings.get('cooldown_minutes', 3)),
                'retention_days': int(settings.get('retention_days', 10)),
            },
            face_recognizer=pipeline.face_recognizer,
            user_id=current_user['user_id'],
        )

    ok = await notifier.send_text_message(request.message)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to send Telegram message")

    return {"success": True}


@app.get("/auth/me", response_model=UserResponse, tags=["Authentication"])
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user information.
    
    Args:
        current_user: Current user from JWT token (injected by dependency)
        
    Returns:
        User information
    """
    if pipeline is None or not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # Get full user data from database
    user = pipeline.mongodb_manager.get_user_by_id(current_user['user_id'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user_id": str(user['_id']),
        "email": user['email'],
        "full_name": user['full_name'],
        "created_at": user['created_at'].isoformat()
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check API health and model status"""
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    return {
        "status": "healthy",
        "version": "1.0.0",
        "models_loaded": {
            "deepfake_detector": pipeline.deepfake_detector is not None,
            "face_recognizer": pipeline.face_recognizer is not None,
            "object_detector": pipeline.object_detector is not None
        }
    }


@app.get("/db/status", tags=["System"])
async def db_status():
    """Return current MongoDB connection status."""
    if pipeline is None or pipeline.mongodb_manager is None:
        return {"connected": False, "detail": "MongoDB manager not initialised"}
    mgr = pipeline.mongodb_manager
    alive = mgr.ping()
    return {
        "connected": alive,
        "detail": "Online" if alive else "Unreachable — will auto-retry every 30 s",
    }


@app.post("/db/reconnect", tags=["System"])
async def db_reconnect(current_user: dict = Depends(get_current_user)):
    """Force an immediate MongoDB reconnection attempt."""
    if pipeline is None or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="MongoDB manager not initialised")
    success = pipeline.mongodb_manager.reconnect()
    if success:
        return {"connected": True, "detail": "Reconnected successfully"}
    raise HTTPException(
        status_code=503,
        detail="Reconnection failed — Atlas may be unreachable. Check your network and Atlas IP whitelist."
    )


@app.get("/test-config", tags=["System"])
async def test_config():
    """Test endpoint to check API configuration"""
    return {
        "return_annotated_default": "True",
        "message": "API is configured to return annotated images by default",
        "timestamp": "2026-01-29"
    }


@app.post("/analyze/image", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_image(
    file: UploadFile = File(...),
    return_annotated: bool = Form(True),  # 🎯 DEFAULT TRUE - Always return visual analysis
    camera_id: Optional[str] = Form(None),
    skip_deepfake: bool = Form(False),  # Set True for live CCTV to skip slow deepfake model
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Analyze an uploaded image.
    
    Args:
        file: Image file (JPG, PNG)
        return_annotated: Whether to return annotated image with circles/squares (base64)
        
    Returns:
        Complete analysis results with risk assessment and visual annotations
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Read and decode image
        contents = await file.read()
        image = decode_image(contents)

        # Auth context (used for per-user face DB + Telegram)
        user_id = current_user.get('user_id') if current_user else None
        
        print(f"\n{'='*60}")
        print(f"🔍 IMAGE ANALYSIS REQUEST")
        print(f"{'='*60}")
        print(f"📥 Received image: {image.shape}")
        print(f"🎯 return_annotated parameter: {return_annotated} (type: {type(return_annotated)})")
        
        # Process image (CPU/GPU heavy) in a worker thread so the event loop stays responsive
        await _analyze_semaphore.acquire()
        try:
            result = await asyncio.to_thread(
                pipeline.process_image,
                image,
                return_annotated=return_annotated,
                user_id=user_id,
                camera_id=camera_id,
                skip_deepfake=skip_deepfake,
            )
        finally:
            _analyze_semaphore.release()

        # If authenticated, ensure Telegram notifier is initialized from MongoDB settings
        if user_id and hasattr(pipeline, 'mongodb_manager') and pipeline.mongodb_manager is not None:
            try:
                user = pipeline.mongodb_manager.get_user_by_id(user_id)
                tg = (user or {}).get('telegram_settings') or {}
                if tg.get('enabled') and tg.get('bot_token') and tg.get('chat_id'):
                    notifier = get_notifier(user_id=user_id)
                    if notifier is None:
                        await initialize_notifier(
                            bot_token=tg.get('bot_token'),
                            owner_chat_id=int(tg.get('chat_id')),
                            config={
                                'cooldown_minutes': int(tg.get('cooldown_minutes', 3)),
                                'retention_days': int(tg.get('retention_days', 10)),
                            },
                            face_recognizer=pipeline.face_recognizer,
                            user_id=user_id,
                        )
            except Exception:
                # Don't fail image analysis if Telegram setup fails
                pass
        
        # Handle Telegram notifications from live feed (async, throttled)
        should_notify = bool(getattr(pipeline, '_last_unknown_faces', None))
        if should_notify:
            key = user_id or 'default'
            now = datetime.utcnow()
            last = _last_live_telegram_enqueue_at.get(key)
            if last is None or (now - last).total_seconds() >= 20:
                _last_live_telegram_enqueue_at[key] = now

                notifier = get_notifier(user_id=user_id) if user_id else get_notifier()
                if notifier:
                    asyncio.create_task(
                        pipeline._notify_unknown_faces(
                            image,
                            pipeline._last_unknown_faces,
                            camera_location="Live CCTV",
                            user_id=user_id,
                            risk_assessment=result.get('risk_assessment'),
                            summary=result.get('summary'),
                            suspicious_objects=result.get('suspicious_objects'),
                        )
                    )
        
        print(f"\n📊 Pipeline returned {len(result)} keys: {list(result.keys())}")
        print(f"🔍 Has 'annotated_image' key: {'annotated_image' in result}")
        
        # Encode annotated image BEFORE converting numpy types
        if 'annotated_image' in result and result['annotated_image'] is not None:
            print(f"✅ annotated_image exists! Shape: {result['annotated_image'].shape}")
            result['annotated_image'] = await asyncio.to_thread(encode_image, result['annotated_image'])
            print(f"✅ Encoded to base64: {len(result['annotated_image'])} characters")
        else:
            print(f"❌ NO annotated_image in result!")
            print(f"   return_annotated was: {return_annotated}")
            print(f"   Result keys: {list(result.keys())}")
        
        # Convert numpy types to Python types for JSON serialization
        result = convert_numpy_types(result)

        # ── Log detection to MongoDB so RAG has history to retrieve ──────────
        if user_id and hasattr(pipeline, 'mongodb_manager') and pipeline.mongodb_manager and pipeline.mongodb_manager.is_connected:
            try:
                risk    = result.get('risk_assessment') or {}
                face    = result.get('face_recognition') or {}
                deepfk  = result.get('deepfake_detection') or {}
                identity = (face.get('identity') or '').strip()
                detected_identities = [identity] if identity and identity.lower() not in {'unknown', 'n/a', ''} else []
                unknown_faces = 1 if (face.get('faces_detected') and not detected_identities) else 0
                log_doc = {
                    'camera_location': camera_id or ('Live CCTV' if skip_deepfake else 'Image Upload'),
                    'detected_identities': detected_identities,
                    'unknown_faces': unknown_faces,
                    'deepfake_detected': bool(deepfk.get('is_fake') or deepfk.get('is_deepfake')),
                    'deepfake_confidence': float(deepfk.get('fake_probability') or deepfk.get('confidence') or 0.0),
                    'suspicious_objects': result.get('suspicious_objects') or [],
                    'risk_level': str(risk.get('risk_level') or 'LOW').lower(),
                    'risk_score': float(risk.get('overall_score') or 0.0),
                }
                doc_id = pipeline.mongodb_manager.log_detection(user_id, log_doc)
                # Live-update that user's RAG index so queries already see this frame
                if doc_id not in {'offline', 'error'} and user_id in rag_engines:
                    log_doc['timestamp'] = __import__('datetime').datetime.utcnow()
                    log_doc['user_id'] = user_id
                    rag_engines[user_id].add_log(log_doc)
            except Exception as _log_err:
                print(f"[Detection Log] failed: {_log_err}")

        print(f"📤 Sending response with {len(result)} keys")
        print(f"   Has annotated_image in final response: {'annotated_image' in result}")
        print(f"{'='*60}\n")
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/analyze/video", tags=["Analysis"])
async def analyze_video(
    file: UploadFile = File(...),
    frame_skip: int = Form(5),
    return_annotated_video: bool = Form(False),
    weapon_detection_only: bool = Form(False),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Analyze an uploaded video file with weapon detection.
    
    Args:
        file: Video file (MP4, AVI, MOV)
        frame_skip: Process every Nth frame (1=all frames, 5=every 5th frame)
        return_annotated_video: Return annotated video with detections
        weapon_detection_only: Focus only on weapon detection (faster)
        
    Returns:
        Video analysis results with weapon detections, timestamps, and summary
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    # Validate file type
    if not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")
    
    try:
        import tempfile
        from collections import defaultdict
        
        # Save uploaded video temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            temp_path = tmp.name
            tmp.write(await file.read())
        
        print(f"\n{'='*60}")
        print(f"🎥 VIDEO ANALYSIS REQUEST")
        print(f"{'='*60}")
        print(f"📥 File: {file.filename}")
        print(f"⚙️  Frame skip: {frame_skip}")
        print(f"🎯 Weapon detection focus: {weapon_detection_only}")
        
        # Setup output path for annotated video
        output_video_path = None
        if return_annotated_video:
            output_video_path = temp_path.replace(Path(temp_path).suffix, '_annotated.mp4')
        
        # Process video
        results = pipeline.process_video(
            temp_path, 
            output_path=output_video_path,
            frame_skip=frame_skip
        )
        
        # Analyze weapon detections across frames
        weapon_detections = defaultdict(list)
        frames_with_weapons = 0
        total_weapons = 0
        
        cap = cv2.VideoCapture(temp_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        cap.release()

        # Deepfake (video-level) summary: aggregate per-frame deepfake results on frames with a detected face.
        deepfake_summary = None
        try:
            threshold = float(getattr(getattr(pipeline, 'deepfake_detector', None), 'threshold', 0.5))
            face_frames = []
            for r in results:
                fr = (r or {}).get('face_recognition') or {}
                if fr.get('face_detected'):
                    face_frames.append(r)

            probs = []
            suspect_frames = []
            for r in face_frames:
                frame_num = r.get('frame_number', 0)
                ts = frame_num / fps if fps > 0 else 0
                df = (r or {}).get('deepfake') or {}
                prob = df.get('fake_probability')
                if prob is None:
                    continue
                prob_f = float(prob)
                probs.append(prob_f)
                if prob_f > threshold:
                    suspect_frames.append({
                        'frame': frame_num,
                        'timestamp': f"{ts:.2f}s",
                        'fake_probability': round(prob_f, 4)
                    })

            if probs:
                probs_sorted = sorted(probs)
                p95_idx = int(0.95 * (len(probs_sorted) - 1))
                p95 = probs_sorted[p95_idx]
                mean_prob = sum(probs_sorted) / len(probs_sorted)
                max_prob = probs_sorted[-1]
                suspect_ratio = (len(suspect_frames) / len(face_frames)) if face_frames else 0.0

                # Simple offline video decision rule: needs both a high percentile and a non-trivial fraction of suspect frames.
                is_fake_video = (p95 > threshold and suspect_ratio >= 0.30)
                deepfake_summary = {
                    'label': 'FAKE' if is_fake_video else 'REAL',
                    'threshold': round(threshold, 4),
                    'frames_with_face': len(face_frames),
                    'frames_suspect': len(suspect_frames),
                    'suspect_ratio': round(suspect_ratio, 4),
                    'fake_probability_mean': round(mean_prob, 4),
                    'fake_probability_p95': round(p95, 4),
                    'fake_probability_max': round(max_prob, 4),
                    'suspect_frames': suspect_frames[:50],
                }
            else:
                deepfake_summary = {
                    'label': 'UNKNOWN',
                    'threshold': round(threshold, 4),
                    'frames_with_face': len(face_frames),
                    'frames_suspect': 0,
                    'suspect_ratio': 0.0,
                    'message': 'No deepfake scores available (no faces detected or deepfake output missing).'
                }
        except Exception:
            deepfake_summary = {
                'label': 'UNKNOWN',
                'message': 'Deepfake video summary failed to compute.'
            }
        
        for result in results:
            frame_num = result.get('frame_number', 0)
            timestamp = frame_num / fps if fps > 0 else 0
            
            # Check for weapons in this frame
            frame_weapons = []
            for obj_label in result.get('suspicious_objects', []):
                if obj_label in ['Grenade', 'Knife', 'Pistol', 'Rifle', 'knife', 'gun', 'weapon']:
                    frame_weapons.append(obj_label)
                    weapon_detections[obj_label].append({
                        'frame': frame_num,
                        'timestamp': f"{timestamp:.2f}s"
                    })
                    total_weapons += 1
            
            if frame_weapons:
                frames_with_weapons += 1
                result['weapons_in_frame'] = frame_weapons
        
        # Generate summary
        weapon_summary = {
            'total_weapons_detected': total_weapons,
            'frames_with_weapons': frames_with_weapons,
            'weapon_types': {},
            'first_detection': None,
            'last_detection': None
        }
        
        for weapon_type, detections in weapon_detections.items():
            weapon_summary['weapon_types'][weapon_type] = len(detections)
            if weapon_summary['first_detection'] is None:
                weapon_summary['first_detection'] = detections[0]['timestamp']
            weapon_summary['last_detection'] = detections[-1]['timestamp']
        
        # Convert numpy types to Python types
        results = convert_numpy_types(results)
        
        # Encode annotated video if requested
        annotated_video_base64 = None
        if return_annotated_video and output_video_path and os.path.exists(output_video_path):
            with open(output_video_path, 'rb') as f:
                import base64
                annotated_video_base64 = base64.b64encode(f.read()).decode('utf-8')

        # Note: Per project constraint, we do not delete temp files here.
        # temp_path/output_video_path are left on disk.

        # ── Log each processed frame to MongoDB so RAG has video history ────
        user_id = (current_user or {}).get('user_id')
        if user_id and hasattr(pipeline, 'mongodb_manager') and pipeline.mongodb_manager and pipeline.mongodb_manager.is_connected:
            import datetime as _dt
            logged = 0
            for r in results:
                try:
                    frame_num = r.get('frame_number', 0)
                    ts_offset = frame_num / fps if fps > 0 else 0
                    risk    = r.get('risk_assessment') or {}
                    face    = r.get('face_recognition') or {}
                    deepfk  = r.get('deepfake') or r.get('deepfake_detection') or {}
                    identity = (face.get('identity') or '').strip()
                    detected_identities = [identity] if identity and identity.lower() not in {'unknown', 'n/a', 'no face', ''} else []
                    unknown_faces = 1 if (face.get('face_detected') and not detected_identities) else 0
                    log_doc = {
                        'camera_location': f'Video Upload ({file.filename}) @{ts_offset:.1f}s',
                        'detected_identities': detected_identities,
                        'unknown_faces': unknown_faces,
                        'deepfake_detected': bool(deepfk.get('is_fake') or deepfk.get('is_deepfake')),
                        'deepfake_confidence': float(deepfk.get('fake_probability') or deepfk.get('confidence') or 0.0),
                        'suspicious_objects': r.get('suspicious_objects') or [],
                        'risk_level': str(risk.get('risk_level') or 'LOW').lower(),
                        'risk_score': float(risk.get('overall_score') or 0.0),
                    }
                    doc_id = pipeline.mongodb_manager.log_detection(user_id, log_doc)
                    if doc_id not in {'offline', 'error'} and user_id in rag_engines:
                        log_doc['timestamp'] = _dt.datetime.utcnow()
                        log_doc['user_id'] = user_id
                        rag_engines[user_id].add_log(log_doc)
                    logged += 1
                except Exception as _log_err:
                    print(f"[Video Log] frame {r.get('frame_number')} failed: {_log_err}")
            print(f"[Video Log] Saved {logged}/{len(results)} frame detections to MongoDB")
        
        print(f"\n📊 Analysis Complete:")
        print(f"   Frames processed: {len(results)}")
        print(f"   Weapons detected: {total_weapons}")
        print(f"   Frames with weapons: {frames_with_weapons}")
        print(f"{'='*60}\n")
        
        # Calculate final video risk level
        final_risk_level = "LOW"
        
        # Check for weapons (highest priority) → HIGH
        if total_weapons > 0 or (deepfake_summary and deepfake_summary.get('label') == 'FAKE'):
            final_risk_level = "HIGH"
        else:
            # Check frame-level risk levels
            high_risk_count = sum(1 for r in results if r.get('risk_assessment', {}).get('risk_level') == 'HIGH')
            medium_risk_count = sum(1 for r in results if r.get('risk_assessment', {}).get('risk_level') == 'MEDIUM')
            
            if high_risk_count > 0:
                final_risk_level = "HIGH"
            elif medium_risk_count > 0:
                final_risk_level = "MEDIUM"
        
        print(f"   Final Risk Level: {final_risk_level}")
        print(f"   High Risk Frames: {sum(1 for r in results if r.get('risk_assessment', {}).get('risk_level') == 'HIGH')}")
        print(f"   Medium Risk Frames: {sum(1 for r in results if r.get('risk_assessment', {}).get('risk_level') == 'MEDIUM')}")
        
        response = {
            "num_frames_processed": len(results),
            "final_risk_level": final_risk_level,
            "weapon_summary": weapon_summary,
            "weapon_detections": dict(weapon_detections),
            "deepfake_summary": deepfake_summary,
            "results": results if not weapon_detection_only else [
                {
                    'frame_number': r['frame_number'],
                    'weapons_in_frame': r.get('weapons_in_frame', []),
                    'risk_assessment': r['risk_assessment']
                }
                for r in results
            ]
        }
        
        if annotated_video_base64:
            response['annotated_video'] = annotated_video_base64
        
        return response
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Video analysis failed: {str(e)}")


@app.post("/face/add", tags=["Face Database"])
async def add_face(
    name: str = Form(...),
    file: UploadFile = File(...),
    camera_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Add a new identity to the face recognition database.
    
    Args:
        name: Person's name/identifier
        file: Face image
        
    Returns:
        Success status
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Read and decode image
        contents = await file.read()
        image = decode_image(contents)
        
        # Add to database — pass current user's ID so face is stored under their account
        success = pipeline.face_recognizer.add_identity(image, name, user_id=current_user['user_id'])
        
        if success:
            return {
                "status": "success",
                "message": f"Identity '{name}' added successfully"
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to add identity (no face detected?)")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add identity: {str(e)}")


@app.get("/face/list", tags=["Face Database"])
async def list_faces(detailed: bool = True, current_user: dict = Depends(get_current_user)):
    """
    Get list of all identities in the database.
    
    Args:
        detailed: Return full metadata (photo, date, approver, location)
    
    Returns:
        List of identity names or detailed info with metadata
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    identities = pipeline.face_recognizer.list_identities(detailed=detailed, user_id=current_user['user_id'])
    
    # If detailed, encode photos as base64
    if detailed and isinstance(identities, list) and len(identities) > 0:
        for identity in identities:
            photo_path = identity.get('photo_path')
            if photo_path and os.path.exists(photo_path):
                try:
                    with open(photo_path, 'rb') as f:
                        image_bytes = f.read()
                    identity['photo_base64'] = base64.b64encode(image_bytes).decode('utf-8')
                except Exception as e:
                    print(f"⚠️ Failed to load photo for {identity['name']}: {e}")
                    identity['photo_base64'] = None
            else:
                identity['photo_base64'] = None
    
    return {
        "num_identities": len(identities),
        "identities": identities
    }


@app.delete("/face/{name}", tags=["Face Database"])
async def remove_face(name: str, current_user: dict = Depends(get_current_user)):
    """
    Remove an identity from the database.
    
    Args:
        name: Identity name to remove
        
    Returns:
        Success status
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    success = pipeline.face_recognizer.remove_identity(name, user_id=current_user['user_id'])
    
    if success:
        return {
            "status": "success",
            "message": f"Identity '{name}' removed"
        }
    else:
        raise HTTPException(status_code=404, detail=f"Identity '{name}' not found")


@app.get("/models/info", tags=["System"])
async def model_info():
    """Get information about loaded models"""
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    return {
        "deepfake_detector": {
            "available": pipeline.deepfake_detector is not None,
            "type": "Vision Transformer"
        },
        "face_recognizer": {
            "available": pipeline.face_recognizer is not None,
            "type": "InsightFace ArcFace",
            "num_identities": len(pipeline.face_recognizer.list_identities())
        },
        "object_detector": {
            "available": pipeline.object_detector is not None and pipeline.object_detector.model is not None,
            "type": "YOLOv8",
            "num_classes": len(pipeline.object_detector.get_class_names()) if pipeline.object_detector.model else 0
        }
    }


# ===== Telegram Bot Endpoints =====

@app.get("/faces/unknown", tags=["Unknown Faces"])
async def list_unknown_faces():
    """
    Get list of pending unknown face detections.
    
    Returns:
        List of unknown face detections awaiting approval
    """
    notifier = get_notifier()
    if notifier is None:
        raise HTTPException(status_code=503, detail="Telegram notifier not initialized")
    
    try:
        queue = notifier._load_queue()
        
        # Filter for notified/pending detections
        pending = [
            {
                "id": det["id"],
                "timestamp": det["timestamp"],
                "camera_location": det.get("camera_location", "Unknown"),
                "unknown_count": det.get("unknown_count", 1),
                "status": det["status"]
            }
            for det in queue
            if det["status"] == "notified"
        ]
        
        return {
            "total_pending": len(pending),
            "detections": pending
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load unknown faces: {str(e)}")


@app.post("/faces/unknown/{detection_id}/approve", tags=["Unknown Faces"])
async def approve_unknown_face(detection_id: str, name: str = Form(...)):
    """
    Approve an unknown face detection and add to known database.
    
    Args:
        detection_id: Detection ID from notification
        name: Name to assign to the face(s)
        
    Returns:
        Success status
    """
    notifier = get_notifier()
    if notifier is None:
        raise HTTPException(status_code=503, detail="Telegram notifier not initialized")
    
    try:
        success = await notifier._add_to_known_faces(detection_id, name)
        
        if success:
            return {
                "status": "success",
                "message": f"Face(s) approved and added as '{name}'"
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to approve face")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error approving face: {str(e)}")


@app.post("/faces/unknown/{detection_id}/reject", tags=["Unknown Faces"])
async def reject_unknown_face(detection_id: str):
    """
    Reject an unknown face detection.
    
    Args:
        detection_id: Detection ID from notification
        
    Returns:
        Success status
    """
    notifier = get_notifier()
    if notifier is None:
        raise HTTPException(status_code=503, detail="Telegram notifier not initialized")
    
    try:
        queue = notifier._load_queue()
        
        # Find and mark as rejected
        found = False
        for detection in queue:
            if detection["id"] == detection_id:
                detection["status"] = "rejected"
                found = True
                break
        
        if not found:
            raise HTTPException(status_code=404, detail="Detection not found")
        
        notifier._save_queue(queue)
        
        return {
            "status": "success",
            "message": "Face detection rejected"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rejecting face: {str(e)}")


@app.get("/telegram/status", tags=["System"])
async def telegram_status():
    """Check Telegram bot status"""
    notifier = get_notifier()
    
    if notifier is None:
        return {
            "enabled": False,
            "status": "not_initialized"
        }
    
    return {
        "enabled": True,
        "status": "running",
        "bot_token_set": bool(notifier.bot_token),
        "owner_chat_id_set": bool(notifier.owner_chat_id),
        "cooldown_minutes": notifier.cooldown_minutes,
        "retention_days": notifier.retention_days
    }


# ===== MongoDB History Endpoints =====

@app.get("/history/detections", tags=["History"])
async def get_detection_history(
    limit: int = 100,
    camera_location: Optional[str] = None
):
    """
    Get detection history from MongoDB.
    
    Args:
        limit: Maximum number of records to return
        camera_location: Filter by camera location (optional)
        
    Returns:
        List of detection events
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    if not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="MongoDB not enabled")
    
    try:
        history = pipeline.mongodb_manager.get_detection_history(
            limit=limit,
            camera_location=camera_location
        )
        return {
            "total": len(history),
            "history": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching history: {str(e)}")


@app.get("/history/telegram", tags=["History"])
async def get_telegram_history(limit: int = 100):
    """Get Telegram interaction history from MongoDB"""
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    if not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="MongoDB not enabled")
    
    try:
        history = pipeline.mongodb_manager.get_telegram_history(limit=limit)
        return {
            "total": len(history),
            "history": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching history: {str(e)}")


@app.get("/history/analyses", tags=["History"])
async def get_analysis_history(
    limit: int = 100,
    analysis_type: Optional[str] = None
):
    """
    Get analysis history from MongoDB.
    
    Args:
        limit: Maximum number of records to return
        analysis_type: Filter by type (image, video, live)
        
    Returns:
        List of analysis results
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    if not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        raise HTTPException(status_code=503, detail="MongoDB not enabled")
    
    try:
        history = pipeline.mongodb_manager.get_analysis_history(
            limit=limit,
            analysis_type=analysis_type
        )
        return {
            "total": len(history),
            "history": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching history: {str(e)}")


@app.get("/stats", tags=["System"])
async def get_statistics():
    """Get database statistics from MongoDB"""
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    if not hasattr(pipeline, 'mongodb_manager') or pipeline.mongodb_manager is None:
        # Return basic stats if MongoDB not enabled
        return {
            "mongodb_enabled": False,
            "total_faces": len(pipeline.face_recognizer.list_identities())
        }
    
    try:
        stats = pipeline.mongodb_manager.get_statistics()
        stats['mongodb_enabled'] = True
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")


# ===== Run Server =====
if __name__ == "__main__":
    import uvicorn
    import socket
    import subprocess

    TARGET_PORT = int(os.getenv("VG_API_PORT", "8000"))

    # Kill anything already holding the target port so we always bind the same port
    def _kill_port(port: int):
        try:
            result = subprocess.run(
                f'netstat -ano | findstr :{port}',
                shell=True, capture_output=True, text=True
            )
            for line in result.stdout.strip().splitlines():
                parts = line.split()
                if f':{port}' in parts[1] and parts[3] == 'LISTENING':
                    pid = parts[4]
                    subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
                    print(f"🔪 Killed old process on port {port} (PID {pid})")
        except Exception:
            pass

    _kill_port(TARGET_PORT)

    print("\n" + "=" * 60)
    print("🚀 Starting VisionGuard AI API Server")
    print("=" * 60)
    print(f"\n📍 API will be available at: http://localhost:{TARGET_PORT}")
    print(f"📖 API Documentation: http://localhost:{TARGET_PORT}/docs")
    print(f"📊 Alternative Docs: http://localhost:{TARGET_PORT}/redoc\n")

    reload_enabled = os.getenv("VG_API_RELOAD", "0") == "1"

    if reload_enabled:
        uvicorn.run(
            "api.main:app",
            host="0.0.0.0",
            port=TARGET_PORT,
            reload=True,
            log_level="info",
        )
    else:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=TARGET_PORT,
            log_level="info",
        )
