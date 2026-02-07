"""
Check database contents
"""
import pickle
import os

db_file = "data/face_database/face_embeddings.pkl"

with open(db_file, 'rb') as f:
    database = pickle.load(f)

print(f"Total identities: {len(database)}\n")

for name, face_data in database.items():
    print(f"Name: {name}")
    if isinstance(face_data, dict):
        metadata = face_data.get('metadata', {})
        print(f"  Added: {metadata.get('added_date')}")
        print(f"  Approved by: {metadata.get('approved_by')}")
        print(f"  Location: {metadata.get('camera_location')}")
        print(f"  Photo: {metadata.get('photo_path')}")
    else:
        print(f"  Format: OLD (embedding only)")
    print()
