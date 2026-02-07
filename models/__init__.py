"""
Initialize models package
"""

from .deepfake.deepfake_detector import DeepfakeDetector
from .face_recognition.face_recognizer import FaceRecognizer
from .object_detection.yolo_detector import YOLODetector

__all__ = ['DeepfakeDetector', 'FaceRecognizer', 'YOLODetector']
