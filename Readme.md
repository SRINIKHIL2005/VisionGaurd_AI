# VisionGuard AI

A real-time AI surveillance system that watches your cameras, detects threats, recognises faces, and alerts you instantly — all controlled by a voice assistant.

---

## What It Does

VisionGuard AI analyses every frame from a live camera, uploaded image, or video file and runs three AI models simultaneously:

1. **Deepfake / AI-image detection** — flags AI-generated or manipulated media
2. **Face recognition** — identifies registered people, queues unknowns for review
3. **Object & weapon detection** — spots weapons, suspicious objects, and more

Every detection is stored in MongoDB, a risk score is generated (Low to Critical), and a Telegram alert is sent when something serious is found. A built-in voice assistant (Jarvis) lets you ask questions about past activity and control the UI hands-free.

---

## Architecture

```
+---------------------------------+      +----------------------------------+
|        React Frontend           |<---->|        FastAPI Backend            |
|  (Vite . Tailwind . Framer      |      |  api/main.py  (port 8000)        |
|   Motion . Lucide Icons)        |      |                                  |
|                                 |      |  +----------------------------+  |
|  Pages                          |      |  |      VisionPipeline         |  |
|  +-- Dashboard                  |      |  |  pipeline/vision_pipeline.py|  |
|  +-- Image Analysis             |      |  |                            |  |
|  +-- Video Analysis             |      |  |  +--------------------+   |  |
|  +-- Live CCTV                  |      |  |  |  Deepfake Detector |   |  |
|  +-- Face Database              |      |  |  |  (Gemini API / ViT)|   |  |
|  +-- Settings                   |      |  |  +--------------------+   |  |
|  +-- Login / Signup             |      |  |  |  Face Recognizer   |   |  |
|                                 |      |  |  |  (InsightFace)     |   |  |
|  Components                     |      |  |  +--------------------+   |  |
|  +-- Jarvis Assistant           |      |  |  |  Object Detector   |   |  |
|  +-- Wake Word Listener         |      |  |  |  (YOLOv8 + weapon) |   |  |
|  +-- Jarvis Orb (floating mic)  |      |  |  +--------------------+   |  |
+---------------------------------+      |  +----------------------------+  |
                                         |                                  |
                                         |  +----------+  +-------------+  |
                                         |  | RAG Engine|  |Gemini Client|  |
                                         |  |  (FAISS)  |  | 2.0 Flash   |  |
                                         |  +----------+  +-------------+  |
                                         |                                  |
                                         |  +----------+  +-------------+  |
                                         |  | MongoDB   |  |  Telegram   |  |
                                         |  |  Atlas    |  |   Notifier  |  |
                                         |  +----------+  +-------------+  |
                                         +----------------------------------+
```

---

## How a Frame Is Processed

```
Camera / Upload / Video
        |
        v
  VisionPipeline.analyze()
        |
        +---> Deepfake Detector
        |         Images  --> Gemini 2.0 Flash (multipart vision)
        |         Video   --> HuggingFace ViT (dima806/deepfake_vs_real_image_detection)
        |
        +---> Face Recognizer (InsightFace ArcFace r100)
        |         Known person  --> label + confidence
        |         Unknown face  --> saved to queue, Telegram notified
        |
        +---> Object Detector (YOLOv8n)
                  General objects detected every frame
                  Weapon sub-model (custom best.pt) runs on person crops
                  every 3rd frame (ROI mode, only when person present)
                        |
                        v
              Risk Score: Low / Medium / High / Critical
                        |
            +-----------+-----------+
            v           v           v
       MongoDB      Telegram    RAG Index
       (log)        (alert)     (FAISS)
                                    |
                                    v
                             Jarvis can answer
                          "what happened yesterday?"
```

---

## Models Used

| Model | Purpose | Source |
|---|---|---|
| `yolov8n.pt` | General object detection (people, vehicles, bags...) | Ultralytics YOLOv8 Nano |
| `Learning/best.pt` | Custom weapon detector (guns, knives) | Locally trained YOLO |
| `dima806/deepfake_vs_real_image_detection` | AI-generated image detection for video frames | HuggingFace |
| Google Gemini 2.0 Flash | Deepfake analysis for still images + AI assistant | Google API |
| InsightFace ArcFace r100 | Face recognition and embedding | InsightFace |

---

## Tech Stack

### Backend

| Tool | Role |
|---|---|
| **FastAPI** | REST API server (async, port 8000) |
| **Python 3.10+** | Core language |
| **Ultralytics YOLOv8** | Object and weapon detection |
| **InsightFace** | Face recognition (ArcFace embeddings) |
| **HuggingFace Transformers** | ViT deepfake model for video frames |
| **Google Gemini 2.0 Flash** | Image deepfake analysis + AI assistant LLM |
| **FAISS** | Vector store for RAG log retrieval |
| **MongoDB Atlas** | Cloud database for users, detections, and history |
| **python-telegram-bot** | Telegram alerts and unknown face approve/reject |
| **Edge TTS** | Microsoft neural TTS for Jarvis voice (free, online) |
| **pyttsx3** | Offline TTS fallback |
| **JWT + bcrypt** | Authentication — token issuance and password hashing |

### Frontend

| Tool | Role |
|---|---|
| **React 18** | UI framework |
| **Vite** | Build tool and dev server (port 3000) |
| **Tailwind CSS** | Styling |
| **Framer Motion** | Animations and transitions |
| **Lucide React** | Icons |
| **Axios** | HTTP client |
| **React Router v6** | Page routing |

---

## Project Structure

```
VRSU/
|-- api/
|   `-- main.py                  # FastAPI app -- all endpoints
|-- pipeline/
|   `-- vision_pipeline.py       # Orchestrates all three AI models
|-- models/
|   |-- deepfake/
|   |   `-- deepfake_detector.py
|   |-- face_recognition/
|   |   `-- face_recognizer.py
|   `-- object_detection/
|       `-- yolo_detector.py
|-- utils/
|   |-- auth.py                  # JWT helpers
|   |-- mongodb_manager.py       # MongoDB CRUD and user management
|   |-- rag_engine.py            # FAISS-based log retrieval
|   |-- llm_client.py            # Gemini API wrapper (text + multipart vision)
|   |-- telegram_notifier.py     # Telegram bot alerts
|   `-- iou_tracker.py           # Lightweight tracker for CCTV person IDs
|-- frontend/
|   `-- src/
|       |-- pages/               # Dashboard, ImageAnalysis, VideoAnalysis,
|       |                        # LiveCCTV, FaceDatabase, Settings, Login, Signup
|       |-- components/          # JarvisAssistant, WakeWordListener, JarvisOrb,
|       |                        # Sidebar, ProtectedRoute, RiskBadge, StatsCard
|       `-- services/
|           `-- authService.js
|-- config/
|   |-- settings.yaml            # Your local config (git-ignored)
|   `-- settings.yaml.example    # Template to copy from
|-- data/
|   `-- face_database/           # Per-user face embeddings and photos
|-- Learning/
|   `-- best.pt                  # Custom trained weapon detector
|-- yolov8n.pt                   # YOLOv8 Nano base model
`-- requirements.txt
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Get JWT token |
| GET | `/auth/me` | Current user info |
| POST | `/analyze/image` | Analyse an uploaded image |
| POST | `/analyze/video` | Analyse a video file |
| POST | `/face/add` | Register a new face identity |
| GET | `/face/list` | List all registered identities |
| DELETE | `/face/{name}` | Remove an identity |
| POST | `/assistant/narrate` | Ask Jarvis a question (RAG + Gemini) |
| POST | `/assistant/tts` | Convert text to speech (Edge TTS) |
| GET | `/faces/unknown` | List unknown faces pending review |
| POST | `/faces/unknown/{id}/approve` | Approve and name an unknown face |
| POST | `/faces/unknown/{id}/reject` | Reject an unknown face |
| GET | `/history/detections` | Past detection logs from MongoDB |
| GET | `/stats` | MongoDB database statistics |
| GET | `/health` | Model load status |
| GET | `/db/status` | MongoDB connection status |

---

## Setup

### 1. Clone and install Python dependencies

```bash
git clone <your-repo-url>
cd VRSU
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure settings

```bash
# Windows
copy config\settings.yaml.example config\settings.yaml

# macOS / Linux
cp config/settings.yaml.example config/settings.yaml
```

Open `config/settings.yaml` and fill in:
- `gemini_api_key` from [Google AI Studio](https://aistudio.google.com/) (free)
- MongoDB Atlas connection string
- Telegram bot token and chat ID (optional — only needed for alerts)

### 3. Start the backend

```bash
python api/main.py
```

API available at `http://localhost:8000`  
Interactive docs at `http://localhost:8000/docs`

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

App available at `http://localhost:3000`

---

## Key Features

### Jarvis — AI Voice Assistant

- Say **"Hey Jarvis"** to activate hands-free
- Ask questions: *"What was detected in the last hour?"* — Jarvis retrieves actual logs via RAG and generates a grounded answer using Gemini
- Voice navigation: *"Go to live camera"*, *"Open face database"*
- Camera control: *"Start live feed"*, *"Stop camera"*
- Male and female voice options (Microsoft Edge TTS neural voices)
- Jarvis sees the current camera frame — Gemini receives the actual image as part of the prompt

### Face Recognition

- Registers faces with name, photo, and location metadata
- Unknown faces are queued and saved; a Telegram message is sent with the crop for approve/reject
- Per-user face databases — each account has its own isolated set

### Weapon Detection

- Custom YOLO model (`best.pt`) trained specifically on weapons
- Runs in ROI mode — only analyses person bounding box crops, not the full frame
- Runs every 3rd frame to reduce compute load
- Skipped entirely if no person is detected in the frame

### RAG-Powered Memory

- Every detection is logged to MongoDB and indexed in FAISS
- Jarvis retrieves the most relevant logs for each question using semantic search
- Answers are grounded in real past events, not hallucinated

---

## Configuration Reference

Key settings in `config/settings.yaml`:

```yaml
models:
  deepfake:
    gemini_api_key: "your-key"
    use_gemini_for_images: true    # Gemini for still images, ViT for video
    threshold: 0.35

  face_recognition:
    similarity_threshold: 0.5     # Lower = stricter matching

  object_detection:
    name: "yolov8n.pt"
    confidence: 0.35
    weapon_model: "./Learning/best.pt"
    weapon_confidence: 0.50
    weapon_inference:
      mode: "roi"                  # roi or full
      every_n_frames: 3
      require_person: true

assistant:
  gemini_api_key: "your-key"
  gemini_model: "gemini-2.0-flash"
  voice_preference: "male"        # male or female

mongodb:
  connection_string: "mongodb+srv://..."
  database_name: "visionguard_ai"

telegram:
  bot_token: "your-bot-token"
  chat_id: "your-chat-id"
```

---

## Requirements

- Python 3.10+
- Node.js 18+
- MongoDB Atlas free tier (or local MongoDB)
- Google Gemini API key (free tier at [aistudio.google.com](https://aistudio.google.com/))
- Webcam (for Live CCTV mode)
- Telegram bot (optional — for instant alerts)