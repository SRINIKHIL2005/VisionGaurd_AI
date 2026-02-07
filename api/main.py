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

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import sys
import os
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import io
import json
import base64
import yaml

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from pipeline.vision_pipeline import VisionPipeline
from utils.telegram_notifier import get_notifier, initialize_notifier, shutdown_notifier

# ===== Initialize FastAPI App =====
app = FastAPI(
    title="VisionGuard AI API",
    description="Unified computer vision system for deepfake detection, face recognition, and object detection",
    version="1.0.0"
)

# ===== CORS Configuration =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== Global Pipeline Instance =====
pipeline: Optional[VisionPipeline] = None


# ===== Startup Event =====
@app.on_event("startup")
async def startup_event():
    """Initialize pipeline and Telegram bot on startup"""
    global pipeline
    print("\n🚀 Starting VisionGuard AI API...")
    pipeline = VisionPipeline(config_path="config/settings.yaml")
    print("✅ API Ready!\n")
    
    # Initialize Telegram bot if configured
    try:
        config_path = Path("config/settings.yaml")
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f)
            
            telegram_config = config.get('telegram', {})
            if telegram_config.get('enabled', False):
                bot_token = telegram_config.get('bot_token')
                owner_chat_id = telegram_config.get('owner_chat_id')
                
                if bot_token and owner_chat_id:
                    print("🤖 Initializing Telegram Bot...")
                    await initialize_notifier(
                        bot_token=bot_token,
                        owner_chat_id=int(owner_chat_id),
                        config={
                            'cooldown_minutes': telegram_config.get('cooldown_minutes', 3),
                            'retention_days': telegram_config.get('retention_days', 10)
                        },
                        face_recognizer=pipeline.face_recognizer  # Pass shared instance
                    )
                    print("✅ Telegram Bot initialized!")
                else:
                    print("⚠️ Telegram enabled but missing bot_token or owner_chat_id")
            else:
                print("ℹ️ Telegram notifications disabled in config")
    except Exception as e:
        print(f"⚠️ Failed to initialize Telegram bot: {e}")


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
            "analyze_image": "POST /analyze/image",
            "analyze_video": "POST /analyze/video",
            "add_face": "POST /face/add",
            "list_faces": "GET /face/list",
            "health": "GET /health"
        }
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
    return_annotated: bool = Form(True)  # 🎯 DEFAULT TRUE - Always return visual analysis
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
        
        print(f"\n{'='*60}")
        print(f"🔍 IMAGE ANALYSIS REQUEST")
        print(f"{'='*60}")
        print(f"📥 Received image: {image.shape}")
        print(f"🎯 return_annotated parameter: {return_annotated} (type: {type(return_annotated)})")
        
        # Process image
        result = pipeline.process_image(image, return_annotated=return_annotated)
        
        # Handle Telegram notifications for unknown faces (async)
        if hasattr(pipeline, '_last_unknown_faces') and pipeline._last_unknown_faces:
            # Import notifier
            from utils.telegram_notifier import get_notifier
            notifier = get_notifier()
            
            if notifier:
                # Send notification in background task
                import asyncio
                asyncio.create_task(
                    pipeline._notify_unknown_faces(
                        image, 
                        pipeline._last_unknown_faces,
                        camera_location="Live CCTV"
                    )
                )
        
        print(f"\n📊 Pipeline returned {len(result)} keys: {list(result.keys())}")
        print(f"🔍 Has 'annotated_image' key: {'annotated_image' in result}")
        
        # Encode annotated image BEFORE converting numpy types
        if 'annotated_image' in result and result['annotated_image'] is not None:
            print(f"✅ annotated_image exists! Shape: {result['annotated_image'].shape}")
            result['annotated_image'] = encode_image(result['annotated_image'])
            print(f"✅ Encoded to base64: {len(result['annotated_image'])} characters")
        else:
            print(f"❌ NO annotated_image in result!")
            print(f"   return_annotated was: {return_annotated}")
            print(f"   Result keys: {list(result.keys())}")
        
        # Convert numpy types to Python types for JSON serialization
        result = convert_numpy_types(result)
        
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
    weapon_detection_only: bool = Form(False)
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
            os.remove(output_video_path)
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        print(f"\n📊 Analysis Complete:")
        print(f"   Frames processed: {len(results)}")
        print(f"   Weapons detected: {total_weapons}")
        print(f"   Frames with weapons: {frames_with_weapons}")
        print(f"{'='*60}\n")
        
        response = {
            "num_frames_processed": len(results),
            "weapon_summary": weapon_summary,
            "weapon_detections": dict(weapon_detections),
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
    file: UploadFile = File(...)
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
        
        # Add to database
        success = pipeline.face_recognizer.add_identity(image, name)
        
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
async def list_faces(detailed: bool = True):
    """
    Get list of all identities in the database.
    
    Args:
        detailed: Return full metadata (photo, date, approver, location)
    
    Returns:
        List of identity names or detailed info with metadata
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    identities = pipeline.face_recognizer.list_identities(detailed=detailed)
    
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
async def remove_face(name: str):
    """
    Remove an identity from the database.
    
    Args:
        name: Identity name to remove
        
    Returns:
        Success status
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    success = pipeline.face_recognizer.remove_identity(name)
    
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


# ===== Run Server =====
if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "=" * 60)
    print("🚀 Starting VisionGuard AI API Server")
    print("=" * 60)
    print("\n📍 API will be available at: http://localhost:8000")
    print("📖 API Documentation: http://localhost:8000/docs")
    print("📊 Alternative Docs: http://localhost:8000/redoc\n")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
