# MongoDB Setup Guide for VisionGuard AI

## Overview

VisionGuard AI now supports MongoDB for storing:
- **Face Database**: Identities with embeddings and metadata
- **Detection History**: All face/object detection events
- **Telegram Interactions**: Bot notifications and user responses
- **Analysis History**: Complete analysis results
- **User Actions**: All user inputs and actions

## Quick Setup

### 1. Install Dependencies

```bash
pip install pymongo dnspython
```

### 2. Choose MongoDB Option

#### Option A: MongoDB Atlas (Cloud - Recommended)

1. Create free account at [https://www.mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)
2. Create a new cluster (Free tier available)
3. Add your IP address to whitelist
4. Create database user
5. Get connection string (looks like: `mongodb+srv://username:password@cluster.mongodb.net/`)

#### Option B: Local MongoDB

1. Download and install MongoDB Community Server from [https://www.mongodb.com/try/download/community](https://www.mongodb.com/try/download/community)
2. Start MongoDB service:
   - Windows: MongoDB service starts automatically
   - Linux/Mac: `sudo systemctl start mongod`
3. Default connection string: `mongodb://localhost:27017/`

### 3. Configure VisionGuard AI

Edit `config/settings.yaml`:

```yaml
mongodb:
  enabled: true  # Set to true to enable MongoDB
  connection_string: "YOUR_MONGODB_CONNECTION_STRING_HERE"
  database_name: "visionguard_ai"
```

**Examples:**
- MongoDB Atlas: `mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/`
- Local MongoDB: `mongodb://localhost:27017/`
- With authentication: `mongodb://username:password@localhost:27017/`

### 4. Migrate Existing Data (Optional)

If you have existing face data in pickle files:

```bash
python migrate_to_mongodb.py
```

This will:
- Connect to your MongoDB database
- Load existing faces from `data/face_database/face_embeddings.pkl`
- Upload all faces to MongoDB
- Preserve all metadata (names, dates, telegram info)

## MongoDB Collections

The system creates these collections automatically:

| Collection | Description | Key Fields |
|------------|-------------|------------|
| `face_database` | Registered faces with embeddings | name, embedding, metadata, created_at |
| `detection_history` | Detection events | timestamp, detected_identities, risk_level, camera_location |
| `telegram_interactions` | Telegram bot activity | action_type, user_id, detection_id, message |
| `analysis_history` | Complete analysis results | analysis_type, risk_score, processing_time |
| `user_actions` | User activity log | action_type, user_identifier, timestamp |

## Testing the Connection

```python
# Test MongoDB connection
from utils.mongodb_manager import MongoDBManager

mongo = MongoDBManager(
    connection_string="YOUR_CONNECTION_STRING",
    database_name="visionguard_ai"
)

# Check statistics
stats = mongo.get_statistics()
print(stats)
```

## Switching Between Pickle and MongoDB

You can switch anytime by toggling `mongodb.enabled` in settings:

- **`enabled: false`** → Uses local pickle files (default)
- **`enabled: true`** → Uses MongoDB

The code works with both storage methods seamlessly!

## Security Best Practices

1. **Never commit your connection string to Git**
   - `config/settings.yaml` is in `.gitignore`
   - Use `config/settings.yaml.example` as template

2. **Use environment variables** (optional):
   ```python
   import os
   connection_string = os.getenv('MONGODB_CONNECTION_STRING')
   ```

3. **Enable MongoDB authentication**
4. **Restrict IP addresses** in MongoDB Atlas
5. **Use strong passwords**

## Troubleshooting

### Connection Timeout
- Check your internet connection (for Atlas)
- Verify IP whitelist in Atlas
- Check firewall settings for local MongoDB

### Authentication Failed
- Double-check username and password
- Ensure special characters in password are URL-encoded

### Module not found: pymongo
```bash
pip install pymongo dnspython
```

## Benefits of MongoDB

✅ **Scalable**: Handles millions of records easily  
✅ **Cloud-ready**: Works with MongoDB Atlas (free tier)  
✅ **Searchable**: Query detection history by date, location, risk level  
✅ **Audit trail**: Track all user actions and system activities  
✅ **Real-time**: Instant updates across multiple instances  

## Next Steps

Once MongoDB is configured:
1. ✅ Restart the backend API
2. ✅ All new face registrations go to MongoDB
3. ✅ Detection history is automatically logged
4. ✅ View statistics via `/api/stats` endpoint (coming soon)

For questions or issues, check the logs or raise an issue on GitHub.
