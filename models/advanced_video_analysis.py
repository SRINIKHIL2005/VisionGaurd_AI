"""
Advanced Video Analysis Module

Provides comprehensive video analysis beyond basic object detection:
- Heatmap generation (crowd density visualization)
- Motion detection and optical flow analysis
- Trajectory tracking and analysis
- Crowd counting and density estimation
- Movement statistics (velocity, direction, acceleration)
- Zone-based analysis
- Performance reports

Tech Stack:
- OpenCV - Video processing, optical flow, motion detection
- NumPy - Array operations and calculations
- Scikit-image - Advanced image processing
- Scipy - Statistical analysis

This module implements ML algorithms (not just deep learning):
- Gaussian Mixture Models (GMM) for motion
- Statistical anomaly detection (Z-score)
- Background subtraction (MOG2)
- Optical flow analysis (Farneback)
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Union
from collections import defaultdict, deque
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

try:
    from scipy import stats
    from scipy.ndimage import gaussian_filter
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("⚠️ SciPy not available. Analytics features will be limited.")


class HeatmapGenerator:
    """
    Generates spatial density heatmaps from detection bounding boxes.
    Maps detections to a 2D grid and visualizes using Gaussian blur.
    """
    
    def __init__(self, frame_height: int, frame_width: int, grid_size: int = 32):
        """
        Args:
            frame_height: Video frame height
            frame_width: Video frame width
            grid_size: Heatmap resolution (smaller = higher detail)
        """
        self.frame_height = frame_height
        self.frame_width = frame_width
        self.grid_size = grid_size
        self.heatmap = np.zeros((grid_size, grid_size), dtype=np.float32)
        self.accumulate = True  # Accumulate across frames
        
    def add_detections(self, detections: List[Dict], reset: bool = False):
        """
        Add detection bounding boxes to heatmap.
        
        Args:
            detections: List of detection dicts with 'bbox' key
            reset: Reset heatmap before adding
        """
        if reset:
            self.heatmap = np.zeros((self.grid_size, self.grid_size), dtype=np.float32)
        
        for det in detections:
            if 'bbox' not in det:
                continue
            
            x1, y1, x2, y2 = det['bbox']
            # Center of bounding box
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            
            # Map to grid
            grid_x = int((cx / self.frame_width) * self.grid_size)
            grid_y = int((cy / self.frame_height) * self.grid_size)
            
            # Clamp to grid bounds
            grid_x = np.clip(grid_x, 0, self.grid_size - 1)
            grid_y = np.clip(grid_y, 0, self.grid_size - 1)
            
            # Increment heatmap cell
            self.heatmap[grid_y, grid_x] += 1.0

    def add_motion_mask(self, motion_mask: np.ndarray, weight: float = 0.35, min_motion_ratio: float = 0.03):
        """
        Add activity contribution from a motion mask to the heatmap grid.

        Args:
            motion_mask: Motion mask array (binary or 0-255 intensity)
            weight: Contribution weight relative to detection points
            min_motion_ratio: Minimum normalized motion ratio per cell to count
        """
        if motion_mask is None or motion_mask.size == 0:
            return

        # Convert to 0..1 motion intensity and downsample to heatmap grid.
        motion = motion_mask.astype(np.float32)
        if np.max(motion) > 1.0:
            motion = motion / 255.0

        grid_motion = cv2.resize(motion, (self.grid_size, self.grid_size), interpolation=cv2.INTER_AREA)

        # Keep only meaningful motion to avoid painting the whole map from noise.
        contrib = np.where(grid_motion >= float(min_motion_ratio), grid_motion * float(weight), 0.0)
        self.heatmap += contrib.astype(np.float32)
    
    def get_heatmap(self, normalize: bool = True) -> np.ndarray:
        """
        Get smoothed heatmap.
        
        Args:
            normalize: Normalize to 0-1 range
            
        Returns:
            Smoothed heatmap array
        """
        if SCIPY_AVAILABLE:
            # Apply Gaussian blur for smooth visualization
            smoothed = gaussian_filter(self.heatmap, sigma=1.0)
        else:
            # Fallback: use OpenCV
            smoothed = cv2.GaussianBlur(self.heatmap, (5, 5), 0)
        
        if normalize:
            max_val = np.max(smoothed)
            if max_val > 0:
                smoothed = smoothed / max_val
        
        return smoothed
    
    def visualize(self, base_frame: Optional[np.ndarray] = None, alpha: float = 0.6) -> np.ndarray:
        """
        Overlay heatmap on video frame.
        
        Args:
            base_frame: Base frame to overlay heatmap on (if None, creates new image)
            alpha: Transparency of overlay (0-1)
            
        Returns:
            Frame with heatmap overlay
        """
        heatmap = self.get_heatmap(normalize=True)
        
        # Resize heatmap to frame size
        heatmap_resized = cv2.resize(heatmap, (self.frame_width, self.frame_height))
        
        # Convert to color map (JET)
        heatmap_colored = cv2.applyColorMap(
            (heatmap_resized * 255).astype(np.uint8),
            cv2.COLORMAP_JET
        )
        
        if base_frame is not None:
            # Overlay on frame
            result = cv2.addWeighted(base_frame, 1 - alpha, heatmap_colored, alpha, 0)
        else:
            result = heatmap_colored
        
        return result


class MotionDetector:
    """
    Detects motion using background subtraction and optical flow.
    Implements both MOG2 and optical flow approaches.
    """
    
    def __init__(self, method: str = 'mog2', history: int = 500):
        """
        Args:
            method: 'mog2' or 'opticalflow'
            history: Number of frames for background model
        """
        self.method = method
        self.prev_frame = None
        self.prev_gray = None
        
        if method == 'mog2':
            self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                history=history,
                varThreshold=16,
                detectShadows=True
            )
    
    def detect(self, frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Detect motion in frame.
        
        Returns:
            motion_mask: Binary mask of moving regions
            flow_magnitude: Magnitude of optical flow (if opticalflow method)
        """
        if self.method == 'mog2':
            # Background subtraction
            fg_mask = self.bg_subtractor.apply(frame)
            # Remove shadows
            fg_mask[fg_mask == 127] = 0
            # Apply morphological operations
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            return fg_mask, fg_mask.astype(np.float32)
        
        elif self.method == 'opticalflow':
            # Optical flow
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if self.prev_gray is None:
                self.prev_gray = gray
                return np.zeros_like(gray), np.zeros_like(gray, dtype=np.float32)
            
            flow = cv2.calcOpticalFlowFarneback(
                self.prev_gray, gray,
                None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
            
            # Calculate magnitude
            mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            
            # Create motion mask (threshold magnitude)
            motion_mask = (mag > 0.5).astype(np.uint8) * 255
            
            self.prev_gray = gray
            return motion_mask, mag
        
        return np.zeros_like(frame[:, :, 0], dtype=np.uint8), np.zeros_like(frame[:, :, 0], dtype=np.float32)


class CrowdAnalyzer:
    """
    Estimates crowd density and counts people using spatial analysis.
    Combines detection count with spatial distribution.
    """
    
    def __init__(self, frame_height: int, frame_width: int, grid_size: int = 8):
        """
        Args:
            frame_height: Video frame height
            frame_width: Video frame width
            grid_size: Grid for density calculation
        """
        self.frame_height = frame_height
        self.frame_width = frame_width
        self.grid_size = grid_size
        self.grid_width = frame_width // grid_size
        self.grid_height = frame_height // grid_size
    
    def analyze_density(self, detections: List[Dict]) -> Dict:
        """
        Analyze crowd density from detections.
        
        Args:
            detections: List of person detections with bboxes
            
        Returns:
            Density analysis dict
        """
        person_count = len([d for d in detections if d.get('class', '').lower() == 'person'])
        
        # Calculate spatial distribution
        grid_counts = np.zeros((self.grid_size, self.grid_size), dtype=int)
        
        for det in detections:
            if det.get('class', '').lower() != 'person':
                continue
            
            x1, y1, x2, y2 = det['bbox']
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            
            grid_x = min(cx // self.grid_width, self.grid_size - 1)
            grid_y = min(cy // self.grid_height, self.grid_size - 1)
            
            grid_counts[grid_y, grid_x] += 1
        
        # Calculate density metrics
        occupied_cells = np.count_nonzero(grid_counts)
        max_density = np.max(grid_counts) if person_count > 0 else 0
        avg_density = np.mean(grid_counts[grid_counts > 0]) if occupied_cells > 0 else 0
        
        # Density level classification
        if person_count < 3:
            density_level = "LOW"
        elif person_count < 10:
            density_level = "MEDIUM"
        elif person_count < 25:
            density_level = "HIGH"
        else:
            density_level = "CRITICAL"
        
        return {
            'person_count': person_count,
            'density_level': density_level,
            'occupied_cells': occupied_cells,
            'max_density_in_cell': max_density,
            'avg_density_per_occupied_cell': round(avg_density, 2),
            'grid_distribution': grid_counts.tolist()
        }


class LoiteringDetector:
    """
    Detects people who stay in the same area for too long (loitering).
    Uses tracking and position history.
    """
    
    def __init__(self, min_duration: float = 5.0, position_threshold: float = 50):
        """
        Args:
            min_duration: Time in seconds to consider as loitering
            position_threshold: Pixel distance threshold for "same position"
        """
        self.min_duration = min_duration
        self.position_threshold = position_threshold
        self.tracks = {}  # track_id -> deque of (frame, cx, cy)
        self.frame_rate = 30  # Assume 30 fps, will be updated
        self.reported_loitering = set()  # Track IDs already reported as loitering
        self.reported_events = []  # list of (frame, x, y) for spatial dedupe across ID churn
    
    def update(self, detections: List[Dict], frame_number: int = 0):
        """
        Update tracking for loitering detection.
        
        Args:
            detections: List of detections with track_id
            frame_number: Current frame number
        """
        seen_ids = set()
        
        for det in detections:
            track_id = det.get('track_id')
            if track_id is None:
                continue
            
            seen_ids.add(track_id)
            
            if track_id not in self.tracks:
                self.tracks[track_id] = deque(maxlen=self.frame_rate * 30)  # 30 sec history
            
            x1, y1, x2, y2 = det['bbox']
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            
            self.tracks[track_id].append((frame_number, cx, cy))
        
        # Remove tracks not seen recently
        for track_id in list(self.tracks.keys()):
            if track_id not in seen_ids and len(self.tracks[track_id]) > 0:
                # Person left, clear their report status
                self.reported_loitering.discard(track_id)
    
    def detect_loitering(self) -> List[Dict]:
        """
        Detect loitering persons (returns only NEW loitering detections).
        
        Returns:
            List of NEW loitering detections with duration
        """
        loitering_list = []
        
        for track_id, history in self.tracks.items():
            # Skip if already reported
            if track_id in self.reported_loitering:
                continue
                
            if len(history) < 2:
                continue
            
            first_frame, first_x, first_y = history[0]
            last_frame, last_x, last_y = history[-1]
            
            # Calculate movement distance
            distance = np.sqrt((last_x - first_x) ** 2 + (last_y - first_y) ** 2)
            
            # Calculate duration
            frame_diff = last_frame - first_frame
            duration = frame_diff / self.frame_rate if self.frame_rate > 0 else 0
            
            # Check if loitering - report only first trigger per track in a video.
            if distance < self.position_threshold and duration >= self.min_duration:
                # Suppress duplicate incidents near the same location in a short time window,
                # which happens when tracker IDs fragment for the same person.
                duplicate = False
                spatial_window = self.position_threshold * 1.5
                temporal_window = int(max(self.frame_rate * self.min_duration * 4, self.frame_rate * 20))
                for evt_frame, evt_x, evt_y in self.reported_events:
                    evt_dist = np.sqrt((last_x - evt_x) ** 2 + (last_y - evt_y) ** 2)
                    frame_gap = abs(last_frame - evt_frame)
                    if evt_dist <= spatial_window and frame_gap <= temporal_window:
                        duplicate = True
                        break

                if duplicate:
                    continue

                self.reported_loitering.add(track_id)
                self.reported_events.append((last_frame, last_x, last_y))
                loitering_list.append({
                    'track_id': track_id,
                    'duration_seconds': round(duration, 2),
                    'position': (round(last_x), round(last_y)),
                    'movement_distance': round(distance, 2),
                    'position_threshold': self.position_threshold,
                    'min_duration': self.min_duration,
                    'severity': 'CRITICAL' if duration > 30 else ('HIGH' if duration > 15 else 'MEDIUM'),
                    'detection_timestamp': last_frame
                })

        return loitering_list


class TrajectoryAnalyzer:
    """
    Analyzes movement trajectories and patterns.
    Detects unusual movement patterns and calculates movement statistics.
    """
    
    def __init__(self, frame_height: int, frame_width: int, frame_rate: int = 30):
        """
        Args:
            frame_height: Video frame height
            frame_width: Video frame width
        """
        self.frame_height = frame_height
        self.frame_width = frame_width
        self.frame_rate = max(1, int(frame_rate))
        self.tracks = {}  # track_id -> list of (x, y, timestamp)
        self.track_labels = {}  # track_id -> class label
        self.reported_unusual = {}  # track_id -> last_report_frame

    def reset(self):
        """Reset per-video trajectory state to avoid cross-video carry-over."""
        self.tracks = {}
        self.track_labels = {}
        self.reported_unusual = {}
    
    def update_track(self, track_id: int, bbox: Tuple, frame_number: int, object_class: Optional[str] = None):
        """
        Update track with new detection.
        
        Args:
            track_id: Track identifier
            bbox: Bounding box (x1, y1, x2, y2)
            frame_number: Frame number
        """
        if track_id not in self.tracks:
            self.tracks[track_id] = []

        if object_class:
            self.track_labels[track_id] = str(object_class)
        
        x1, y1, x2, y2 = bbox
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        
        self.tracks[track_id].append({
            'frame': frame_number,
            'x': cx,
            'y': cy,
            'bbox': bbox
        })
        
        # Debug: log when trajectory tracking starts
        if len(self.tracks[track_id]) == 1:
            label = self.track_labels.get(track_id, 'object')
            print(f"   [Trajectory] Started tracking {label} {track_id}")
    
    def calculate_statistics(self, track_id: int) -> Optional[Dict]:
        """
        Calculate movement statistics for a track.
        
        Returns:
            Statistics dict with velocity, direction, etc.
        """
        if track_id not in self.tracks or len(self.tracks[track_id]) < 2:
            return None
        
        track = self.tracks[track_id]
        
        # Calculate velocity
        positions = [(p['x'], p['y']) for p in track]
        distances = []
        
        for i in range(1, len(positions)):
            x1, y1 = positions[i - 1]
            x2, y2 = positions[i]
            dist = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            distances.append(dist)
        
        avg_velocity = np.mean(distances) if distances else 0
        max_velocity = np.max(distances) if distances else 0
        
        # Calculate direction (start to end)
        x_start, y_start = positions[0]
        x_end, y_end = positions[-1]
        
        if (x_end - x_start) != 0:
            angle = np.arctan2(y_end - y_start, x_end - x_start)
            angle_deg = np.degrees(angle)
        else:
            angle_deg = 0
        
        # Calculate total distance
        total_distance = sum(distances)
        
        return {
            'avg_velocity': round(avg_velocity, 2),
            'max_velocity': round(max_velocity, 2),
            'total_distance': round(total_distance, 2),
            'direction_angle': round(angle_deg, 2),
            'frames_tracked': len(track),
            'path_efficiency': round(total_distance / np.sqrt((x_end - x_start) ** 2 + (y_end - y_start) ** 2), 2) if np.sqrt((x_end - x_start) ** 2 + (y_end - y_start) ** 2) > 0 else 0
        }
    
    def detect_unusual_movement(self) -> List[Dict]:
        """
        Detect unusual movement patterns using robust statistics over track velocity.
        
        Returns:
            List of unusual movement detections
        """
        unusual = []

        for track_id, track in self.tracks.items():
            if len(track) < 8:
                continue

            track_span_sec = (track[-1]['frame'] - track[0]['frame']) / self.frame_rate
            if track_span_sec < 6.0:
                continue

            speeds_per_second = []
            for i in range(1, len(track)):
                p1 = track[i - 1]
                p2 = track[i]
                dx = p2['x'] - p1['x']
                dy = p2['y'] - p1['y']
                frame_delta = max(1, p2['frame'] - p1['frame'])
                speed_per_frame = float(np.sqrt(dx * dx + dy * dy) / frame_delta)
                speeds_per_second.append(speed_per_frame * self.frame_rate)

            if len(speeds_per_second) < 5:
                continue

            baseline = float(np.median(speeds_per_second[:-1]))
            mad = float(np.median(np.abs(np.array(speeds_per_second[:-1]) - baseline)))
            latest_speed = float(speeds_per_second[-1])
            max_speed = float(np.max(speeds_per_second))

            robust_score = 0.0
            if mad > 1e-6:
                robust_score = (latest_speed - baseline) / (1.4826 * mad)

            latest_frame = int(track[-1]['frame'])
            cooldown_frames = self.frame_rate * 20
            last_report_frame = self.reported_unusual.get(track_id, -cooldown_frames)
            if (latest_frame - last_report_frame) < cooldown_frames:
                continue

            # Adaptive trigger for sparse sampling (high frame_skip) and regular streams.
            # We require a meaningful absolute speed plus a strong relative jump.
            absolute_floor = max(30.0, baseline * 2.5)
            has_large_jump = (latest_speed > absolute_floor and robust_score > 3.5)
            has_sustained_spike = (max_speed > max(45.0, baseline * 4.0))

            if has_large_jump or has_sustained_spike:
                self.reported_unusual[track_id] = latest_frame
                unusual.append({
                    'track_id': track_id,
                    'class': self.track_labels.get(track_id, 'unknown'),
                    'velocity': round(max_speed, 2),
                    'z_score': round(robust_score, 2),
                    'anomaly_type': 'RAPID_MOVEMENT',
                    'severity': 'HIGH' if (max_speed > 70.0 or robust_score > 5.0) else 'MEDIUM',
                    'latest_speed': round(latest_speed, 2),
                    'baseline_speed': round(baseline, 2),
                    'frame': latest_frame,
                })

        return unusual


class BehavioralAnomalyDetector:
    """
    Detects behavioral anomalies using ML algorithms (not deep learning).
    Uses Isolation Forest and statistical methods.
    """
    
    def __init__(self):
        """Initialize anomaly detector"""
        self.frame_history = deque(maxlen=300)  # 10 seconds at 30 fps
    
    def extract_features(self, detections: List[Dict], motion_magnitude: float) -> Optional[np.ndarray]:
        """
        Extract features for anomaly detection.
        
        Args:
            detections: List of detections
            motion_magnitude: Average motion magnitude
            
        Returns:
            Feature vector
        """
        person_count = len([d for d in detections if d.get('class', '').lower() == 'person'])
        weapon_count = len([d for d in detections if 'weapon' in d.get('class', '').lower()])
        
        # Calculate bounding box areas
        areas = []
        for det in detections:
            x1, y1, x2, y2 = det.get('bbox', [0, 0, 0, 0])
            area = (x2 - x1) * (y2 - y1)
            areas.append(area)
        
        avg_area = np.mean(areas) if areas else 0
        
        features = np.array([
            person_count,
            weapon_count,
            motion_magnitude,
            avg_area / 100000 if avg_area > 0 else 0,  # Normalized
        ], dtype=np.float32)
        
        return features
    
    def detect_anomalies(self) -> List[Dict]:
        """
        Detect behavioral anomalies from frame history.
        
        Returns:
            List of anomalies
        """
        if len(self.frame_history) < 10:
            return []
        
        anomalies = []
        
        # Convert history to feature matrix
        features = np.array([f for f in self.frame_history if isinstance(f, np.ndarray)])
        
        if len(features) < 10 or not SCIPY_AVAILABLE:
            return anomalies
        
        # Statistical anomaly detection - Z-score on each feature
        try:
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            features_scaled = scaler.fit_transform(features)
            
            # Get last frame
            last_frame = features_scaled[-1]
            z_scores = np.abs(last_frame)
            
            # Check each feature
            feature_names = ['person_count', 'weapon_count', 'motion', 'avg_object_size']
            
            for i, (z_score, name) in enumerate(zip(z_scores, feature_names)):
                if z_score > 2.5:  # Threshold for anomaly
                    anomalies.append({
                        'anomaly_type': name.upper(),
                        'z_score': round(float(z_score), 2),
                        'severity': 'HIGH' if z_score > 3.5 else 'MEDIUM',
                        'description': f'Unusual {name}: Z-score={z_score:.2f}'
                    })
        except ImportError:
            # Fallback: simple threshold-based detection
            last_frame = features[-1]
            history_mean = np.mean(features[:-1], axis=0)
            history_std = np.std(features[:-1], axis=0)
            
            for i, (val, mean, std) in enumerate(zip(last_frame, history_mean, history_std)):
                if std > 0:
                    z_score = abs((val - mean) / std)
                    if z_score > 2.0:
                        feature_names = ['person_count', 'weapon_count', 'motion', 'avg_object_size']
                        anomalies.append({
                            'anomaly_type': feature_names[i].upper(),
                            'z_score': round(float(z_score), 2),
                            'severity': 'MEDIUM'
                        })
        
        return anomalies
    
    def add_frame(self, features: np.ndarray):
        """Add frame features to history"""
        self.frame_history.append(features)
