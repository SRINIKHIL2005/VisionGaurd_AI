"""
Clear Telegram Cooldown - Run this to test notifications immediately
"""
import json
from pathlib import Path

queue_file = Path("data/face_database/unknown_queue.json")

if queue_file.exists():
    # Clear the queue
    with open(queue_file, 'w') as f:
        json.dump([], f)
    print("✅ Cooldown cleared! You can now receive notifications immediately.")
    print("🔄 Try Live CCTV again - it should send notifications now.")
else:
    print("⚠️ Queue file not found. Creating empty queue...")
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    with open(queue_file, 'w') as f:
        json.dump([], f)
    print("✅ Queue created and cleared!")
