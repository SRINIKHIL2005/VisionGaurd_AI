# VisionGuard AI

VisionGuard AI is a unified computer vision system that integrates:
- Deepfake image detection
- Face recognition
- Object detection

The system accepts an image or video as input and performs:
1. Deepfake authenticity verification
2. Identity verification using face recognition
3. Real-time object detection
4. Risk scoring based on combined outputs

Tech Stack:
- Python
- PyTorch
- OpenCV
- YOLOv8
- ArcFace
- Vision Transformer
- FastAPI
- Streamlit

## 🚀 Installation & Setup

### Prerequisites
- Python 3.8 or higher
- Git (optional, for cloning)

### Step 1: Clone or Download the Project
```bash
# If using Git
git clone <repository-url>
cd VRSU

# Or extract the ZIP file and navigate to the folder
```

### Step 2: Create Virtual Environment
```bash
# Create virtual environment
python -m venv .venv
```

### Step 3: Activate Virtual Environment

**Windows (PowerShell/CMD):**
```powershell
.venv\Scripts\activate
```

**Windows (Git Bash):**
```bash
source .venv/Scripts/activate
```

**Linux/Mac:**
```bash
source .venv/bin/activate
```

### Step 4: Install Dependencies
```bash
# Install all required packages (this may take 5-10 minutes for ML libraries)
pip install -r requirements.txt
```

### Step 5: Verify Installation
```bash
# Check if PyTorch is installed correctly
python -c "import torch; print(f'PyTorch: {torch.__version__}')"

# Check if CUDA is available (for GPU support)
python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}')"
```

### Step 6: Run the Application

**Option 1: FastAPI Backend**
```bash
cd api
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Access at: http://localhost:8000

**Option 2: Streamlit UI**
```bash
streamlit run ui/app.py
```

**Option 3: Frontend (React)**
```bash
cd frontend
npm install
npm run dev
```

### Important Notes:
- ⚠️ **Never share or commit the `.venv` folder** - it's 8GB+ and platform-specific
- ✅ `.venv` is already in `.gitignore`
- ✅ Anyone can recreate `.venv` using the steps above
- 📦 Total project size (without `.venv`): ~30MB

---

🔍 VisionGuard AI — Inputs & Outputs (Final)
4
✅ INPUTS (What the system takes)

Your project accepts visual data only.

1️⃣ Image Input

Formats: JPG, PNG

Content:

Face images (selfies, profile photos)

Scene images (rooms, public places)

Documents with faces

2️⃣ Video Input (Optional / Advanced)

Formats: MP4

Content:

Recorded videos

CCTV footage

Screen recordings

3️⃣ Live Camera Input (Optional)

Source:

Webcam

IP camera (RTSP)

✅ OUTPUTS (What the system gives)

The output is structured visual + textual information, not just labels.

🔹 1️⃣ Deepfake Detection Output

Real / Fake classification

Confidence score (0–100%)

Optional: manipulated region heatmap

Example:

Deepfake Status: FAKE
Confidence: 92.3%

🔹 2️⃣ Visual Recognition Output

Face detected: Yes / No

Identity result:

Known person

Unknown person

Similarity score (%)

Example:

Identity: Unknown
Match Confidence: 18%

🔹 3️⃣ Object Detection Output

Detected objects list

Bounding boxes

Confidence per object

Example:

Objects Detected:
- Mobile Phone (0.87)
- Person (0.99)

🔹 4️⃣ Risk Assessment Output (FINAL DECISION)

The system combines all results.

Example:

Overall Risk Level: HIGH
Reason:
- Fake image detected
- Unknown identity
- Suspicious object present

🔹 5️⃣ Visual Output (UI)

Image/video with:

Bounding boxes

Labels

Confidence scores

Timeline view (for video)

🔹 6️⃣ Machine-Readable Output (JSON)

Example:

{
  "deepfake": {
    "status": "fake",
    "confidence": 0.92
  },
  "face_recognition": {
    "identity": "unknown",
    "confidence": 0.18
  },
  "objects": [
    {"label": "mobile_phone", "confidence": 0.87}
  ],
  "risk_level": "HIGH"
}

🎯 One-Line Summary (Perfect Answer)

Input: Image, video, or live camera feed
Output: Authenticity verification, identity recognition, object detection results, and a final risk assessment

🧠 Why This Input–Output Design Is STRONG

✔ Clear and measurable
✔ Easy to evaluate
✔ Fits real-world systems
✔ Easy to demo
✔ Industry-aligned

📝 Ready-to-use for Report

Input:
The system accepts image, video, or live camera feeds containing human faces and surrounding environments.

Output:
The system produces authenticity verification results, identity recognition scores, detected objects with bounding boxes, and an overall risk assessment.

visionguard-ai/
│
├── README.md
│
├── requirements.txt
│
├── config/
│   └── settings.yaml
│
├── models/
│   ├── deepfake/
│   │   └── deepfake_detector.py
│   │
│   ├── face_recognition/
│   │   └── face_recognizer.py
│   │
│   ├── object_detection/
│   │   └── yolo_detector.py
│
├── pipeline/
│   └── vision_pipeline.py
│
├── api/
│   └── main.py
│
├── utils/
│   └── image_utils.py
│
└── ui/
    └── app.py
