"""
Face Recognition Module

This module uses InsightFace (ArcFace) for state-of-the-art face recognition.
It detects faces, extracts embeddings, and matches against a known database.

Tech Stack:
- InsightFace - ArcFace model for face embeddings
- OpenCV - Face detection and preprocessing
- NumPy - Vector operations

Input:
- RGB image (numpy array or PIL Image)
- Face database (stored embeddings)

Output:
- face_detected: bool
- identity: str (name or "Unknown")
- similarity_score: float (0 to 1)
- confidence: float (percentage)
"""

import cv2
import numpy as np
from typing import Dict, List, Union, Tuple, Optional
from PIL import Image
import os
import pickle
import warnings

warnings.filterwarnings('ignore')

try:
    from insightface.app import FaceAnalysis
    from insightface.data import get_image as ins_get_image
    INSIGHTFACE_AVAILABLE = True
except ImportError as e:
    INSIGHTFACE_AVAILABLE = False
    print(f"⚠️ InsightFace import error: {e}")
    print("💡 Install with: pip install insightface onnxruntime")
except Exception as e:
    INSIGHTFACE_AVAILABLE = False
    print(f"⚠️ InsightFace error: {e}")
    print("💡 Try: pip install --upgrade insightface onnxruntime")


class FaceRecognizer:
    """
    Face recognition using InsightFace ArcFace model.
    Handles face detection, embedding extraction, and identity matching.
    """
    
    def __init__(
        self, 
        model_name: str = 'buffalo_l',
        database_path: str = './data/face_database',
        similarity_threshold: float = 0.5,
        device: str = 'auto'
    ):
        """
        Initialize face recognizer with ArcFace model.
        
        Args:
            model_name: InsightFace model name ('buffalo_l', 'buffalo_s', 'antelopev2')
            database_path: Path to store/load face embeddings database
            similarity_threshold: Minimum similarity score for match (0-1)
            device: 'auto', 'cuda', or 'cpu'
        """
        self.database_path = database_path
        self.similarity_threshold = similarity_threshold
        self.face_database = {}
        
        # Determine device
        if device == 'auto':
            import torch
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
        
        print(f"🔧 Initializing Face Recognizer on {self.device}...")
        
        if not INSIGHTFACE_AVAILABLE:
            print("❌ InsightFace not installed. Using fallback detector.")
            self._init_fallback()
            return
        
        try:
            # Initialize InsightFace
            self.app = FaceAnalysis(
                name=model_name,
                providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
            )
            self.app.prepare(ctx_id=0 if self.device == 'cuda' else -1, det_size=(640, 640))
            
            print(f"✅ InsightFace loaded: {model_name}")
            
            # Load existing face database
            self._load_database()
            
        except Exception as e:
            print(f"⚠️ Error initializing InsightFace: {e}")
            self._init_fallback()
    
    def _init_fallback(self):
        """Fallback to OpenCV Haar Cascade if InsightFace unavailable"""
        print("💡 Using OpenCV Haar Cascade as fallback...")
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        self.app = None
    
    def _load_database(self):
        """Load face embeddings database from disk"""
        os.makedirs(self.database_path, exist_ok=True)
        db_file = os.path.join(self.database_path, 'face_embeddings.pkl')
        
        if os.path.exists(db_file):
            with open(db_file, 'rb') as f:
                loaded_data = pickle.load(f)
                
            # Handle migration from old format (embedding only) to new format (with metadata)
            if loaded_data and isinstance(list(loaded_data.values())[0], np.ndarray):
                # Old format: {name: embedding} -> Migrate to new format
                print("📦 Migrating database to new format with metadata...")
                from datetime import datetime
                migration_date = datetime.now().isoformat()
                self.face_database = {}
                for name, embedding in loaded_data.items():
                    self.face_database[name] = {
                        'embedding': embedding,
                        'metadata': {
                            'added_date': migration_date,  # Use current time as migration timestamp
                            'photo_path': None,
                            'approved_by': 'Legacy (Migrated)',
                            'camera_location': 'Pre-migration data'
                        }
                    }
                self._save_database()  # Save migrated format
                print(f"✅ Migrated {len(self.face_database)} identities with timestamp {migration_date}")
            else:
                self.face_database = loaded_data
                
            print(f"📂 Loaded {len(self.face_database)} identities from database")
        else:
            print("📂 No existing database found. Starting fresh.")
    
    def _save_database(self):
        """Save face embeddings database to disk"""
        os.makedirs(self.database_path, exist_ok=True)
        db_file = os.path.join(self.database_path, 'face_embeddings.pkl')
        
        with open(db_file, 'wb') as f:
            pickle.dump(self.face_database, f)
        print(f"💾 Database saved with {len(self.face_database)} identities")
    
    def preprocess_image(self, image: Union[np.ndarray, Image.Image]) -> np.ndarray:
        """
        Convert image to format required by InsightFace (BGR numpy array).
        
        Args:
            image: Input image (numpy array or PIL Image)
            
        Returns:
            BGR numpy array
        """
        if isinstance(image, Image.Image):
            image = np.array(image)
        
        # Convert RGB to BGR if needed
        if len(image.shape) == 3 and image.shape[2] == 3:
            # Assume RGB, convert to BGR
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        return image
    
    def detect_faces(self, image: Union[np.ndarray, Image.Image]) -> List[Dict]:
        """
        Detect all faces in the image and extract embeddings.
        
        Args:
            image: Input image
            
        Returns:
            List of face dictionaries with bbox, embedding, landmarks
        """
        image_bgr = self.preprocess_image(image)
        
        if self.app is not None:
            # Use InsightFace
            faces = self.app.get(image_bgr)
            
            face_list = []
            for face in faces:
                face_dict = {
                    'bbox': face.bbox.astype(int).tolist(),  # [x1, y1, x2, y2]
                    'embedding': face.normed_embedding,
                    'landmarks': face.kps.astype(int).tolist() if hasattr(face, 'kps') else None,
                    'det_score': float(face.det_score)
                }
                face_list.append(face_dict)
            
            return face_list
        else:
            # Fallback: OpenCV Haar Cascade
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
            
            face_list = []
            for (x, y, w, h) in faces:
                face_dict = {
                    'bbox': [x, y, x+w, y+h],
                    'embedding': None,  # No embedding in fallback mode
                    'landmarks': None,
                    'det_score': 1.0
                }
                face_list.append(face_dict)
            
            return face_list
    
    def add_face(self, name: str, embedding: np.ndarray, metadata: dict = None) -> bool:
        """
        Add a face embedding directly to the database with metadata.
        Used by Telegram bot for approved unknown faces.
        
        Args:
            name: Person's name/identifier
            embedding: Pre-computed face embedding
            metadata: Optional metadata dict with:
                - photo_path: Path to saved photo
                - added_date: ISO timestamp when added
                - approved_by: Who approved (Telegram user/chat ID)
                - camera_location: Where detected
            
        Returns:
            Success status
        """
        from datetime import datetime
        
        # Default metadata if not provided
        if metadata is None:
            metadata = {
                'added_date': datetime.now().isoformat(),
                'photo_path': None,
                'approved_by': 'Manual',
                'camera_location': 'Unknown'
            }
        
        self.face_database[name] = {
            'embedding': embedding,
            'metadata': metadata
        }
        self._save_database()
        print(f"✅ Added {name} to database with metadata")
        return True
    
    def add_identity(self, image: Union[np.ndarray, Image.Image], name: str) -> bool:
        """
        Add a new identity to the face database.
        
        Args:
            image: Face image
            name: Person's name/identifier
            
        Returns:
            Success status
        """
        print(f"🔍 Attempting to add identity: {name}")
        
        # Check if InsightFace is available
        if self.app is None:
            print("❌ Cannot add identity: InsightFace not available")
            print("💡 Install InsightFace: pip install insightface onnxruntime")
            return False
        
        faces = self.detect_faces(image)
        
        if len(faces) == 0:
            print(f"❌ No face detected for {name}")
            print("💡 Try uploading a clearer face image with good lighting")
            return False
        
        if len(faces) > 1:
            print(f"⚠️ Multiple faces detected ({len(faces)} faces). Using the largest face.")
        
        # Use the first (or largest) face
        face = faces[0]
        
        if face['embedding'] is None:
            print("❌ Cannot add identity: No embedding generated")
            print("💡 This usually means InsightFace is not properly initialized")
            return False
        
        # Store embedding with metadata (for manual additions via UI)
        from datetime import datetime
        self.face_database[name] = {
            'embedding': face['embedding'],
            'metadata': {
                'added_date': datetime.now().isoformat(),
                'photo_path': None,  # Could save uploaded image here
                'approved_by': 'Manual Upload',
                'camera_location': 'N/A'
            }
        }
        self._save_database()
        
        print(f"✅ Successfully added {name} to database")
        return True
    
    def find_match(self, embedding: np.ndarray) -> Tuple[str, float]:
        """
        Find the best match for a face embedding in the database.
        
        Args:
            embedding: Face embedding vector
            
        Returns:
            (identity, similarity_score)
        """
        if len(self.face_database) == 0:
            return "Unknown", 0.0
        
        best_match = "Unknown"
        best_score = 0.0
        
        for name, face_data in self.face_database.items():
            # Handle both old format (embedding only) and new format (with metadata)
            if isinstance(face_data, dict):
                stored_embedding = face_data['embedding']
            else:
                stored_embedding = face_data  # Old format
            
            # Cosine similarity
            similarity = np.dot(embedding, stored_embedding)
            
            if similarity > best_score:
                best_score = similarity
                best_match = name
        
        # Check threshold
        if best_score < self.similarity_threshold:
            return "Unknown", best_score
        
        return best_match, best_score
    
    def recognize(self, image: Union[np.ndarray, Image.Image]) -> Dict:
        """
        Recognize faces in the image and match against database.
        
        Args:
            image: Input image
            
        Returns:
            Dictionary with recognition results
        """
        faces = self.detect_faces(image)
        
        if len(faces) == 0:
            return {
                'face_detected': False,
                'identity': 'No Face',
                'similarity_score': 0.0,
                'confidence': 0.0,
                'num_faces': 0,
                'faces': [],
                'unknown_faces': []  # New field for unknown faces
            }
        
        # Process all detected faces
        results = []
        unknown_faces = []  # Track unknown faces separately
        
        for face in faces:
            if face['embedding'] is not None:
                identity, similarity = self.find_match(face['embedding'])
                confidence = similarity * 100
                
                # Track unknown faces
                if identity == "Unknown":
                    # Convert bbox from [x1, y1, x2, y2] to [x, y, w, h]
                    x1, y1, x2, y2 = face['bbox']
                    bbox_xywh = [x1, y1, x2-x1, y2-y1]
                    
                    unknown_faces.append({
                        'embedding': face['embedding'],
                        'bbox': bbox_xywh,  # (x, y, w, h) format
                        'det_score': face['det_score']
                    })
            else:
                identity = "Unknown"
                similarity = 0.0
                confidence = 0.0
            
            results.append({
                'identity': identity,
                'similarity_score': round(similarity, 4),
                'confidence': round(confidence, 2),
                'bbox': face['bbox'],
                'landmarks': face['landmarks']
            })
        
        # Return primary result (first/largest face)
        primary = results[0]
        
        return {
            'face_detected': True,
            'identity': primary['identity'],
            'similarity_score': primary['similarity_score'],
            'confidence': primary['confidence'],
            'num_faces': len(faces),
            'faces': results,
            'unknown_faces': unknown_faces  # List of unknown face data
        }
    
    def remove_identity(self, name: str) -> bool:
        """Remove an identity from the database"""
        if name in self.face_database:
            del self.face_database[name]
            self._save_database()
            print(f"🗑️ Removed {name} from database")
            return True
        return False
    
    def list_identities(self, detailed: bool = False) -> Union[List[str], List[Dict]]:
        """
        Get list of all identities in database.
        
        Args:
            detailed: If True, return full metadata for each identity
            
        Returns:
            List of names or list of dicts with full info
        """
        if not detailed:
            return list(self.face_database.keys())
        
        # Return detailed information
        result = []
        from datetime import datetime
        for name, face_data in self.face_database.items():
            if isinstance(face_data, dict):
                metadata = face_data.get('metadata', {})
                result.append({
                    'name': name,
                    'added_date': metadata.get('added_date', datetime.now().isoformat()),
                    'photo_path': metadata.get('photo_path'),
                    'approved_by': metadata.get('approved_by', 'Unknown'),
                    'camera_location': metadata.get('camera_location', 'Unknown'),
                    'telegram_user_id': metadata.get('telegram_user_id'),
                    'telegram_username': metadata.get('telegram_username'),
                    'telegram_first_name': metadata.get('telegram_first_name'),
                    'telegram_last_name': metadata.get('telegram_last_name'),
                    'approval_timestamp': metadata.get('approval_timestamp')
                })
            else:
                # Old format fallback - shouldn't happen after migration
                result.append({
                    'name': name,
                    'added_date': datetime.now().isoformat(),
                    'photo_path': None,
                    'approved_by': 'Legacy (No metadata)',
                    'camera_location': 'Unknown'
                })
        return result


# Convenience function
def recognize_face(image: Union[np.ndarray, Image.Image]) -> Dict:
    """
    Quick function to recognize a face without instantiating class.
    
    Args:
        image: Input image
        
    Returns:
        Recognition results
    """
    recognizer = FaceRecognizer()
    return recognizer.recognize(image)


if __name__ == "__main__":
    # Test the face recognizer
    print("\n🧪 Testing Face Recognizer...\n")
    
    # Create test image
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Initialize recognizer
    recognizer = FaceRecognizer()
    
    # Run recognition
    result = recognizer.recognize(test_image)
    
    print("\n📊 Recognition Result:")
    print(f"   Face Detected: {result['face_detected']}")
    print(f"   Identity: {result['identity']}")
    print(f"   Similarity: {result['similarity_score']}")
    print(f"   Confidence: {result['confidence']}%")
    print(f"   Num Faces: {result['num_faces']}")
    print("\n✅ Face Recognizer initialized successfully!")
