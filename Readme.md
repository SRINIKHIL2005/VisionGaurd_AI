<div align="center">

# VisionGuard AI

**Real-time AI surveillance that watches, detects, and alerts — so you never miss what matters.**



# Overview

VisionGuard AI is an intelligent security platform built for organisations that need more than passive camera feeds. It continuously analyses video in real time, identifies threats the moment they appear, and notifies the right people instantly — all through a clean, voice-controlled interface.

The system is built around three independent AI engines that run simultaneously on every frame, producing a unified risk score that drives automatic alerts and a searchable history you can query in plain English.


## What It Does

| Capability                         | Description                                                                                           |
|------------------------------------|-------------------------------------------------------------------------------------------------------|
| **Deepfake & Media Verification**  | Detects AI-generated or manipulated images and video frames before they cause harm                    |
| **Face Recognition**               | Matches known individuals from a managed identity database; flags and queues unknown faces for review |
| **Weapon & Object Detection**      | Identifies weapons, suspicious objects, and people of interest in real time                           |
| **Instant Alerts**                 | Fires a Telegram notification with a snapshot within seconds of a high-risk detection                 |
| **Jarvis Voice Assistant**n        | Lets operators ask questions ("what happened in the last hour?") and control the interface by voice   |
| **Detection History & Search**     | Every event is stored and searchable — Jarvis retrieves answers from actual past logs, not guesses    |

---

## How It Works

```
Live Camera / Uploaded Image / Video File
                  |
                  v
         AI Analysis Pipeline
         (three engines in parallel)
         /          |           \
   Deepfake    Face Match    Object Scan
   Detection                + Weapon Check
         \          |           /
          v         v          v
            Risk Score Engine
          (Low / Medium / High / Critical)
                  |
        +---------+---------+
        v                   v
   MongoDB               Telegram
   (log + history)       (instant alert)
        |
        v
   Jarvis RAG
   (ask questions in plain English)
```

---

## Interface

The web application is fully dark-themed and responsive, with six main sections:

- **Dashboard** — live model status, system health, and project overview
- **Image Analysis** — upload any image for a full threat report
- **Video Analysis** — upload a video, get a frame-by-frame risk timeline
- **Live CCTV** — real-time webcam feed with AI overlays and instant alerts
- **Face Database** — register, view, and manage known identities
- **Settings** — configure assistant voice, Telegram, and alert preferences

A floating voice assistant (Jarvis) is available on every page. Wake it with "Hey Jarvis" and speak naturally.

---

## Tech at a Glance

**Backend** — Python, FastAPI, PyTorch, computer vision libraries, cloud AI APIs, MongoDB Atlas, Telegram Bot API

**Frontend** — React 18, Vite, Tailwind CSS, Framer Motion

**AI** — Large vision models for deepfake detection, state-of-the-art face embedding for recognition, real-time object detection with a custom-trained weapon model, and an LLM-powered assistant with retrieval-augmented generation

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- MongoDB Atlas account (free tier works)
- API keys for the AI services used (details in `config/settings.yaml.example`)
- A webcam (for Live CCTV mode)
- Telegram bot token (optional — only needed for alerts)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/SRINIKHIL2005/VisionGaurd_AI.git
cd VisionGaurd_AI

# 2. Set up Python environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt

# 3. Configure the application
copy config\settings.yaml.example config\settings.yaml
# Open settings.yaml and fill in your API keys and connection strings

# 4. Start the backend
python api/main.py
# Runs at http://localhost:8000

# 5. Start the frontend (new terminal)
cd frontend
npm install
npm run dev
# Runs at http://localhost:3000
```

Open `http://localhost:3000`, create an account, and the system is ready.

---

## Configuration

Copy `config/settings.yaml.example` to `config/settings.yaml` and fill in:

- AI service API keys
- MongoDB connection string
- Telegram bot credentials (optional)
- Detection confidence thresholds (optional — defaults are tuned)

The example file documents every available option with inline comments.

---

## Project Structure

```
VisionGaurd_AI/
|-- api/              # FastAPI backend and all endpoints
|-- pipeline/         # Core AI orchestration layer
|-- models/           # Deepfake, face, and object detection modules
|-- utils/            # Database, auth, RAG, TTS, and notification helpers
|-- frontend/         # React web application
|-- config/           # Settings template
|-- data/             # Face database storage (created at runtime)
|-- Learning/         # Custom trained model weights
`-- requirements.txt
```

---

## Security & Privacy

- All user accounts are password-protected with hashed credentials and JWT session tokens
- Face databases are isolated per user account — no cross-user data access
- `config/settings.yaml` (containing API keys) is excluded from version control
- Unknown faces are never stored permanently without an operator approval step

---

## Built With

This project was built as part of an academic security research initiative, combining multiple production-grade AI systems into a unified, usable platform. The goal was to explore how modern deep learning tools can be composed into a practical, real-world surveillance product.

---

<div align="center">
  <sub>VisionGuard AI &copy; 2026</sub>
</div>
