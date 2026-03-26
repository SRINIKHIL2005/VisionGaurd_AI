"""
One-time fix: drop the stale global unique index on 'name' in face_database.

The old index (name_1) enforced uniqueness across ALL users, meaning two different
accounts could not share the same identity name (e.g. both having "Nikhil").

The correct index is the compound (user_id, name) unique index, which only prevents
the SAME user from adding the same name twice.

Run once:  python fix_face_index.py
"""
import sys
import os
import yaml
sys.path.insert(0, os.path.dirname(__file__))

from utils.mongodb_manager import MongoDBManager

# Load connection string from config
with open(os.path.join(os.path.dirname(__file__), 'config', 'settings.yaml'), 'r') as f:
    config = yaml.safe_load(f)

mongodb_cfg = config.get('mongodb', {})
connection_string = mongodb_cfg.get('connection_string', 'mongodb://localhost:27017')
database_name = mongodb_cfg.get('database_name', 'visionguard_ai')

manager = MongoDBManager(connection_string, database_name)

if manager.db is None:
    print("❌ Could not connect to MongoDB. Check your settings.")
    sys.exit(1)

collection = manager.db.face_database
indexes = collection.index_information()

print("Current indexes on face_database:")
for idx_name, idx_info in indexes.items():
    print(f"  {idx_name}: {idx_info}")

# Drop stale single-field unique index on 'name' if it exists
if 'name_1' in indexes:
    if indexes['name_1'].get('unique'):
        collection.drop_index('name_1')
        print("\n✅ Dropped stale unique index 'name_1'.")
    else:
        print("\nℹ️  'name_1' index exists but is not unique — no action needed.")
else:
    print("\nℹ️  No 'name_1' index found — database is already clean.")

# Ensure the correct compound index exists
from pymongo import ASCENDING
collection.create_index([('user_id', ASCENDING), ('name', ASCENDING)], unique=True)
print("✅ Compound unique index (user_id, name) confirmed.")

print("\nDone. Different users can now share the same identity name.")
