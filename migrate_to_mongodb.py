"""
Migration Script: Pickle to MongoDB

Migrates existing face database from pickle file to MongoDB.
Run this once when switching to MongoDB.
"""

import sys
import os
from pathlib import Path
import yaml

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from utils.mongodb_manager import MongoDBManager


def migrate_pickle_to_mongodb(config_path: str = "config/settings.yaml"):
    """
    Migrate face database from pickle file to MongoDB.
    
    Args:
        config_path: Path to configuration file
    """
    print("=" * 60)
    print("📦 Face Database Migration: Pickle → MongoDB")
    print("=" * 60)
    
    # Load config
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Check MongoDB config
    mongodb_config = config.get('mongodb', {})
    if not mongodb_config.get('enabled', False):
        print("❌ MongoDB is not enabled in config/settings.yaml")
        print("   Set mongodb.enabled: true and provide connection_string")
        return
    
    connection_string = mongodb_config.get('connection_string')
    database_name = mongodb_config.get('database_name', 'visionguard_ai')
    
    if not connection_string:
        print("❌ MongoDB connection_string not configured")
        return
    
    # Initialize MongoDB
    try:
        mongo_manager = MongoDBManager(connection_string, database_name)
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        return
    
    # Load pickle database
    import pickle
    database_path = config['models']['face_recognition'].get('database_path', './data/face_database')
    db_file = os.path.join(database_path, 'face_embeddings.pkl')
    
    if not os.path.exists(db_file):
        print(f"❌ Pickle database not found at: {db_file}")
        return
    
    print(f"📂 Loading pickle database from: {db_file}")
    
    with open(db_file, 'rb') as f:
        face_database = pickle.load(f)
    
    print(f"✅ Loaded {len(face_database)} identities from pickle file")
    
    # Migrate each face
    print("\n🔄 Starting migration...")
    migrated = 0
    skipped = 0
    
    for name, face_data in face_database.items():
        try:
            embedding = face_data['embedding']
            metadata = face_data.get('metadata', {})
            
            success = mongo_manager.add_face(name, embedding, metadata)
            if success:
                migrated += 1
                print(f"  ✅ Migrated: {name}")
            else:
                skipped += 1
                print(f"  ⚠️  Skipped (already exists): {name}")
        except Exception as e:
            print(f"  ❌ Error migrating {name}: {e}")
            skipped += 1
    
    print("\n" + "=" * 60)
    print("✅ Migration Complete!")
    print(f"   Migrated: {migrated}")
    print(f"   Skipped: {skipped}")
    print(f"   Total: {len(face_database)}")
    print("=" * 60)
    
    # Show statistics
    stats = mongo_manager.get_statistics()
    print("\n📊 MongoDB Statistics:")
    print(f"   Total faces: {stats['total_faces']}")
    print(f"   Total detections: {stats['total_detections']}")
    print(f"   Total analyses: {stats['total_analyses']}")
    
    mongo_manager.close()


if __name__ == "__main__":
    migrate_pickle_to_mongodb()
