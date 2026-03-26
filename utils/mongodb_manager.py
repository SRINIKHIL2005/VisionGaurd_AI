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
from pymongo.errors import ConnectionFailure, DuplicateKeyError, ServerSelectionTimeoutError
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Optional, Any
import pickle
import base64
import time
import threading


class MongoDBManager:
    """MongoDB manager for VisionGuard AI"""

    # How long to wait before retrying a failed connection (seconds)
    _RETRY_INTERVAL = 30
    # Atlas-friendly timeouts (ms)
    _CONNECT_TIMEOUT_MS = 30000
    _SOCKET_TIMEOUT_MS  = 30000
    _SERVER_SEL_TIMEOUT_MS = 30000

    def __init__(self, connection_string: str, database_name: str = "visionguard_ai"):
        """
        Initialize MongoDB connection.  Never raises — the app runs even when
        Atlas is temporarily unreachable, and auto-reconnects in the background.

        Args:
            connection_string: MongoDB connection string
            database_name: Database name to use
        """
        self.connection_string = connection_string
        self.database_name = database_name
        self.client = None
        self._db = None                  # backing store for the db property
        self.is_connected = False
        self._connect_lock = threading.Lock()
        self._last_attempt: float = 0.0
        self._connect()

    # ------------------------------------------------------------------ #
    #  Connection management                                               #
    # ------------------------------------------------------------------ #

    @property
    def db(self):
        """Return the live DB handle, transparently reconnecting if needed."""
        if self._db is None or not self.is_connected:
            self._try_reconnect_if_due()
        return self._db

    @db.setter
    def db(self, value):
        self._db = value

    def _clean_uri(self) -> str:
        """Strip TLS/SSL params from URI so kwargs are the sole source of truth."""
        import re
        uri = re.sub(r'[&?]tls(?:Allow\w+|Insecure|CAFile|CertificateKey(?:File|Password)?|[^=&]*)=[^&]*', '', self.connection_string)
        uri = re.sub(r'[&?]ssl(?:[^=&]*)=[^&]*', '', uri)
        uri = re.sub(r'[?&]$', '', uri)
        return uri

    def _build_client(self, allow_insecure_tls: bool = False) -> MongoClient:
        """Build a MongoClient.  NOTE: MongoClient is lazy — this never raises."""
        base = dict(
            serverSelectionTimeoutMS=self._SERVER_SEL_TIMEOUT_MS,
            connectTimeoutMS=self._CONNECT_TIMEOUT_MS,
            socketTimeoutMS=self._SOCKET_TIMEOUT_MS,
            retryWrites=True,
            retryReads=True,
            tls=True,
        )
        if allow_insecure_tls:
            # Bypass all cert / hostname validation (matches original URL intent)
            return MongoClient(self._clean_uri(), **base,
                               tlsAllowInvalidCertificates=True,
                               tlsAllowInvalidHostnames=True)
        # Strict path: use certifi CA bundle when available
        try:
            import certifi
            return MongoClient(self._clean_uri(), **base, tlsCAFile=certifi.where())
        except ImportError:
            return MongoClient(self._clean_uri(), **base)

    def _connect(self):
        """
        Attempt to establish a MongoDB connection.
        Never raises — sets self.is_connected accordingly.
        Tries strict TLS (certifi) first, then falls back to
        tlsAllowInvalidCertificates=True if the SSL handshake fails.
        """
        with self._connect_lock:
            self._last_attempt = time.monotonic()
            if self.client:
                try:
                    self.client.close()
                except Exception:
                    pass

            last_exc = None
            for allow_insecure in (False, True):
                client = None
                try:
                    client = self._build_client(allow_insecure_tls=allow_insecure)
                    # ping() is where the actual TCP + TLS handshake happens (MongoClient is lazy)
                    client.admin.command('ping')
                    self.client = client
                    self._db = self.client[self.database_name]
                    self._setup_collections()
                    self.is_connected = True
                    print(f"✅ Connected to MongoDB: {self.database_name}")
                    return
                except Exception as e:
                    last_exc = e
                    if client is not None:
                        try:
                            client.close()
                        except Exception:
                            pass
                    if not allow_insecure:
                        # First attempt (strict TLS) failed — retry with cert bypass
                        continue

            # Both attempts exhausted
            self.is_connected = False
            self._db = None
            short = str(last_exc).split(',')[0].strip()
            print(f"⚠️  MongoDB unavailable (will retry in {self._RETRY_INTERVAL}s): {short}")

    def _try_reconnect_if_due(self):
        """Reconnect only if enough time has passed since the last attempt."""
        elapsed = time.monotonic() - self._last_attempt
        if elapsed >= self._RETRY_INTERVAL:
            print("[MongoDB] Attempting reconnect …")
            self._connect()

    def reconnect(self):
        """Force an immediate reconnection attempt (call from health-check routes etc.)."""
        self._last_attempt = 0.0
        self._try_reconnect_if_due()
        return self.is_connected

    def ping(self) -> bool:
        """Return True if the server is reachable right now."""
        try:
            if self.client:
                self.client.admin.command('ping')
                self.is_connected = True
                return True
        except Exception:
            self.is_connected = False
        return False
    
    def _require_db(self, default=None):
        """
        Return the live db handle, or `default` if MongoDB is unavailable.
        Triggers a lazy reconnect attempt if enough time has passed.
        """
        handle = self.db   # property: tries reconnect internally
        if handle is None:
            print("[MongoDB] DB unavailable — operation skipped.")
        return handle

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
        # Drop any old single-field unique index on 'name' that would incorrectly
        # prevent different users from sharing the same identity name.
        try:
            existing_indexes = self.db.face_database.index_information()
            if 'name_1' in existing_indexes and existing_indexes['name_1'].get('unique'):
                self.db.face_database.drop_index('name_1')
                print("⚠️ Dropped stale unique index 'name_1' from face_database collection")
        except Exception as _idx_err:
            print(f"[MongoDB] Index cleanup check failed (non-fatal): {_idx_err}")
        # Compound index for user_id + name (unique per user, not globally)
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
                'assistant_settings': {
                    'enabled': False,
                    'name': 'Jarvis',
                    'voice': 'male',
                    'voice_lock_enabled': False,
                },
                'voice_enrolled': False,
                'voice_embedding': None,
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
        db = self._require_db()
        if db is None:
            return None
        try:
            return db.users.find_one({'email': email.lower()})
        except Exception as e:
            print(f"[MongoDB] get_user_by_email failed: {e}")
            return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        db = self._require_db()
        if db is None:
            return None
        try:
            from bson.objectid import ObjectId
            return db.users.find_one({'_id': ObjectId(user_id)})
        except Exception as e:
            print(f"[MongoDB] get_user_by_id failed: {e}")
            return None
    
    def update_user(self, user_id: str, update_data: Dict) -> bool:
        """
        Update user information.

        Args:
            user_id: User's ID
            update_data: Data to update

        Returns:
            Success status
        """
        db = self._require_db()
        if db is None:
            return False
        try:
            from bson.objectid import ObjectId
            update_data['updated_at'] = datetime.utcnow()
            result = db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"[MongoDB] update_user failed: {e}")
            return False

    def update_telegram_settings(self, user_id: str, telegram_settings: Dict) -> bool:
        """Update user's Telegram bot settings"""
        db = self._require_db()
        if db is None:
            return False
        try:
            from bson.objectid import ObjectId
            result = db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'telegram_settings': telegram_settings, 'updated_at': datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"[MongoDB] update_telegram_settings failed: {e}")
            return False

    def update_assistant_settings(self, user_id: str, assistant_settings: Dict) -> bool:
        """Update user's AI assistant settings (enabled/name)."""
        db = self._require_db()
        if db is None:
            return False
        try:
            from bson.objectid import ObjectId
            result = db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'assistant_settings': assistant_settings, 'updated_at': datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"[MongoDB] update_assistant_settings failed: {e}")
            return False
    
    # ===== Voice Lock =====

    def store_voice_embedding(self, user_id: str, embedding_b64: str) -> bool:
        """Store a base64-encoded voice embedding in the user document."""
        db = self._require_db()
        if db is None:
            return False
        try:
            from bson.objectid import ObjectId
            result = db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'voice_embedding': embedding_b64, 'voice_enrolled': True, 'updated_at': datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"[MongoDB] store_voice_embedding failed: {e}")
            return False

    def get_voice_embedding(self, user_id: str) -> Optional[str]:
        """Return the stored base64 voice embedding string, or None."""
        db = self._require_db()
        if db is None:
            return None
        try:
            from bson.objectid import ObjectId
            user = db.users.find_one({'_id': ObjectId(user_id)}, {'voice_embedding': 1})
            return user.get('voice_embedding') if user else None
        except Exception as e:
            print(f"[MongoDB] get_voice_embedding failed: {e}")
            return None

    def delete_voice_embedding(self, user_id: str) -> bool:
        """Remove the stored voice embedding and mark as not enrolled."""
        db = self._require_db()
        if db is None:
            return False
        try:
            from bson.objectid import ObjectId
            result = db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$unset': {'voice_embedding': ''}, '$set': {'voice_enrolled': False, 'updated_at': datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"[MongoDB] delete_voice_embedding failed: {e}")
            return False

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
        db = self._require_db()
        if db is None:
            return None
        try:
            doc = db.face_database.find_one({'user_id': user_id, 'name': name})
            if doc:
                embedding_bytes = base64.b64decode(doc['embedding'])
                doc['embedding'] = pickle.loads(embedding_bytes)
            return doc
        except Exception as e:
            print(f"[MongoDB] get_face failed: {e}")
            return None

    def get_all_faces(self, user_id: str) -> Dict[str, Dict]:
        """
        Get all faces from database for specific user.

        Args:
            user_id: User's ID

        Returns:
            Dictionary {name: {embedding, metadata}}
        """
        db = self._require_db()
        if db is None:
            return {}
        try:
            faces = {}
            for doc in db.face_database.find({'user_id': user_id}):
                embedding_bytes = base64.b64decode(doc['embedding'])
                embedding = pickle.loads(embedding_bytes)
                faces[doc['name']] = {'embedding': embedding, 'metadata': doc['metadata']}
            return faces
        except Exception as e:
            print(f"[MongoDB] get_all_faces failed: {e}")
            return {}

    def remove_face(self, user_id: str, name: str) -> bool:
        """Remove face from database for specific user"""
        db = self._require_db()
        if db is None:
            return False
        try:
            result = db.face_database.delete_one({'user_id': user_id, 'name': name})
            return result.deleted_count > 0
        except Exception as e:
            print(f"[MongoDB] remove_face failed: {e}")
            return False
    
    def list_identities(self, user_id: str, detailed: bool = False) -> List:
        """List all identities for specific user"""
        db = self._require_db()
        if db is None:
            return []
        try:
            if detailed:
                identities = []
                for doc in db.face_database.find({'user_id': user_id}).sort('created_at', DESCENDING):
                    identities.append({
                        'name': doc['name'],
                        'added_date': doc['metadata'].get('added_date', 'Unknown'),
                        'approved_by': doc['metadata'].get('approved_by', 'Unknown'),
                        'camera_location': doc['metadata'].get('camera_location', 'Unknown'),
                        'photo_path': doc['metadata'].get('photo_path'),
                        'telegram_user_id': doc['metadata'].get('telegram_user_id'),
                        'telegram_username': doc['metadata'].get('telegram_username'),
                        'telegram_first_name': doc['metadata'].get('telegram_first_name'),
                        'telegram_last_name': doc['metadata'].get('telegram_last_name'),
                    })
                return identities
            else:
                return [doc['name'] for doc in db.face_database.find({'user_id': user_id})]
        except Exception as e:
            print(f"[MongoDB] list_identities failed: {e}")
            return []
    
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
        db = self._require_db()
        if db is None:
            return 'offline'
        try:
            result = db.detection_history.insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            print(f"[MongoDB] log_detection failed: {e}")
            return 'error'

    def get_detection_history(self, user_id: str, limit: int = 100, camera_location: Optional[str] = None,
                              start_date: Optional[datetime] = None) -> List[Dict]:
        """Get detection history with filters for specific user"""
        db = self._require_db()
        if db is None:
            return []
        try:
            query = {'user_id': user_id}
            if camera_location:
                query['camera_location'] = camera_location
            if start_date:
                query['timestamp'] = {'$gte': start_date}
            return list(db.detection_history.find(query).sort('timestamp', DESCENDING).limit(limit))
        except Exception as e:
            print(f"[MongoDB] get_detection_history failed: {e}")
            return []
    
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
        db = self._require_db()
        if db is None:
            return 'offline'
        try:
            result = db.telegram_interactions.insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            print(f"[MongoDB] log_telegram_interaction failed: {e}")
            return 'error'

    def get_telegram_history(self, user_id: str, limit: int = 100) -> List[Dict]:
        """Get Telegram interaction history for specific user"""
        db = self._require_db()
        if db is None:
            return []
        try:
            return list(db.telegram_interactions.find({'user_id': user_id}).sort('timestamp', DESCENDING).limit(limit))
        except Exception as e:
            print(f"[MongoDB] get_telegram_history failed: {e}")
            return []
    
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
        db = self._require_db()
        if db is None:
            return 'offline'
        try:
            result = db.analysis_history.insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            print(f"[MongoDB] log_analysis failed: {e}")
            return 'error'

    def get_analysis_history(self, user_id: str, limit: int = 100, analysis_type: Optional[str] = None) -> List[Dict]:
        """Get analysis history for specific user"""
        db = self._require_db()
        if db is None:
            return []
        try:
            query = {'user_id': user_id}
            if analysis_type:
                query['analysis_type'] = analysis_type
            return list(db.analysis_history.find(query).sort('timestamp', DESCENDING).limit(limit))
        except Exception as e:
            print(f"[MongoDB] get_analysis_history failed: {e}")
            return []
    
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
        db = self._require_db()
        if db is None:
            return 'offline'
        try:
            result = db.user_actions.insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            print(f"[MongoDB] log_user_action failed: {e}")
            return 'error'
    
    # ===== Statistics =====
    
    def get_statistics(self, user_id: str) -> Dict:
        """Get database statistics for specific user"""
        db = self._require_db()
        if db is None:
            return {
                'total_faces': 0, 'total_detections': 0,
                'total_telegram_interactions': 0, 'total_analyses': 0,
                'total_user_actions': 0, 'recent_detections_24h': 0,
                'high_risk_detections': 0, 'db_status': 'offline',
            }
        try:
            return {
                'total_faces': db.face_database.count_documents({'user_id': user_id}),
                'total_detections': db.detection_history.count_documents({'user_id': user_id}),
                'total_telegram_interactions': db.telegram_interactions.count_documents({'user_id': user_id}),
                'total_analyses': db.analysis_history.count_documents({'user_id': user_id}),
                'total_user_actions': db.user_actions.count_documents({'user_id': user_id}),
                'recent_detections_24h': db.detection_history.count_documents({
                    'user_id': user_id,
                    'timestamp': {'$gte': datetime.utcnow() - timedelta(days=1)}
                }),
                'high_risk_detections': db.detection_history.count_documents({
                    'user_id': user_id, 'risk_level': 'high'
                }),
                'db_status': 'online',
            }
        except Exception as e:
            print(f"[MongoDB] get_statistics failed: {e}")
            return {
                'total_faces': 0, 'total_detections': 0,
                'total_telegram_interactions': 0, 'total_analyses': 0,
                'total_user_actions': 0, 'recent_detections_24h': 0,
                'high_risk_detections': 0, 'db_status': 'error',
            }
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("✅ MongoDB connection closed")
