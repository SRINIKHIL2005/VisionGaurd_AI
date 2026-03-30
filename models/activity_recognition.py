"""
Activity Recognition Module

Detects human actions and behaviors from video:
- Running/fast movement detection
- Suspicious postures and movements
- Crowd behavior analysis
- Abnormal activity patterns
- Gesture recognition (raising arms, etc.)

Tech Stack:
- OpenCV - Motion and pose analysis
- MediaPipe - Human pose estimation (lightweight alternative)
- NumPy - Calculations

ML Algorithms Used:
- Pose-based feature extraction
- Movement pattern matching
- Statistical anomaly detection
- k-means clustering for behavior patterns
"""

import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple
from collections import deque
import warnings

warnings.filterwarnings('ignore')

try:
    import mediapipe as mp
    MP_AVAILABLE = True
except ImportError:
    MP_AVAILABLE = False
    print("⚠️ MediaPipe not available. Pose-based activity detection will be limited.")


class ActivityRecognizer:
    """
    Recognizes human activities and suspicious behaviors.
    Uses pose estimation and movement analysis.
    """
    
    def __init__(self, use_pose: bool = True):
        """
        Args:
            use_pose: Use MediaPipe pose estimation if available
        """
        self.use_pose = use_pose and MP_AVAILABLE
        
        if self.use_pose:
            try:
                mp_pose = mp.solutions.pose
                self.pose = mp_pose.Pose(
                    static_image_mode=False,
                    model_complexity=0,  # Lite model for speed
                    smooth_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
                self.mp_drawing = mp.solutions.drawing_utils
                print("✅ MediaPipe Pose Estimation loaded")
            except Exception as e:
                print(f"⚠️ Failed to load MediaPipe: {e}")
                self.use_pose = False
        
        self.activity_history = {}  # person_id -> deque of activities
        self.pose_history = {}  # person_id -> deque of poses
    
    def detect_activities(
        self,
        frame: np.ndarray,
        detections: List[Dict],
        motion_mask: Optional[np.ndarray] = None
    ) -> List[Dict]:
        """
        Detect activities in frame.
        
        Args:
            frame: Video frame
            detections: List of detections with track_id and bbox
            motion_mask: Optional motion/optical flow mask
            
        Returns:
            List of detected activities
        """
        activities = []
        
        for det in detections:
            # Activity recognition is only meaningful for people.
            if str(det.get('class', '')).lower() != 'person':
                continue

            track_id = det.get('track_id')
            if track_id is None:
                continue
            
            x1, y1, x2, y2 = det['bbox']
            
            # Detect activity based on motion and posture
            activity = self._detect_person_activity(
                frame, (x1, y1, x2, y2), track_id, motion_mask
            )
            
            if activity:
                activities.append(activity)
        
        return activities
    
    def _detect_person_activity(
        self,
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
        person_id: int,
        motion_mask: Optional[np.ndarray] = None
    ) -> Optional[Dict]:
        """
        Detect activity for a single person.
        """
        x1, y1, x2, y2 = bbox
        person_box = frame[max(0, y1):min(frame.shape[0], y2), max(0, x1):min(frame.shape[1], x2)]
        
        if person_box.size == 0:
            return None
        
        activity_type = "NORMAL"
        confidence = 0.5
        details = {}
        
        # Check motion intensity
        if motion_mask is not None:
            motion_box = motion_mask[max(0, y1):min(motion_mask.shape[0], y2), max(0, x1):min(motion_mask.shape[1], x2)]
            motion_intensity = np.sum(motion_box > 0) / motion_box.size if motion_box.size > 0 else 0
            
            if motion_intensity > 0.3:
                activity_type = "RUNNING"
                confidence = min(0.95, 0.5 + motion_intensity)
                details['motion_intensity'] = round(motion_intensity, 3)
            elif motion_intensity > 0.15:
                activity_type = "WALKING"
                confidence = 0.7
                details['motion_intensity'] = round(motion_intensity, 3)
        
        # Pose-based analysis
        if self.use_pose:
            pose_activity, pose_conf = self._analyze_pose(person_box, person_id)
            if pose_activity:
                activity_type = pose_activity
                confidence = pose_conf
                details['pose_based'] = True
        
        # Aspect ratio analysis (rough pose detection without MediaPipe)
        height = y2 - y1
        width = x2 - x1
        
        if height > 0 and width > 0:
            aspect_ratio = height / width
            
            # Tall and narrow = standing/raised arms
            if aspect_ratio > 2.5:
                if activity_type == "NORMAL":
                    activity_type = "RAISED_ARMS"
                    confidence = 0.6
                    details['raised_arms'] = True
            # Short and wide = crouching/ducking
            elif aspect_ratio < 0.8:
                if activity_type != "RUNNING":
                    activity_type = "CROUCHING"
                    confidence = 0.65
                    details['crouching'] = True
        
        # Classify suspicious activities
        if activity_type in ["RAISED_ARMS", "CROUCHING"]:
            details['is_suspicious'] = True
            confidence = min(0.95, confidence + 0.2)
        
        return {
            'person_id': person_id,
            'activity': activity_type,
            'confidence': round(confidence, 3),
            'bbox': bbox,
            'details': details
        }
    
    def _analyze_pose(self, person_frame: np.ndarray, person_id: int) -> Tuple[Optional[str], float]:
        """
        Analyze pose using MediaPipe.
        
        Returns:
            (activity_type, confidence)
        """
        if not self.use_pose:
            return None, 0.0
        
        try:
            rgb_frame = cv2.cvtColor(person_frame, cv2.COLOR_BGR2RGB)
            results = self.pose.process(rgb_frame)
            
            if not results.pose_landmarks:
                return None, 0.0
            
            landmarks = results.pose_landmarks.landmark
            
            # Extract key joint positions
            nose = landmarks[0]
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]
            left_elbow = landmarks[13]
            right_elbow = landmarks[14]
            left_hip = landmarks[23]
            right_hip = landmarks[24]
            left_knee = landmarks[25]
            right_knee = landmarks[26]
            
            # Check if joints are visible
            visible_joints = sum([
                left_shoulder.visibility, right_shoulder.visibility,
                left_elbow.visibility, right_elbow.visibility,
                left_knee.visibility, right_knee.visibility
            ])
            
            if visible_joints < 3:
                return None, 0.0
            
            # Activity detection based on pose
            # 1. Check if arms are raised
            if (left_elbow.y < left_shoulder.y and right_elbow.y < right_shoulder.y):
                return "RAISED_ARMS", 0.7
            
            # 2. Check if person is crouching (knees high relative to hips)
            if (left_knee.y < left_hip.y and right_knee.y < right_hip.y):
                return "CROUCHING", 0.7
            
            # 3. Check body angle (leaning)
            shoulder_dist = abs(left_shoulder.x - right_shoulder.x)
            hip_dist = abs(left_hip.x - right_hip.x)
            
            if shoulder_dist > hip_dist * 1.5:
                return "LEANING", 0.6
            
            return None, 0.0
        
        except Exception as e:
            return None, 0.0


class SuspiciousBehaviorDetector:
    """
    Detects suspicious behavioral patterns.
    Uses pattern matching and statistical analysis.
    """
    
    def __init__(self):
        """Initialize detector"""
        self.person_history = {}  # person_id -> behavior history
        self.frame_threshold = 30  # frames to analyze
        self.reported_patterns = {}  # (person_id, pattern) -> last_report_frame

    def reset(self):
        """Reset state between video runs to avoid stale carry-over."""
        self.person_history = {}
        self.reported_patterns = {}
    
    def update_person_behavior(
        self,
        person_id: int,
        activity: str,
        detection: Dict,
        frame_number: int
    ):
        """
        Track person's behavioral history.
        """
        if person_id not in self.person_history:
            self.person_history[person_id] = deque(maxlen=self.frame_threshold)
        
        self.person_history[person_id].append({
            'frame': frame_number,
            'activity': activity,
            'bbox': detection.get('bbox'),
            'confidence': detection.get('confidence', 0.0)
        })
    
    def detect_suspicious_patterns(self, frame_number: Optional[int] = None) -> List[Dict]:
        """
        Detect suspicious behavioral patterns from history.
        
        Returns:
            List of suspicious behavior detections
        """
        suspicious = []
        
        for person_id, history in self.person_history.items():
            if len(history) < 5:
                continue
            
            recent = list(history)
            current_frame = frame_number if frame_number is not None else int(recent[-1]['frame'])
            cooldown_frames = max(10, self.frame_threshold // 2)

            def should_emit(pattern_name: str) -> bool:
                key = (person_id, pattern_name)
                # Emit each person-pattern at most once per video run.
                if key in self.reported_patterns:
                    return False
                self.reported_patterns[key] = current_frame
                return True
            
            # Pattern 1: Repeated running/fast movement
            running_count = sum(1 for h in recent if h['activity'] in ['RUNNING', 'RAPID_MOVEMENT'])
            if running_count > len(recent) * 0.6 and should_emit('REPEATED_RUNNING'):
                suspicious.append({
                    'person_id': person_id,
                    'pattern': 'REPEATED_RUNNING',
                    'frames_with_activity': running_count,
                    'severity': 'HIGH',
                    'description': 'Person repeatedly running/moving rapidly'
                })
            
            # Pattern 2: Raised arms (suspicious posture)
            raised_arms_count = sum(1 for h in recent if h['activity'] == 'RAISED_ARMS')
            if raised_arms_count > len(recent) * 0.5 and should_emit('SUSPICIOUS_POSTURE'):
                suspicious.append({
                    'person_id': person_id,
                    'pattern': 'SUSPICIOUS_POSTURE',
                    'frames_with_activity': raised_arms_count,
                    'severity': 'HIGH',
                    'description': 'Person with raised arms repeatedly (potential threat)'
                })
            
            # Pattern 3: Alternating between crouching and running
            activities = [h['activity'] for h in recent]
            if 'CROUCHING' in activities and 'RUNNING' in activities and should_emit('EVASIVE_BEHAVIOR'):
                suspicious.append({
                    'person_id': person_id,
                    'pattern': 'EVASIVE_BEHAVIOR',
                    'severity': 'MEDIUM',
                    'description': 'Alternating between crouching and running (evasive)'
                })
        
        return suspicious


class CrowdBehaviorAnalyzer:
    """
    Analyzes crowd-level behavior patterns.
    Detects unusual collective behaviors.
    """
    
    def __init__(self):
        """Initialize analyzer"""
        self.crowd_state_history = deque(maxlen=100)
    
    def analyze_crowd(self, activities: List[Dict], detections: List[Dict]) -> Dict:
        """
        Analyze crowd behavior.
        
        Args:
            activities: List of individual activities
            detections: List of all detections
            
        Returns:
            Crowd analysis dict
        """
        person_count = len([d for d in detections if d.get('class', '').lower() == 'person'])
        
        # Activity distribution
        activity_dist = {}
        for act in activities:
            activity_type = act.get('activity', 'UNKNOWN')
            activity_dist[activity_type] = activity_dist.get(activity_type, 0) + 1
        
        # Calculate crowd state
        if person_count == 0:
            crowd_state = "EMPTY"
        elif person_count < 5:
            crowd_state = "SPARSE"
        elif person_count < 20:
            if activity_dist.get('RUNNING', 0) > person_count * 0.3:
                crowd_state = "SCATTERED_RUNNING"
            else:
                crowd_state = "NORMAL"
        else:
            if activity_dist.get('RUNNING', 0) > person_count * 0.5:
                crowd_state = "PANIC_RUNNING"
            elif activity_dist.get('RAISED_ARMS', 0) > person_count * 0.3:
                crowd_state = "AGITATED"
            else:
                crowd_state = "DENSE_CROWD"
        
        # Detect suspicious crowd pattern
        is_suspicious = crowd_state in [
            'PANIC_RUNNING', 'SCATTERED_RUNNING', 'AGITATED'
        ]
        
        return {
            'person_count': person_count,
            'crowd_state': crowd_state,
            'activity_distribution': activity_dist,
            'is_suspicious': is_suspicious,
            'severity': 'HIGH' if crowd_state == 'PANIC_RUNNING' else (
                'MEDIUM' if is_suspicious else 'LOW'
            )
        }
