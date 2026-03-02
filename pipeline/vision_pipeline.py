"""
Vision Pipeline Module

Integrates all three AI modules (Deepfake, Face Recognition, Object Detection)
into a unified pipeline with risk assessment.

This is the CORE module that combines:
1. Deepfake Detection
2. Face Recognition
3. Object Detection
4. Risk Scoring Algorithm

Outputs comprehensive JSON results matching the project specification.
"""

import sys
import os
import numpy as np
import cv2
from typing import Dict, Union, Optional, List
from PIL import Image
import yaml
from pathlib import Path
import asyncio
from collections import defaultdict

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from models.deepfake.deepfake_detector import DeepfakeDetector
from models.face_recognition.face_recognizer import FaceRecognizer
from models.object_detection.yolo_detector import YOLODetector
from utils.image_utils import draw_bbox, draw_circle, draw_text, bgr_to_rgb
from utils.iou_tracker import IOUTracker


class VisionPipeline:
    """
    Unified VisionGuard AI Pipeline.
    Processes images/videos through all detection modules and generates risk assessment.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the complete vision pipeline.
        
        Args:
            config_path: Path to YAML configuration file
        """
        print("=" * 60)
        print("🚀 Initializing VisionGuard AI Pipeline...")
        print("=" * 60)
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize all modules
        self._init_modules()

        # Per-stream state for Live CCTV
        self._stream_frame_counters = defaultdict(int)
        self._trackers = {}
        
        print("=" * 60)
        print("✅ VisionGuard AI Pipeline Ready!")
        print("=" * 60)
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load configuration from YAML file"""
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        
        # Default configuration
        return {
            'models': {
                'deepfake': {'threshold': 0.5},
                'face_recognition': {'similarity_threshold': 0.6},
                'object_detection': {'confidence': 0.25}
            },
            'risk_assessment': {
                'weights': {
                    'deepfake_score': 0.4,
                    'face_recognition_score': 0.3,
                    'object_detection_score': 0.3
                },
                'risk_levels': {'low': 0.3, 'medium': 0.6, 'high': 0.8},
                'suspicious_objects': ['knife', 'scissors', 'gun', 'weapon', 'cell phone', 'baseball bat'],
                'weapon_objects': ['knife', 'gun', 'weapon', 'pistol', 'rifle', 'baseball bat', 'scissors'],
                'mask_objects': ['mask', 'face mask', 'ski mask'],
                'harmful_objects': ['scissors', 'bottle', 'cell phone', 'baseball bat']
            }
        }
    
    def _init_modules(self):
        """Initialize all AI modules"""
        # Initialize MongoDB if enabled
        mongodb_config = self.config.get('mongodb', {})
        self.mongodb_manager = None
        
        if mongodb_config.get('enabled', False):
            try:
                from utils.mongodb_manager import MongoDBManager
                connection_string = mongodb_config.get('connection_string')
                database_name = mongodb_config.get('database_name', 'visionguard_ai')
                
                if connection_string:
                    self.mongodb_manager = MongoDBManager(connection_string, database_name)
                    print("✅ MongoDB initialized and ready")
                else:
                    print("⚠️ MongoDB enabled but connection_string not provided")
            except Exception as e:
                print(f"⚠️ Failed to initialize MongoDB: {e}")
                print("   Falling back to local pickle database")
        
        # 1. Deepfake Detector
        print("\n1️⃣ Loading Deepfake Detector...")
        deepfake_config = self.config['models']['deepfake']
        deepfake_threshold = deepfake_config.get('threshold', 0.35)
        gemini_api_key = deepfake_config.get('gemini_api_key', None)
        use_gemini_for_images = deepfake_config.get('use_gemini_for_images', False)
        
        # Pass gemini_api_key if available
        if gemini_api_key and gemini_api_key.strip():
            self.deepfake_detector = DeepfakeDetector(
                threshold=deepfake_threshold,
                gemini_api_key=gemini_api_key
            )
        else:
            self.deepfake_detector = DeepfakeDetector(threshold=deepfake_threshold)
        
        # Store image analysis preference
        self.use_gemini_for_images = use_gemini_for_images
        
        # 2. Face Recognizer
        print("\n2️⃣ Loading Face Recognizer...")
        face_config = self.config['models'].get('face_recognition', {})
        
        # Get user_id from config or use default
        user_id = mongodb_config.get('default_user_id', 'default_user')
        
        self.face_recognizer = FaceRecognizer(
            similarity_threshold=face_config.get('similarity_threshold', 0.6),
            database_path=face_config.get('database_path', './data/face_database'),
            mongodb_manager=self.mongodb_manager,
            user_id=user_id
        )
        
        # 3. Object Detector
        print("\n3️⃣ Loading Object Detector...")
        obj_config = self.config['models'].get('object_detection', {})
        suspicious_objects = self.config['risk_assessment'].get('suspicious_objects', [])
        weapon_model = obj_config.get('weapon_model', None)
        # Make relative paths robust (running from api/ or elsewhere)
        project_root = Path(__file__).parent.parent
        if weapon_model and not os.path.isabs(weapon_model):
            weapon_model = str((project_root / weapon_model).resolve())

        model_name = obj_config.get('name', 'yolov8n.pt')
        if model_name and isinstance(model_name, str) and model_name.endswith('.pt') and not os.path.isabs(model_name):
            candidate = (project_root / model_name)
            if candidate.exists():
                model_name = str(candidate.resolve())
        weapon_confidence = obj_config.get('weapon_confidence', 0.65)

        weapon_inference = obj_config.get('weapon_inference', {}) or {}
        self.weapon_inference_mode = str(weapon_inference.get('mode', 'roi'))
        self.weapon_inference_every_n_frames = int(weapon_inference.get('every_n_frames', 3))
        self.weapon_inference_require_person = bool(weapon_inference.get('require_person', True))
        self.weapon_inference_roi_padding = float(weapon_inference.get('roi_padding', 0.15))

        tracking_cfg = obj_config.get('tracking', {}) or {}
        self.tracking_enabled = bool(tracking_cfg.get('enabled', True))
        self.tracking_iou_threshold = float(tracking_cfg.get('iou_threshold', 0.3))
        self.tracking_max_missed = int(tracking_cfg.get('max_missed', 10))

        self.object_detector = YOLODetector(
            model_name=model_name,
            confidence=obj_config.get('confidence', 0.35),
            iou_threshold=obj_config.get('iou_threshold', 0.50),
            imgsz=obj_config.get('imgsz', 640),
            max_det=obj_config.get('max_det', 300),
            agnostic_nms=obj_config.get('agnostic_nms', False),
            suspicious_objects=suspicious_objects,
            weapon_model_path=weapon_model,
            weapon_confidence=weapon_confidence
        )
    
    def process_image(
        self,
        image: Union[str, np.ndarray, Image.Image],
        return_annotated: bool = True,
        user_id: Optional[str] = None,
        camera_id: Optional[str] = None
    ) -> Dict:
        """
        Process a single image through the complete pipeline.
        
        Args:
            image: Input image (path, numpy array, or PIL Image)
            return_annotated: Whether to return annotated image
            user_id: Optional user ID for per-user face recognition
            
        Returns:
            Complete analysis results with risk assessment
        """
        # Load image if path provided
        if isinstance(image, str):
            image = cv2.imread(image)
            if image is None:
                raise ValueError(f"Cannot load image: {image}")
        
        print("\n🔍 Processing Image...")

        # Try to extract a face crop for deepfake detection (most deepfake models expect a face ROI)
        deepfake_input = image
        try:
            faces_for_deepfake = self.face_recognizer.detect_faces(image)
            if faces_for_deepfake:
                def _area(b):
                    x1, y1, x2, y2 = b
                    return max(0, x2 - x1) * max(0, y2 - y1)

                best_face = max(
                    faces_for_deepfake,
                    key=lambda f: (float(f.get('det_score', 0.0)), _area(f.get('bbox', [0, 0, 0, 0])))
                )
                x1, y1, x2, y2 = [int(v) for v in best_face.get('bbox', [0, 0, 0, 0])]
                h, w = image.shape[:2]
                bw, bh = max(0, x2 - x1), max(0, y2 - y1)
                pad = int(0.15 * max(bw, bh))
                x1 = max(0, x1 - pad)
                y1 = max(0, y1 - pad)
                x2 = min(w, x2 + pad)
                y2 = min(h, y2 + pad)
                if x2 > x1 and y2 > y1:
                    deepfake_input = image[y1:y2, x1:x2].copy()
        except Exception:
            # Non-fatal: fall back to full-frame deepfake detection
            deepfake_input = image
        
        # ====== 1. DEEPFAKE DETECTION ======
        print("   1️⃣ Deepfake Detection...")
        # Use Gemini-only mode for image analysis if configured
        if self.use_gemini_for_images and hasattr(self.deepfake_detector, 'gemini_model') and self.deepfake_detector.gemini_model:
            print("   🤖 Using Gemini API for image analysis...")
            deepfake_result = self.deepfake_detector._predict_with_gemini(deepfake_input)
            if (not deepfake_result) or (deepfake_result.get('label') == 'UNKNOWN'):
                # Fallback to primary model if Gemini fails/returns unknown
                print("   ⚠️ Gemini unavailable/uncertain, using primary model...")
                deepfake_result = self.deepfake_detector.predict(deepfake_input)
        else:
            deepfake_result = self.deepfake_detector.predict(deepfake_input)
        
        # ====== 2. FACE RECOGNITION ======
        print("   2️⃣ Face Recognition...")
        # Pass user_id if provided, otherwise use the face_recognizer's default
        if user_id:
            # Temporarily set user_id for this recognition
            original_user_id = self.face_recognizer.user_id
            self.face_recognizer.user_id = user_id
            face_result = self.face_recognizer.recognize(image)
            self.face_recognizer.user_id = original_user_id
        else:
            face_result = self.face_recognizer.recognize(image)
        
        # Store unknown faces for later notification (will be handled by caller)
        self._last_unknown_faces = face_result.get('unknown_faces', [])
        
        # ====== 3. OBJECT DETECTION ======
        print("   3️⃣ Object Detection...")
        stream_key = f"{user_id or 'anon'}::{camera_id or 'default'}"
        self._stream_frame_counters[stream_key] += 1
        frame_index = self._stream_frame_counters[stream_key]

        is_live_stream = bool(camera_id)
        object_result = self.object_detector.detect(
            image,
            return_image=False,
            frame_index=frame_index,
            weapon_mode=(self.weapon_inference_mode if is_live_stream else 'full'),
            weapon_every_n_frames=(self.weapon_inference_every_n_frames if is_live_stream else 1),
            weapon_require_person=(self.weapon_inference_require_person if is_live_stream else False),
            weapon_roi_padding=self.weapon_inference_roi_padding,
        )

        tracking = None
        if self.tracking_enabled and camera_id:
            tracker = self._trackers.get(stream_key)
            if tracker is None:
                tracker = IOUTracker(
                    iou_threshold=self.tracking_iou_threshold,
                    max_missed=self.tracking_max_missed,
                )
                self._trackers[stream_key] = tracker

            person_indices: List[int] = []
            person_boxes: List[List[int]] = []
            for idx, obj in enumerate(object_result.get('objects', [])):
                if obj.get('source') != 'general_model':
                    continue
                if str(obj.get('label', '')).lower() != 'person':
                    continue
                bbox = obj.get('bbox')
                if not (isinstance(bbox, list) and len(bbox) == 4):
                    continue
                person_indices.append(idx)
                person_boxes.append([int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])])

            _, det_to_tid = tracker.update(person_boxes)
            for det_i, obj_i in enumerate(person_indices):
                tid = det_to_tid.get(det_i)
                if tid is not None:
                    object_result['objects'][obj_i]['track_id'] = tid

            tracking = {
                'stream_key': stream_key,
                'frame_index': frame_index,
                'tracks': tracker.snapshot(),
            }
        
        # ====== 4. RISK ASSESSMENT ======
        print("   4️⃣ Risk Assessment...")
        risk_result = self._calculate_risk(deepfake_result, face_result, object_result)
        
        # ====== 5. GENERATE OUTPUT ======
        output = {
            "deepfake": {
                "status": deepfake_result['label'].lower(),
                "confidence": deepfake_result['confidence'] / 100,
                "fake_probability": deepfake_result['fake_probability']
            },
            "face_recognition": {
                "face_detected": face_result['face_detected'],
                "identity": face_result['identity'],
                "confidence": face_result['confidence'] / 100,
                "similarity_score": face_result['similarity_score'],
                "num_faces": face_result['num_faces']
            },
            "objects": [
                {
                    "label": obj['label'],
                    "confidence": obj['confidence'],
                    "bbox": obj['bbox'],
                    **({"track_id": obj["track_id"]} if "track_id" in obj else {})
                }
                for obj in object_result['objects']
            ],
            "suspicious_objects": [
                obj['label'] for obj in object_result['suspicious_items']
            ],
            "risk_assessment": risk_result,
            "summary": self._generate_summary(deepfake_result, face_result, object_result, risk_result),
            "tracking": tracking
        }
        
        # Generate annotated image
        if return_annotated:
            output['annotated_image'] = self._create_visualization(
                image, deepfake_result, face_result, object_result, risk_result
            )
        
        print("✅ Processing Complete!\n")
        return output
    
    def _calculate_risk(
        self,
        deepfake_result: Dict,
        face_result: Dict,
        object_result: Dict
    ) -> Dict:
        """
        Calculate overall risk score with specific threat categorization.
        
        Threat Categories:
        1. EMERGENCY - Weapons detected or armed unknown person
        2. UNKNOWN PERSON - Unknown individual detected
        3. MASKED PERSON - Person wearing mask
        4. HARMFUL ACTIVITY - Suspicious behavior/objects
        5. LOW RISK - Normal activity
        """
        weights = self.config['risk_assessment']['weights']
        
        # Detect specific threats
        weapon_objects = self.config['risk_assessment'].get('weapon_objects', ['knife', 'gun', 'weapon'])
        mask_objects = self.config['risk_assessment'].get('mask_objects', ['mask'])
        
        # Check for weapons (including trained model classes)
        weapon_classes = ['Grenade', 'Knife', 'Pistol', 'Rifle', 'knife', 'gun', 'weapon', 'pistol', 'rifle']
        detected_weapons = []
        detected_masks = []
        for obj in object_result['objects']:
            # Direct class name match (case-sensitive for trained model)
            if obj['label'] in weapon_classes:
                detected_weapons.append(obj['label'])
            # Fallback to case-insensitive substring match
            elif any(weapon in obj['label'].lower() for weapon in weapon_objects):
                detected_weapons.append(obj['label'])
            
            if any(mask in obj['label'].lower() for mask in mask_objects):
                detected_masks.append(obj['label'])
        
        has_weapon = len(detected_weapons) > 0
        has_mask = len(detected_masks) > 0
        is_unknown = face_result['identity'] == 'Unknown'
        is_fake = deepfake_result['is_fake']
        
        # 1. Deepfake Risk (0-1)
        deepfake_score = deepfake_result['fake_probability']
        
        # 2. Face Recognition Risk (0-1)
        if not face_result['face_detected']:
            face_score = 0.5  # Moderate risk if no face
        elif is_unknown:
            face_score = 0.95  # Very high risk if unknown person detected
        else:
            face_score = 1 - face_result['similarity_score']  # Low similarity = high risk
        
        # 3. Object Detection Risk (0-1)
        if has_weapon:
            object_score = 1.0  # Maximum risk for weapons
        elif object_result['suspicious_detected']:
            object_score = 0.9  # Very high risk
        elif object_result['num_objects'] > 10:
            object_score = 0.4  # Moderate risk for cluttered scene
        else:
            object_score = 0.1  # Low risk
        
        # Weighted sum
        overall_score = (
            deepfake_score * weights['deepfake_score'] +
            face_score * weights['face_recognition_score'] +
            object_score * weights['object_detection_score']
        )
        
        # Determine specific threat category and risk level
        threat_category = "NORMAL"
        risk_level = "LOW"
        reasons = []
        
        # EMERGENCY - Highest priority
        if has_weapon:
            threat_category = "EMERGENCY"
            risk_level = "HIGH"  # Changed from CRITICAL to HIGH for frontend compatibility
            overall_score = 0.95  # Very high score for weapon detection
            reasons.append(f"⚠️ WEAPON DETECTED: {', '.join(detected_weapons)}")
            if is_unknown:
                reasons.append("Unknown person carrying weapon")
                overall_score = 1.0  # Maximum for armed unknown person
        
        # MASKED PERSON - High priority if also unknown
        elif has_mask:
            if is_unknown:
                threat_category = "MASKED UNKNOWN"
                risk_level = "HIGH"
                overall_score = max(overall_score, 0.85)
                reasons.append("Masked unknown person detected")
            else:
                threat_category = "MASKED PERSON"
                risk_level = "MEDIUM"
                reasons.append(f"Person wearing mask: {face_result['identity']}")
        
        # UNKNOWN PERSON - Medium-High priority
        elif is_unknown and face_result['face_detected']:
            threat_category = "UNKNOWN PERSON"
            risk_level = "HIGH"
            reasons.append("Unknown person detected - Not in database")
        
        # HARMFUL ACTIVITY - Suspicious objects/behavior
        elif object_result['suspicious_detected']:
            threat_category = "SUSPICIOUS ACTIVITY"
            risk_level = "MEDIUM"
            reasons.append(f"Suspicious objects: {', '.join([o['label'] for o in object_result['suspicious_items']])}")
        
        # DEEPFAKE DETECTION
        elif is_fake:
            threat_category = "DEEPFAKE"
            risk_level = "HIGH"
            reasons.append("Fake/manipulated image detected")
        
        # Normal activity
        else:
            risk_levels_config = self.config['risk_assessment']['risk_levels']
            if overall_score >= risk_levels_config['high']:
                risk_level = "HIGH"
                threat_category = "ELEVATED"
            elif overall_score >= risk_levels_config['medium']:
                risk_level = "MEDIUM"
                threat_category = "MODERATE"
            else:
                risk_level = "LOW"
                threat_category = "NORMAL"
        
        if not reasons:
            reasons = ["No significant threats detected"]
        
        return {
            "overall_score": round(overall_score, 4),
            "risk_level": risk_level,
            "threat_category": threat_category,
            "scores": {
                "deepfake": round(deepfake_score, 4),
                "face_recognition": round(face_score, 4),
                "object_detection": round(object_score, 4)
            },
            "threats": {
                "has_weapon": has_weapon,
                "weapons_detected": detected_weapons,
                "has_mask": has_mask,
                "is_unknown_person": is_unknown,
                "is_deepfake": is_fake
            },
            "reasons": reasons
        }
    
    def _generate_summary(
        self,
        deepfake_result: Dict,
        face_result: Dict,
        object_result: Dict,
        risk_result: Dict
    ) -> str:
        """Generate human-readable summary"""
        summary_parts = []
        
        # Deepfake
        summary_parts.append(
            f"Deepfake Status: {deepfake_result['label']} ({deepfake_result['confidence']:.1f}%)"
        )
        
        # Face
        if face_result['face_detected']:
            summary_parts.append(
                f"Identity: {face_result['identity']} ({face_result['confidence']:.1f}%)"
            )
        else:
            summary_parts.append("Identity: No face detected")
        
        # Objects
        if object_result['num_objects'] > 0:
            summary_parts.append(
                f"Objects Detected: {object_result['num_objects']}"
            )
            if object_result['suspicious_detected']:
                summary_parts.append(
                    f"⚠️ Suspicious: {', '.join([o['label'] for o in object_result['suspicious_items']])}"
                )
        
        # Risk
        summary_parts.append(f"Overall Risk: {risk_result['risk_level']}")
        
        return " | ".join(summary_parts)
    
    def _create_visualization(
        self,
        image: np.ndarray,
        deepfake_result: Dict,
        face_result: Dict,
        object_result: Dict,
        risk_result: Dict
    ) -> np.ndarray:
        """
        Create annotated image with all detection results.
        Uses circles for people/faces and squares for objects.
        """
        img_vis = image.copy()
        
        # Draw object bounding boxes (SQUARES) 🔲
        for obj in object_result['objects']:
            # 🔴 RED for weapons/dangerous items, 🟢 GREEN for normal objects
            is_suspicious = any(danger in obj['label'].lower() 
                              for danger in ['knife', 'gun', 'weapon', 'pistol', 'rifle'])
            color = (0, 0, 255) if is_suspicious else (0, 255, 0)  # BGR: Red or Green
            draw_bbox(
                img_vis,
                obj['bbox'],
                obj['label'],
                obj['confidence'],
                color=color,
                thickness=4  # Thicker for visibility
            )
        
        # Draw face circles (CIRCLES for people) ⭕
        if face_result['face_detected'] and face_result.get('faces'):
            for face in face_result['faces']:
                # 🟡 YELLOW/CYAN for known person, 🟣 MAGENTA for unknown
                if face['identity'] != 'Unknown':
                    color = (0, 255, 255)  # BGR: Yellow (Cyan in BGR)
                else:
                    color = (255, 0, 255)  # BGR: Magenta (Unknown person - Alert!)
                
                draw_circle(
                    img_vis,
                    face['bbox'],
                    face['identity'],
                    face['similarity_score'],
                    color=color,
                    thickness=4  # Thicker for visibility
                )
        
        # Add header with results and gradient background 🎨
        header_height = 140
        header = np.zeros((header_height, img_vis.shape[1], 3), dtype=np.uint8)
        
        # Risk level background with GRADIENT for visual appeal
        risk_colors = {
            "LOW": [(0, 200, 0), (0, 255, 100)],      # Dark to light green
            "MEDIUM": [(0, 100, 255), (100, 200, 255)],  # Orange gradient
            "HIGH": [(0, 0, 180), (100, 0, 255)]      # Dark to bright red
        }
        colors = risk_colors.get(risk_result['risk_level'], [(80, 80, 80), (150, 150, 150)])
        
        # Create gradient background
        for i in range(header_height):
            ratio = i / header_height
            color = tuple(int(colors[0][j] * (1 - ratio) + colors[1][j] * ratio) for j in range(3))
            header[i, :] = color
        
        # Add text
        draw_text(header, "VisionGuard AI - Analysis Results", (10, 30), font_scale=0.8, thickness=2)
        draw_text(header, f"Deepfake: {deepfake_result['label']} ({deepfake_result['confidence']:.1f}%)", 
                 (10, 60), font_scale=0.6, thickness=1)
        draw_text(header, f"Identity: {face_result['identity']} ({face_result['confidence']:.1f}%)", 
                 (10, 85), font_scale=0.6, thickness=1)
        draw_text(header, f"Risk Level: {risk_result['risk_level']} ({risk_result['overall_score']:.2f})", 
                 (10, 110), font_scale=0.7, thickness=2)
        
        # Combine header and image
        final_image = np.vstack([header, img_vis])
        
        return final_image
    
    def process_video(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        frame_skip: int = 5
    ) -> List[Dict]:
        """
        Process video file through pipeline.
        
        Args:
            video_path: Path to video file
            output_path: Optional output path for annotated video
            frame_skip: Process every Nth frame
            
        Returns:
            List of results per processed frame
        """
        print(f"\n🎥 Processing Video: {video_path}")
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        results = []
        writer = None
        frame_count = 0
        
        # Setup video writer
        if output_path:
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) + 120  # Add header
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(output_path, fourcc, fps // frame_skip, (width, height))
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            if frame_count % frame_skip != 0:
                continue
            
            # Process frame
            result = self.process_image(frame, return_annotated=output_path is not None)
            result['frame_number'] = frame_count
            results.append(result)
            
            # Write annotated frame
            if writer and 'annotated_image' in result:
                writer.write(result['annotated_image'])
            
            print(f"   Frame {frame_count}: {result['summary']}")
        
        cap.release()
        if writer:
            writer.release()
            print(f"\n💾 Saved annotated video: {output_path}")
        
        print(f"\n✅ Processed {len(results)} frames")
        return results
    
    async def _notify_unknown_faces(
        self,
        image: np.ndarray,
        unknown_faces: List[Dict],
        camera_location: str = "Unknown",
        user_id: Optional[str] = None,
        risk_assessment: Optional[Dict] = None,
        summary: Optional[str] = None,
        suspicious_objects: Optional[List[str]] = None,
    ):
        """
        Send Telegram notification for unknown faces with cooldown check.
        
        Args:
            image: Original image with unknown faces
            unknown_faces: List of unknown face data (embeddings, bboxes)
            camera_location: Location identifier
            suspicious_objects: Optional list of detected suspicious object labels
        """
        try:
            from utils.telegram_notifier import get_notifier
            
            notifier = get_notifier(user_id=user_id)
            if notifier is None:
                print("   ⚠️ Telegram notifier not initialized, skipping notification")
                return
            
            # Check cooldown for each face
            faces_to_notify = []
            for face in unknown_faces:
                if notifier.check_cooldown(face['embedding']):
                    faces_to_notify.append(face)
            
            if not faces_to_notify:
                print(f"   ⏳ All unknown faces in cooldown period ({notifier.cooldown_minutes}min), skipping notification")
                return
            
            # Cleanup old detections
            notifier.cleanup_old_detections()
            
            # Send notification ONLY for faces not in cooldown
            print(f"   📤 Sending Telegram notification for {len(faces_to_notify)} unknown face(s) (filtered from {len(unknown_faces)} total)...")
            detection_id = await notifier.send_unknown_face_notification(
                image=image,
                unknown_faces=faces_to_notify,  # Only notify new faces
                camera_location=camera_location,
                risk_assessment=risk_assessment,
                summary=summary,
                suspicious_objects=suspicious_objects,
            )
            
            if detection_id:
                print(f"   ✅ Notification sent (ID: {detection_id})")
            else:
                print(f"   ❌ Failed to send notification")
        
        except Exception as e:
            print(f"   ⚠️ Error sending notification: {e}")


# Convenience function
def analyze_image(image_path: str) -> Dict:
    """
    Quick analysis of an image without instantiating pipeline.
    
    Args:
        image_path: Path to image
        
    Returns:
        Analysis results
    """
    pipeline = VisionPipeline()
    return pipeline.process_image(image_path)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🧪 Testing VisionGuard AI Pipeline")
    print("=" * 60)
    
    # Initialize pipeline
    pipeline = VisionPipeline()
    
    # Create test image
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Process
    result = pipeline.process_image(test_image, return_annotated=False)
    
    print("\n📊 Test Results:")
    print(f"   Deepfake: {result['deepfake']['status']}")
    print(f"   Face: {result['face_recognition']['identity']}")
    print(f"   Objects: {len(result['objects'])}")
    print(f"   Risk Level: {result['risk_assessment']['risk_level']}")
    print(f"\n   Summary: {result['summary']}")
    
    print("\n" + "=" * 60)
    print("✅ VisionGuard AI Pipeline Test Complete!")
    print("=" * 60)
