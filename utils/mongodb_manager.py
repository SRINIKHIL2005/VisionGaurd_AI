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
            # SSL/TLS configuration for Python 3.13 compatibility
            import certifi
            import ssl
            
            # Try different SSL version configurations
            # This fixes the TLS handshake issue with Python 3.13
            try:
                # First attempt: Use basic TLS with certifi certificates
                self.client = MongoClient(
                    self.connection_string,
                    serverSelectionTimeoutMS=10000,
                    tls=True,
                    tlsCAFile=certifi.where(),
                    tlsAllowInvalidCertificates=False,
                    tlsAllowInvalidHostnames=False
                )
            except Exception as e1:
                print(f"⚠️ First connection attempt failed: {e1}")
                # Fallback: Minimal SSL settings
                self.client = MongoClient(
                    self.connection_string,
                    serverSelectionTimeoutMS=10000,
                    tls=True,
                    tlsInsecure=True  # Allow insecure TLS for Python 3.13
                )
            
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
        # Users Collection
        if 'users' not in self.db.list_collection_names():
            self.db.create_collection('users')
        self.db.users.create_index([('email', ASCENDING)], unique=True)
        self.db.users.create_index([('created_at', DESCENDING)])
        
        # Face Database Collection
        if 'face_database' not in self.db.list_collection_names():
            self.db.create_collection('face_database')
        # Compound index for user_id + name (unique per user)
        self.db.face_database.create_index([('user_id', ASCENDING), ('name', ASCENDING)], unique=True)
        self.db.face_database.create_index([('user_id', ASCENDING)])
        self.db.face_database.create_index([('added_date', DESCENDING)])
        
        # Detection History Collection
        if 'detection_history' not in self.db.list_collection_names():
            self.db.create_collection('detection_history')
        self.db.detection_history.create_index([('user_id', ASCENDING), ('timestamp', DESCENDING)])
        self.db.detection_history.create_index([('user_id', ASCENDING), ('camera_location', ASCENDING)])
        self.db.detection_history.create_index([('user_id', ASCENDING), ('detected_identities', ASCENDING)])
        
        # Telegram Interactions Collection
        if 'telegram_interactions' not in self.db.list_collection_names():
            self.db.create_collection('telegram_interactions')
        self.db.telegram_interactions.create_index([('user_id', ASCENDING), ('timestamp', DESCENDING)])
        self.db.telegram_interactions.create_index([('user_id', ASCENDING), ('action_type', ASCENDING)])
        self.db.telegram_interactions.create_index([('detection_id', ASCENDING)])
        
        # Analysis History Collection
        if 'analysis_history' not in self.db.list_collection_names():
            self.db.create_collection('analysis_history')
        self.db.analysis_history.create_index([('user_id', ASCENDING), ('timestamp', DESCENDING)])
        self.db.analysis_history.create_index([('user_id', ASCENDING), ('analysis_type', ASCENDING)])
        self.db.analysis_history.create_index([('user_id', ASCENDING), ('risk_level', ASCENDING)])
        
        # User Actions Collection
        if 'user_actions' not in self.db.list_collection_names():
            self.db.create_collection('user_actions')
        self.db.user_actions.create_index([('user_id', ASCENDING), ('timestamp', DESCENDING)])
        self.db.user_actions.create_index([('user_id', ASCENDING), ('action_type', ASCENDING)])
    
    # ===== User Management Operations =====
    
    def create_user(self, email: str, hashed_password: str, full_name: str, 
                   additional_data: Optional[Dict] = None) -> Optional[str]:
        """
        Create a new user account.
        
        Args:
            email: User's email (unique identifier)
            hashed_password: Hashed password
            full_name: User's full name
            additional_data: Optional additional user data
            
        Returns:
            User ID if successful, None otherwise
        """
        try:
            user_doc = {
                'email': email.lower(),
                'password': hashed_password,
                'full_name': full_name,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'is_active': True,
                'telegram_settings': {
                    'enabled': False,
                    'bot_token': None,
                    'chat_id': None,
                    'cooldown_minutes': 3,
                    'retention_days': 10
                },
                'camera_locations': {},
            }
            
            if additional_data:
                user_doc.update(additional_data)
            
            result = self.db.users.insert_one(user_doc)
            print(f"✅ Created user: {email}")
            return str(result.inserted_id)
        except DuplicateKeyError:
            print(f"⚠️ User already exists: {email}")
            return None
        except Exception as e:
            print(f"❌ Error creating user: {e}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email"""
        return self.db.users.find_one({'email': email.lower()})
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        from bson.objectid import ObjectId
        return self.db.users.find_one({'_id': ObjectId(user_id)})
    
    def update_user(self, user_id: str, update_data: Dict) -> bool:
        """
        Update user information.
        
        Args:
            user_id: User's ID
            update_data: Data to update
            
        Returns:
            Success status
        """
        from bson.objectid import ObjectId
        update_data['updated_at'] = datetime.utcnow()
        result = self.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': update_data}
        )
        return result.modified_count > 0
    
    def update_telegram_settings(self, user_id: str, telegram_settings: Dict) -> bool:
        """Update user's Telegram bot settings"""
        from bson.objectid import ObjectId
        result = self.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'telegram_settings': telegram_settings,
                'updated_at': datetime.utcnow()
            }}
        )
        return result.modified_count > 0
    
    # ===== Face Database Operations =====
    
    def add_face(self, user_id: str, name: str, embedding: np.ndarray, metadata: Dict) -> bool:
        """
        Add face to database.
        
        Args:
            user_id: User's ID
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
                'user_id': user_id,
                'name': name,
                'embedding': embedding_b64,
                'metadata': metadata,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            self.db.face_database.insert_one(face_doc)
            print(f"✅ Added face to MongoDB: {name} (user: {user_id})")
            return True
        except DuplicateKeyError:
            print(f"⚠️ Face already exists for this user: {name}")
            return False
        except Exception as e:
            print(f"❌ Error adding face: {e}")
            return False
    
    def get_face(self, user_id: str, name: str) -> Optional[Dict]:
        """Get face by name for specific user"""
        doc = self.db.face_database.find_one({'user_id': user_id, 'name': name})
        if doc:
            # Convert embedding back to numpy array
            embedding_bytes = base64.b64decode(doc['embedding'])
            doc['embedding'] = pickle.loads(embedding_bytes)
        return doc
    
    def get_all_faces(self, user_id: str) -> Dict[str, Dict]:
        """
        Get all faces from database for specific user.
        
        Args:
            user_id: User's ID
            
        Returns:
            Dictionary {name: {embedding, metadata}}
        """
        faces = {}
        for doc in self.db.face_database.find({'user_id': user_id}):
            # Convert embedding back to numpy array
            embedding_bytes = base64.b64decode(doc['embedding'])
            embedding = pickle.loads(embedding_bytes)
            
            faces[doc['name']] = {
                'embedding': embedding,
                'metadata': doc['metadata']
            }
        return faces
    
    def remove_face(self, user_id: str, name: str) -> bool:
        """Remove face from database for specific user"""
        result = self.db.face_database.delete_one({'user_id': user_id, 'name': name})
        return result.deleted_count > 0
    
    def list_identities(self, user_id: str, detailed: bool = False) -> List:
        """List all identities for specific user"""
        if detailed:
            identities = []
            for doc in self.db.face_database.find({'user_id': user_id}).sort('created_at', DESCENDING):
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
            return [doc['name'] for doc in self.db.face_database.find({'user_id': user_id})]
    
    # ===== Detection History Operations =====
    
    def log_detection(self, user_id: str, detection_data: Dict) -> str:
        """
        Log detection event.
        
        Args:
            user_id: User's ID
            detection_data: Detection information
            
        Returns:
            Detection ID
        """
        doc = {
            'user_id': user_id,
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
    
    def get_detection_history(self, user_id: str, limit: int = 100, camera_location: Optional[str] = None,
                              start_date: Optional[datetime] = None) -> List[Dict]:
        """Get detection history with filters for specific user"""
        query = {'user_id': user_id}
        if camera_location:
            query['camera_location'] = camera_location
        if start_date:
            query['timestamp'] = {'$gte': start_date}
        
        return list(self.db.detection_history.find(query).sort('timestamp', DESCENDING).limit(limit))
    
    # ===== Telegram Interactions =====
    
    def log_telegram_interaction(self, user_id: str, interaction_data: Dict) -> str:
        """
        Log Telegram bot interaction.
        
        Args:
            user_id: User's ID
            interaction_data: Interaction details
            
        Returns:
            Interaction ID
        """
        doc = {
            'user_id': user_id,
            'timestamp': datetime.utcnow(),
            'action_type': interaction_data.get('action_type'),  # notification, approval, rejection
            'detection_id': interaction_data.get('detection_id'),
            'telegram_user_id': interaction_data.get('telegram_user_id'),
            'username': interaction_data.get('username'),
            'first_name': interaction_data.get('first_name'),
            'last_name': interaction_data.get('last_name'),
            'message': interaction_data.get('message'),
            'response': interaction_data.get('response'),
            'approved_name': interaction_data.get('approved_name'),
        }
        result = self.db.telegram_interactions.insert_one(doc)
        return str(result.inserted_id)
    
    def get_telegram_history(self, user_id: str, limit: int = 100) -> List[Dict]:
        """Get Telegram interaction history for specific user"""
        return list(self.db.telegram_interactions.find({'user_id': user_id}).sort('timestamp', DESCENDING).limit(limit))
    
    # ===== Analysis History =====
    
    def log_analysis(self, user_id: str, analysis_data: Dict) -> str:
        """
        Log complete analysis result.
        
        Args:
            user_id: User's ID
            analysis_data: Full analysis result
            
        Returns:
            Analysis ID
        """
        doc = {
            'user_id': user_id,
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
    
    def get_analysis_history(self, user_id: str, limit: int = 100, analysis_type: Optional[str] = None) -> List[Dict]:
        """Get analysis history for specific user"""
        query = {'user_id': user_id}
        if analysis_type:
            query['analysis_type'] = analysis_type
        
        return list(self.db.analysis_history.find(query).sort('timestamp', DESCENDING).limit(limit))
    
    # ===== User Actions =====
    
    def log_user_action(self, user_id: str, action_data: Dict) -> str:
        """
        Log user action.
        
        Args:
            user_id: User's ID
            action_data: Action details
            
        Returns:
            Action ID
        """
        doc = {
            'user_id': user_id,
            'timestamp': datetime.utcnow(),
            'action_type': action_data.get('action_type'),  # add_face, remove_face, upload_image, etc.
            'details': action_data.get('details'),
            'ip_address': action_data.get('ip_address'),
        }
        result = self.db.user_actions.insert_one(doc)
        return str(result.inserted_id)
    
    # ===== Statistics =====
    
    def get_statistics(self, user_id: str) -> Dict:
        """Get database statistics for specific user"""
        return {
            'total_faces': self.db.face_database.count_documents({'user_id': user_id}),
            'total_detections': self.db.detection_history.count_documents({'user_id': user_id}),
            'total_telegram_interactions': self.db.telegram_interactions.count_documents({'user_id': user_id}),
            'total_analyses': self.db.analysis_history.count_documents({'user_id': user_id}),
            'total_user_actions': self.db.user_actions.count_documents({'user_id': user_id}),
            'recent_detections_24h': self.db.detection_history.count_documents({
                'user_id': user_id,
                'timestamp': {'$gte': datetime.utcnow() - timedelta(days=1)}
            }),
            'high_risk_detections': self.db.detection_history.count_documents({
                'user_id': user_id,
                'risk_level': 'high'
            }),
        }
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("✅ MongoDB connection closed")
