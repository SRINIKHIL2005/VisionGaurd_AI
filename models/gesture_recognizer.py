"""
Gesture and Pose Recognition Module - Simplified Version

This simplified version focuses on detecting suspicious behaviors 
using OpenCV and basic computer vision techniques.

Detects:
1. Rapid hand/body movements (potential weapon drawing)
2. Crowding and physical aggression indicators
3. Unusual motion patterns
4. Erratic movements
"""

import cv2
import numpy as np
from typing import Dict, List, Optional
import time

class GestureRecognizer:
    """Simplified gesture recognizer using OpenCV motion detection."""
    
    def __init__(self):
        """Initialize gesture recognizer."""
        self.prev_frame_gray = None
        self.frame_count = 0
        self.motion_history = []
        self.max_history = 30
        self.last_behavior_report_frame = {}
        self.report_cooldown_frames = 30
        
        print("✅ Gesture Recognizer initialized (OpenCV-based motion detection)")

    def reset(self):
        """Reset state between videos to avoid carrying stale motion patterns."""
        self.prev_frame_gray = None
        self.frame_count = 0
        self.motion_history = []
        self.last_behavior_report_frame = {}

    def _should_emit(self, behavior_key: str) -> bool:
        """Emit behavior events with cooldown to prevent per-frame spam."""
        last = self.last_behavior_report_frame.get(behavior_key, -self.report_cooldown_frames)
        if (self.frame_count - last) < self.report_cooldown_frames:
            return False
        self.last_behavior_report_frame[behavior_key] = self.frame_count
        return True
    
    def analyze_frame(self, frame: np.ndarray) -> Dict:
        """
        Analyze a frame for suspicious movements and behaviors.
        
        Args:
            frame: Input frame (BGR format)
            
        Returns:
            Dictionary with gesture and behavior analysis
        """
        h, w = frame.shape[:2]
        
        results = {
            'poses': [],
            'hands': [],
            'gestures': [],
            'suspicious_behaviors': [],
            'threat_level': 'LOW'
        }
        
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect motion
            if self.prev_frame_gray is not None:
                # Check if frame dimensions changed - if so, skip difference calculation
                if self.prev_frame_gray.shape != gray.shape:
                    print(f"⚠️ Frame dimensions changed from {self.prev_frame_gray.shape} to {gray.shape}, resetting motion history")
                    self.prev_frame_gray = gray
                    self.motion_history = []
                    return results
                
                # Calculate frame difference
                diff = cv2.absdiff(self.prev_frame_gray, gray)
                motion_amount = np.sum(diff > 30) / (h * w)  # Normalized motion
                self.motion_history.append(motion_amount)
                
                # Keep history
                if len(self.motion_history) > self.max_history:
                    self.motion_history.pop(0)
                
                # Analyze motion patterns
                if motion_amount > 0.05 and self._should_emit('rapid_movement'):  # High motion
                    results['suspicious_behaviors'].append({
                        'type': 'rapid_movement',
                        'level': 'MEDIUM',
                        'description': 'Rapid motion detected',
                        'confidence': float(motion_amount)
                    })
                    results['threat_level'] = 'MEDIUM'
                
                # Check for erratic patterns (high motion variance)
                if len(self.motion_history) > 5:
                    recent_motion = self.motion_history[-5:]
                    motion_variance = np.var(recent_motion)
                    if motion_variance > 0.001 and self._should_emit('erratic_movement'):  # High variance = erratic
                        results['suspicious_behaviors'].append({
                            'type': 'erratic_movement',
                            'level': 'HIGH',
                            'description': 'Erratic/unpredictable motion detected',
                            'confidence': float(motion_variance)
                        })
                        results['threat_level'] = 'HIGH'
            
            # Store current frame
            self.prev_frame_gray = gray
            self.frame_count += 1
            
            # Detect edges for hand/posture features
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Analyze hand-like contours (rough estimation)
            suspicious_contours = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if 200 < area < 5000:  # Potential hand-sized regions
                    x, y, w_c, h_c = cv2.boundingRect(contour)
                    aspect_ratio = float(w_c) / h_c if h_c > 0 else 0
                    
                    # Extreme aspect ratios might indicate weapon
                    if aspect_ratio > 3 or aspect_ratio < 0.33:
                        suspicious_contours.append({
                            'region': (x, y, w_c, h_c),
                            'aspect_ratio': aspect_ratio
                        })
            
            recent_motion = np.mean(self.motion_history[-3:]) if self.motion_history else 0.0
            # Only emit suspicious-item gesture when contour evidence and motion both support it.
            if len(suspicious_contours) >= 2 and recent_motion > 0.02 and self._should_emit('suspicious_item'):
                results['hands'] = [{
                    'count': len(suspicious_contours),
                    'regions': [c['region'] for c in suspicious_contours]
                }]
                results['gestures'].append({
                    'gesture': 'SUSPICIOUS_ITEM',
                    'confidence': 0.6
                })
            
            return results
            
        except Exception as e:
            print(f"⚠️ Error in gesture analysis: {e}")
            return results
    
    def _detect_suspicious_patterns(self, motion_history: List[float]) -> tuple:
        """Detect suspicious motion patterns."""
        if len(motion_history) < 2:
            return 'LOW', 0.0
        
        recent = np.array(motion_history[-10:]) if len(motion_history) >= 10 else np.array(motion_history)
        
        # Check for sudden spikes (weapon drawing)
        if len(recent) >= 2:
            spike = max(recent) - np.mean(recent[:-1])
            if spike > 0.1:
                return 'HIGH', float(spike)
        
        # Check for sustained high motion
        if np.mean(recent) > 0.08:
            return 'MEDIUM', float(np.mean(recent))
        
        return 'LOW', 0.0
    
    def draw_pose_on_frame(self, frame: np.ndarray, pose_info: Dict) -> np.ndarray:
        """Draw pose landmarks on frame (simplified version)."""
        # Return frame as-is for this simplified version
        return frame
    
    def __del__(self):
        """Cleanup resources."""
        pass
