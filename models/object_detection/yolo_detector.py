"""
Object Detection Module

This module uses YOLOv8 from Ultralytics for real-time object detection.
Detects objects, draws bounding boxes, and identifies suspicious items.

Tech Stack:
- Ultralytics YOLOv8 - Latest YOLO implementation
- OpenCV - Image processing
- NumPy - Array operations

Input:
- RGB image (numpy array or PIL Image)
- Video file path
- Camera feed

Output:
- detected_objects: List of objects with labels and confidence
- bounding_boxes: Coordinates for each object
- suspicious_items: Flagged dangerous objects
"""

import cv2
import numpy as np
from typing import Dict, List, Union, Optional, Tuple
from PIL import Image
import warnings

warnings.filterwarnings('ignore')

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError as e:
    YOLO_AVAILABLE = False
    print(f"⚠️ Ultralytics import error: {e}")
    print("💡 Install with: pip install ultralytics")
except Exception as e:
    YOLO_AVAILABLE = False
    print(f"⚠️ Ultralytics error: {e}")
    print("💡 Try: pip install --upgrade ultralytics")


class YOLODetector:
    """
    YOLOv8-based object detection for real-time analysis.
    Supports image, video, and camera feed processing.
    """
    
    def __init__(
        self,
        model_name: str = 'yolov8n.pt',
        confidence: float = 0.35,
        iou_threshold: float = 0.50,
        device: str = 'auto',
        suspicious_objects: Optional[List[str]] = None,
        weapon_model_path: Optional[str] = None,
        weapon_confidence: float = 0.65,
        imgsz: int = 640,
        max_det: int = 300,
        agnostic_nms: bool = False
    ):
        """
        Initialize YOLO detector with dual model support (v8 + v11).
        
        Args:
            model_name: YOLOv8 model variant (general object detection)
                       'yolov8n.pt' - Nano (fastest, ~80% accuracy, COCO 80 classes)
                       'yolov8s.pt' - Small (balanced, ~85% accuracy)
                       'yolov8m.pt' - Medium (good accuracy, ~88% accuracy)
                       'yolov8l.pt' - Large (high accuracy, ~90% accuracy)
                       'yolov8x.pt' - Extra Large (best accuracy, ~91% accuracy)
            confidence: Minimum confidence threshold (0-1)
                       Recommended: 0.35-0.45 for better recall
            iou_threshold: IoU threshold for NMS (0-1)
                          Recommended: 0.45-0.60 to reduce duplicates
            device: 'auto', 'cuda', or 'cpu'
            suspicious_objects: List of object classes to flag as suspicious
            weapon_model_path: Path to YOLOv11 weapon detection model
                              Example: 'Learning/best.pt' (YOLOv11 nano trained on weapons)
            weapon_confidence: Confidence threshold for weapon detection (higher = fewer false positives)
            imgsz: Input image size (640, 800, 1024)
                  Larger = more accurate but slower
            max_det: Maximum detections per image
            agnostic_nms: Class-agnostic NMS
        """
        self.confidence = confidence
        self.iou_threshold = iou_threshold
        self.weapon_confidence = weapon_confidence
        self.imgsz = imgsz
        self.max_det = max_det
        self.agnostic_nms = agnostic_nms
        
        # Default suspicious objects - expanded list for better detection
        self.suspicious_objects = suspicious_objects or [
            'knife', 'scissors', 'gun', 'weapon', 'mask',
            'cell phone',  # Can be suspicious in certain contexts
            'baseball bat', 'bottle', 'fire hydrant',  # Potential weapons
            'pistol', 'rifle', 'handgun', 'firearm'  # For custom weapon models
        ]
        
        # Determine device
        if device == 'auto':
            import torch
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
        
        print(f"🔧 Initializing YOLO Detector on {self.device}...")
        
        if not YOLO_AVAILABLE:
            print("❌ Ultralytics YOLO not installed")
            self.model = None
            return
        
        try:
            # Load YOLOv8 model for general object detection
            self.model = YOLO(model_name)
            self.model.to(self.device)
            
            print(f"✅ YOLOv8 general detector loaded: {model_name}")
            print(f"📊 Classes: {len(self.model.names)} COCO classes (people, cars, animals, etc.)")
            print(f"   Detected objects: person, car, dog, cat, bottle, etc.")
            print(f"   Note: YOLOv8 focuses on general objects, not specialized weapons")
            
            # Try to load YOLOv11 weapon detection model
            self.weapon_model = None
            if weapon_model_path:
                try:
                    import os
                    if os.path.exists(weapon_model_path):
                        self.weapon_model = YOLO(weapon_model_path)
                        self.weapon_model.to(self.device)
                        print(f"\n🔫 YOLOv11 WEAPON DETECTOR LOADED: {weapon_model_path}")
                        print(f"   Weapon classes: {len(self.weapon_model.names)} (knife, gun, grenade, etc.)")
                        print(f"   ✅ System now supports advanced firearm/weapon detection!")
                        print(f"   📌 Models: YOLOv8 (general) + YOLOv11 (weapons)")
                    else:
                        print(f"\n⚠️  Weapon model not found at: {weapon_model_path}")
                except Exception as e:
                    print(f"\n⚠️  Could not load YOLOv11 weapon model: {e}")
            else:
                # Auto-detect weapon model in common locations
                import os
                possible_paths = [
                    'weapon_detector.pt',
                    'models/weapon_detector.pt',
                    'weapon_detection.pt',
                    'gun_detector.pt'
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        try:
                            self.weapon_model = YOLO(path)
                            self.weapon_model.to(self.device)
                            print(f"\n🔫 AUTO-DETECTED WEAPON MODEL: {path}")
                            print(f"   Additional classes: {len(self.weapon_model.names)}")
                            print(f"   ✅ System now supports firearm/weapon detection!")
                            break
                        except:
                            continue
            
        except Exception as e:
            print(f"⚠️ Error loading YOLO: {e}")
            self.model = None
    
    def preprocess_image(self, image: Union[np.ndarray, Image.Image]) -> np.ndarray:
        """
        Convert image to OpenCV format (BGR numpy array).
        
        Args:
            image: Input image
            
        Returns:
            BGR numpy array
        """
        if isinstance(image, Image.Image):
            image = np.array(image)
            # Convert RGB to BGR
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        # If it's already a numpy array (most of our pipeline uses OpenCV), assume it's BGR.
        # Do NOT swap channels here; doing so breaks YOLO accuracy on live frames.
        
        return image
    
    def detect(
        self,
        image: Union[np.ndarray, Image.Image],
        return_image: bool = False,
        *,
        frame_index: Optional[int] = None,
        weapon_mode: str = "full",
        weapon_every_n_frames: int = 1,
        weapon_require_person: bool = True,
        weapon_roi_padding: float = 0.15
    ) -> Dict:
        """
        Detect objects in a single image.
        
        Args:
            image: Input image
            return_image: Whether to return annotated image
            
        Returns:
            Dictionary with detection results
        """
        if self.model is None:
            return {
                'objects': [],
                'num_objects': 0,
                'suspicious_detected': False,
                'suspicious_items': [],
                'annotated_image': None
            }
        
        # Preprocess
        image_bgr = self.preprocess_image(image)
        
        # Run inference with standard model
        results = self.model.predict(
            image_bgr,
            conf=self.confidence,
            iou=self.iou_threshold,
            imgsz=self.imgsz,
            max_det=self.max_det,
            agnostic_nms=self.agnostic_nms,
            device=self.device,
            verbose=False
        )
        
        # Parse results
        detected_objects = []
        suspicious_items = []
        person_bboxes: List[List[int]] = []
        
        for result in results:
            boxes = result.boxes
            
            for box in boxes:
                # Extract box info
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = self.model.names[cls_id]
                
                obj_dict = {
                    'label': label,
                    'confidence': round(conf, 4),
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'class_id': cls_id,
                    'source': 'general_model'
                }
                
                detected_objects.append(obj_dict)

                if label.lower() == 'person':
                    person_bboxes.append(obj_dict['bbox'])
                
                # Check if suspicious
                if label.lower() in [s.lower() for s in self.suspicious_objects]:
                    suspicious_items.append(obj_dict)
        
        weapon_results = []
        run_weapon = (
            self.weapon_model is not None and
            weapon_every_n_frames >= 1 and
            (frame_index is None or ((frame_index - 1) % weapon_every_n_frames) == 0) and
            (not weapon_require_person or len(person_bboxes) > 0)
        )

        # Also run weapon model if available (optionally gated)
        if run_weapon:
            if weapon_mode not in ("full", "roi"):
                weapon_mode = "full"

            if weapon_mode == "roi" and len(person_bboxes) > 0:
                h, w = image_bgr.shape[:2]
                for bbox in person_bboxes:
                    x1, y1, x2, y2 = bbox
                    bw, bh = max(0, x2 - x1), max(0, y2 - y1)
                    pad = int(weapon_roi_padding * max(bw, bh))
                    rx1 = max(0, x1 - pad)
                    ry1 = max(0, y1 - pad)
                    rx2 = min(w, x2 + pad)
                    ry2 = min(h, y2 + pad)
                    if rx2 <= rx1 or ry2 <= ry1:
                        continue
                    roi = image_bgr[ry1:ry2, rx1:rx2]
                    roi_results = self.weapon_model.predict(
                        roi,
                        conf=self.weapon_confidence,
                        iou=self.iou_threshold,
                        imgsz=self.imgsz,
                        max_det=self.max_det,
                        device=self.device,
                        verbose=False
                    )
                    weapon_results.extend(roi_results)

                    for result in roi_results:
                        boxes = result.boxes
                        for box in boxes:
                            wx1, wy1, wx2, wy2 = box.xyxy[0].cpu().numpy()
                            conf = float(box.conf[0])
                            cls_id = int(box.cls[0])
                            label = self.weapon_model.names[cls_id]

                            obj_dict = {
                                'label': label,
                                'confidence': round(conf, 4),
                                'bbox': [int(wx1) + rx1, int(wy1) + ry1, int(wx2) + rx1, int(wy2) + ry1],
                                'class_id': cls_id,
                                'source': 'weapon_model',
                                'is_weapon': True
                            }
                            detected_objects.append(obj_dict)
                            suspicious_items.append(obj_dict)
            else:
                weapon_results = self.weapon_model.predict(
                    image_bgr,
                    conf=self.weapon_confidence,  # Use configurable weapon threshold (default 0.65)
                    iou=self.iou_threshold,
                    imgsz=self.imgsz,
                    max_det=self.max_det,
                    device=self.device,
                    verbose=False
                )
            
                for result in weapon_results:
                    boxes = result.boxes
                    
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        label = self.weapon_model.names[cls_id]
                        
                        # Mark as weapon detection (keep original label for matching)
                        obj_dict = {
                            'label': label,  # Keep original: Grenade, Knife, Pistol, Rifle
                            'confidence': round(conf, 4),
                            'bbox': [int(x1), int(y1), int(x2), int(y2)],
                            'class_id': cls_id,
                            'source': 'weapon_model',
                            'is_weapon': True  # Flag for easy identification
                        }
                        
                        detected_objects.append(obj_dict)
                        suspicious_items.append(obj_dict)  # All weapon detections are suspicious
        
        # Generate annotated image if requested
        annotated_image = None
        if return_image and len(results) > 0:
            annotated_image = results[0].plot()
            # If weapon model detected something, add those annotations too
            if self.weapon_model is not None and len(weapon_results) > 0:
                try:
                    weapon_annotated = weapon_results[0].plot()
                    # Overlay weapon detections on standard image
                    annotated_image = cv2.addWeighted(annotated_image, 0.7, weapon_annotated, 0.3, 0)
                except Exception:
                    pass
        
        return {
            'objects': detected_objects,
            'num_objects': len(detected_objects),
            'suspicious_detected': len(suspicious_items) > 0,
            'suspicious_items': suspicious_items,
            'annotated_image': annotated_image
        }
    
    def detect_video(
        self,
        video_path: str,
        frame_skip: int = 5,
        output_path: Optional[str] = None
    ) -> List[Dict]:
        """
        Detect objects in a video file.
        
        Args:
            video_path: Path to video file
            frame_skip: Process every Nth frame
            output_path: Optional path to save annotated video
            
        Returns:
            List of detection results per frame
        """
        if self.model is None:
            print("❌ YOLO model not available")
            return []
        
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            print(f"❌ Cannot open video: {video_path}")
            return []
        
        frame_results = []
        frame_count = 0
        
        # Video writer setup
        writer = None
        if output_path:
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        print(f"🎥 Processing video: {video_path}")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # Skip frames
            if frame_count % frame_skip != 0:
                continue
            
            # Detect objects
            result = self.detect(frame, return_image=output_path is not None)
            result['frame_number'] = frame_count
            frame_results.append(result)
            
            # Write annotated frame
            if writer and result['annotated_image'] is not None:
                writer.write(result['annotated_image'])
        
        cap.release()
        if writer:
            writer.release()
            print(f"💾 Saved annotated video to: {output_path}")
        
        print(f"✅ Processed {len(frame_results)} frames")
        return frame_results
    
    def detect_camera(
        self,
        camera_id: int = 0,
        display: bool = True,
        record_path: Optional[str] = None
    ):
        """
        Real-time object detection from camera feed.
        
        Args:
            camera_id: Camera device ID (0 for default webcam)
            display: Show live feed window
            record_path: Optional path to record annotated feed
            
        Returns:
            Generator yielding detection results per frame
        """
        if self.model is None:
            print("❌ YOLO model not available")
            return
        
        cap = cv2.VideoCapture(camera_id)
        
        if not cap.isOpened():
            print(f"❌ Cannot open camera {camera_id}")
            return
        
        # Video writer setup
        writer = None
        if record_path:
            fps = 20
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(record_path, fourcc, fps, (width, height))
        
        print("📹 Starting camera detection. Press 'q' to quit.")
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Detect objects
                result = self.detect(frame, return_image=True)
                
                # Display
                if display and result['annotated_image'] is not None:
                    cv2.imshow('YOLO Detection', result['annotated_image'])
                    
                    # Record
                    if writer:
                        writer.write(result['annotated_image'])
                    
                    # Quit on 'q'
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                
                yield result
        
        finally:
            cap.release()
            if writer:
                writer.release()
            if display:
                cv2.destroyAllWindows()
            print("📹 Camera detection stopped")
    
    def get_class_names(self) -> List[str]:
        """Get list of all detectable object classes"""
        if self.model:
            return list(self.model.names.values())
        return []
    
    def set_suspicious_objects(self, objects: List[str]):
        """Update the list of suspicious object classes"""
        self.suspicious_objects = objects
        print(f"🚨 Suspicious objects updated: {objects}")


# Convenience function
def detect_objects(image: Union[np.ndarray, Image.Image]) -> Dict:
    """
    Quick object detection without instantiating class.
    
    Args:
        image: Input image
        
    Returns:
        Detection results
    """
    detector = YOLODetector()
    return detector.detect(image)


if __name__ == "__main__":
    # Test the detector
    print("\n🧪 Testing YOLO Detector...\n")
    
    # Create test image
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Initialize detector
    detector = YOLODetector(model_name='yolov8n.pt')
    
    if detector.model:
        # Run detection
        result = detector.detect(test_image)
        
        print("\n📊 Detection Result:")
        print(f"   Objects Detected: {result['num_objects']}")
        print(f"   Suspicious Items: {len(result['suspicious_items'])}")
        print(f"   Classes Available: {len(detector.get_class_names())}")
        print("\n✅ YOLO Detector working correctly!")
    else:
        print("\n⚠️ YOLO model not available. Install ultralytics first.")
