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

### Step 5: Configure Settings
```bash
# Copy the example configuration file
cp config/settings.yaml.example config/settings.yaml

# Edit config/settings.yaml and add:
# - Your Gemini API key (for deepfake detection)
# - Your Telegram bot token (optional, for notifications)
# - Your Telegram chat ID (optional)
```

**Important:** Never commit `config/settings.yaml` with your API keys - it's already in `.gitignore`.

### Step 6: Verify Installation
```bash
# Check if PyTorch is installed correctly
python -c "import torch; print(f'PyTorch: {torch.__version__}')"

# Check if CUDA is available (for GPU support)
python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}')"
```

### Step 7: Run the Application

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

