"""
MongoDB Manager for VisionGuard AI

Handles all database operations for:
- Face database (identities with embeddings)
- Detection history
- Telegram interactions
- Analysis history
- User actions
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Optional, Any
import pickle
import base64


class MongoDBManager:
    """MongoDB manager for VisionGuard AI"""
    
    def __init__(self, connection_string: str, database_name: str = "visionguard_ai"):
        """
        Initialize MongoDB connection.
        
        Args:
            connection_string: MongoDB connection string
            database_name: Database name to use
        """
        self.connection_string = connection_string
        self.database_name = database_name
        self.client = None
        self.db = None
        self._connect()
    
    def _connect(self):
        """Establish MongoDB connection and setup collections"""
        try:
            self.client = MongoClient(self.connection_string, serverSelectionTimeoutMS=5000)
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            
            # Create collections and indexes
            self._setup_collections()
            
            print(f"✅ Connected to MongoDB: {self.database_name}")
        except ConnectionFailure as e:
            print(f"❌ Failed to connect to MongoDB: {e}")
            raise
    
    def _setup_collections(self):
        """Create collections and indexes"""
        # Face Database Collection
        if 'face_database' not in self.db.list_collection_names():
            self.db.create_collection('face_database')
        self.db.face_database.create_index([('name', ASCENDING)], unique=True)
        self.db.face_database.create_index([('added_date', DESCENDING)])
        
        # Detection History Collection
        if 'detection_history' not in self.db.list_collection_names():
            self.db.create_collection('detection_history')
        self.db.detection_history.create_index([('timestamp', DESCENDING)])
        self.db.detection_history.create_index([('camera_location', ASCENDING)])
        self.db.detection_history.create_index([('detected_identities', ASCENDING)])
        
        # Telegram Interactions Collection
        if 'telegram_interactions' not in self.db.list_collection_names():
            self.db.create_collection('telegram_interactions')
        self.db.telegram_interactions.create_index([('timestamp', DESCENDING)])
        self.db.telegram_interactions.create_index([('action_type', ASCENDING)])
        self.db.telegram_interactions.create_index([('detection_id', ASCENDING)])
        
        # Analysis History Collection
        if 'analysis_history' not in self.db.list_collection_names():
            self.db.create_collection('analysis_history')
        self.db.analysis_history.create_index([('timestamp', DESCENDING)])
        self.db.analysis_history.create_index([('analysis_type', ASCENDING)])
        self.db.analysis_history.create_index([('risk_level', ASCENDING)])
        
        # User Actions Collection
        if 'user_actions' not in self.db.list_collection_names():
            self.db.create_collection('user_actions')
        self.db.user_actions.create_index([('timestamp', DESCENDING)])
        self.db.user_actions.create_index([('action_type', ASCENDING)])
    
    # ===== Face Database Operations =====
    
    def add_face(self, name: str, embedding: np.ndarray, metadata: Dict) -> bool:
        """
        Add face to database.
        
        Args:
            name: Person's name
            embedding: Face embedding (numpy array)
            metadata: Additional metadata (photo_path, added_date, etc.)
        
        Returns:
            Success status
        """
        try:
            # Convert numpy array to base64 for storage
            embedding_bytes = pickle.dumps(embedding)
            embedding_b64 = base64.b64encode(embedding_bytes).decode('utf-8')
            
            face_doc = {
                'name': name,
                'embedding': embedding_b64,
                'metadata': metadata,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            self.db.face_database.insert_one(face_doc)
            print(f"✅ Added face to MongoDB: {name}")
            return True
        except DuplicateKeyError:
            print(f"⚠️ Face already exists: {name}")
            return False
        except Exception as e:
            print(f"❌ Error adding face: {e}")
            return False
    
    def get_face(self, name: str) -> Optional[Dict]:
        """Get face by name"""
        doc = self.db.face_database.find_one({'name': name})
        if doc:
            # Convert embedding back to numpy array
            embedding_bytes = base64.b64decode(doc['embedding'])
            doc['embedding'] = pickle.loads(embedding_bytes)
        return doc
    
    def get_all_faces(self) -> Dict[str, Dict]:
        """
        Get all faces from database.
        
        Returns:
            Dictionary {name: {embedding, metadata}}
        """
        faces = {}
        for doc in self.db.face_database.find():
            # Convert embedding back to numpy array
            embedding_bytes = base64.b64decode(doc['embedding'])
            embedding = pickle.loads(embedding_bytes)
            
            faces[doc['name']] = {
                'embedding': embedding,
                'metadata': doc['metadata']
            }
        return faces
    
    def remove_face(self, name: str) -> bool:
        """Remove face from database"""
        result = self.db.face_database.delete_one({'name': name})
        return result.deleted_count > 0
    
    def list_identities(self, detailed: bool = False) -> List:
        """List all identities"""
        if detailed:
            identities = []
            for doc in self.db.face_database.find().sort('created_at', DESCENDING):
                identity = {
                    'name': doc['name'],
                    'added_date': doc['metadata'].get('added_date', 'Unknown'),
                    'approved_by': doc['metadata'].get('approved_by', 'Unknown'),
                    'camera_location': doc['metadata'].get('camera_location', 'Unknown'),
                    'photo_path': doc['metadata'].get('photo_path'),
                    'telegram_user_id': doc['metadata'].get('telegram_user_id'),
                    'telegram_username': doc['metadata'].get('telegram_username'),
                    'telegram_first_name': doc['metadata'].get('telegram_first_name'),
                    'telegram_last_name': doc['metadata'].get('telegram_last_name'),
                }
                identities.append(identity)
            return identities
        else:
            return [doc['name'] for doc in self.db.face_database.find()]
    
    # ===== Detection History Operations =====
    
    def log_detection(self, detection_data: Dict) -> str:
        """
        Log detection event.
        
        Args:
            detection_data: Detection information
            
        Returns:
            Detection ID
        """
        doc = {
            'timestamp': datetime.utcnow(),
            'camera_location': detection_data.get('camera_location', 'Unknown'),
            'detected_identities': detection_data.get('detected_identities', []),
            'unknown_faces': detection_data.get('unknown_faces', 0),
            'deepfake_detected': detection_data.get('deepfake_detected', False),
            'deepfake_confidence': detection_data.get('deepfake_confidence', 0.0),
            'suspicious_objects': detection_data.get('suspicious_objects', []),
            'risk_level': detection_data.get('risk_level', 'low'),
            'risk_score': detection_data.get('risk_score', 0.0),
            'image_path': detection_data.get('image_path'),
        }
        result = self.db.detection_history.insert_one(doc)
        return str(result.inserted_id)
    
    def get_detection_history(self, limit: int = 100, camera_location: Optional[str] = None,
                              start_date: Optional[datetime] = None) -> List[Dict]:
        """Get detection history with filters"""
        query = {}
        if camera_location:
            query['camera_location'] = camera_location
        if start_date:
            query['timestamp'] = {'$gte': start_date}
        
        return list(self.db.detection_history.find(query).sort('timestamp', DESCENDING).limit(limit))
    
    # ===== Telegram Interactions =====
    
    def log_telegram_interaction(self, interaction_data: Dict) -> str:
        """
        Log Telegram bot interaction.
        
        Args:
            interaction_data: Interaction details
            
        Returns:
            Interaction ID
        """
        doc = {
            'timestamp': datetime.utcnow(),
            'action_type': interaction_data.get('action_type'),  # notification, approval, rejection
            'detection_id': interaction_data.get('detection_id'),
            'user_id': interaction_data.get('user_id'),
            'username': interaction_data.get('username'),
            'first_name': interaction_data.get('first_name'),
            'last_name': interaction_data.get('last_name'),
            'message': interaction_data.get('message'),
            'response': interaction_data.get('response'),
            'approved_name': interaction_data.get('approved_name'),
        }
        result = self.db.telegram_interactions.insert_one(doc)
        return str(result.inserted_id)
    
    def get_telegram_history(self, limit: int = 100) -> List[Dict]:
        """Get Telegram interaction history"""
        return list(self.db.telegram_interactions.find().sort('timestamp', DESCENDING).limit(limit))
    
    # ===== Analysis History =====
    
    def log_analysis(self, analysis_data: Dict) -> str:
        """
        Log complete analysis result.
        
        Args:
            analysis_data: Full analysis result
            
        Returns:
            Analysis ID
        """
        doc = {
            'timestamp': datetime.utcnow(),
            'analysis_type': analysis_data.get('analysis_type', 'image'),  # image, video, live
            'deepfake_result': analysis_data.get('deepfake_result'),
            'face_recognition_result': analysis_data.get('face_recognition_result'),
            'object_detection_result': analysis_data.get('object_detection_result'),
            'risk_level': analysis_data.get('risk_level'),
            'risk_score': analysis_data.get('risk_score'),
            'processing_time': analysis_data.get('processing_time'),
            'source_path': analysis_data.get('source_path'),
        }
        result = self.db.analysis_history.insert_one(doc)
        return str(result.inserted_id)
    
    def get_analysis_history(self, limit: int = 100, analysis_type: Optional[str] = None) -> List[Dict]:
        """Get analysis history"""
        query = {}
        if analysis_type:
            query['analysis_type'] = analysis_type
        
        return list(self.db.analysis_history.find(query).sort('timestamp', DESCENDING).limit(limit))
    
    # ===== User Actions =====
    
    def log_user_action(self, action_data: Dict) -> str:
        """
        Log user action.
        
        Args:
            action_data: Action details
            
        Returns:
            Action ID
        """
        doc = {
            'timestamp': datetime.utcnow(),
            'action_type': action_data.get('action_type'),  # add_face, remove_face, upload_image, etc.
            'user_identifier': action_data.get('user_identifier'),
            'details': action_data.get('details'),
            'ip_address': action_data.get('ip_address'),
        }
        result = self.db.user_actions.insert_one(doc)
        return str(result.inserted_id)
    
    # ===== Statistics =====
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        return {
            'total_faces': self.db.face_database.count_documents({}),
            'total_detections': self.db.detection_history.count_documents({}),
            'total_telegram_interactions': self.db.telegram_interactions.count_documents({}),
            'total_analyses': self.db.analysis_history.count_documents({}),
            'total_user_actions': self.db.user_actions.count_documents({}),
            'recent_detections_24h': self.db.detection_history.count_documents({
                'timestamp': {'$gte': datetime.utcnow() - timedelta(days=1)}
            }),
            'high_risk_detections': self.db.detection_history.count_documents({
                'risk_level': 'high'
            }),
        }
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("✅ MongoDB connection closed")
