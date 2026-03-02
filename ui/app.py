"""
Streamlit UI for VisionGuard AI

Interactive web interface for:
- Image upload and analysis
- Video upload and processing
- Live camera feed (optional)
- Face database management
- Result visualization

Run with: streamlit run app.py
"""

import streamlit as st
import sys
import os
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import json
import time
import tempfile

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from pipeline.vision_pipeline import VisionPipeline
from utils.image_utils import cv2_to_pil, pil_to_cv2

# ===== Page Configuration =====
st.set_page_config(
    page_title="VisionGuard AI",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== Custom CSS =====
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        color: #1E88E5;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    .risk-high {
        background-color: #ff4444;
        color: white;
        padding: 10px;
        border-radius: 5px;
        font-weight: bold;
    }
    .risk-medium {
        background-color: #ffaa00;
        color: white;
        padding: 10px;
        border-radius: 5px;
        font-weight: bold;
    }
    .risk-low {
        background-color: #44ff44;
        color: white;
        padding: 10px;
        border-radius: 5px;
        font-weight: bold;
    }
    .risk-critical {
        background-color: #8B0000;
        color: white;
        padding: 15px;
        border-radius: 5px;
        font-weight: bold;
        font-size: 1.2em;
        animation: blink 1s infinite;
    }
    @keyframes blink {
        0%, 50%, 100% { opacity: 1; }
        25%, 75% { opacity: 0.5; }
    }
    .threat-category {
        background-color: #1E88E5;
        color: white;
        padding: 8px;
        border-radius: 5px;
        font-weight: bold;
        margin-top: 10px;
    }
    </style>
""", unsafe_allow_html=True)


# ===== Initialize Pipeline =====
@st.cache_resource
def load_pipeline():
    """Load and cache the VisionGuard pipeline"""
    with st.spinner("🔧 Loading AI models... This may take a moment..."):
        return VisionPipeline()


# ===== Helper Functions =====
def display_results(result: dict, image: np.ndarray = None, show_expanders: bool = True):
    """Display analysis results in a formatted layout"""
    
    # Main Risk Assessment
    risk_level = result['risk_assessment']['risk_level']
    threat_category = result['risk_assessment'].get('threat_category', 'UNKNOWN')
    risk_class = f"risk-{risk_level.lower()}"
    
    # Display threat category and risk level
    st.markdown(f'<div class="threat-category">🚨 THREAT: {threat_category}</div>', 
                unsafe_allow_html=True)
    st.markdown(f'<div class="{risk_class}">RISK LEVEL: {risk_level}</div>', 
                unsafe_allow_html=True)
    st.markdown(f"**Overall Score:** {result['risk_assessment']['overall_score']:.4f}")
    
    # Display specific threat details
    threats = result['risk_assessment'].get('threats', {})
    if threats.get('has_weapon'):
        st.error(f"🛑 **WEAPONS DETECTED:** {', '.join(threats.get('weapons_detected', []))}")
    if threats.get('has_mask'):
        st.warning("🎭 **MASK DETECTED** - Person is wearing a mask")
    if threats.get('is_unknown_person'):
        st.warning("👤 **UNKNOWN PERSON** - Individual not in database")
    if threats.get('is_deepfake'):
        st.error("🎭 **DEEPFAKE DETECTED** - Manipulated image")
    
    # Create columns for results
    col1, col2, col3 = st.columns(3)
    
    # Deepfake Results
    with col1:
        st.subheader("🎭 Deepfake Detection")
        status = result['deepfake']['status'].upper()
        conf = result['deepfake']['confidence']
        
        if status == "FAKE":
            st.error(f"Status: **{status}**")
        else:
            st.success(f"Status: **{status}**")
        
        st.metric("Confidence", f"{conf*100:.2f}%")
        st.progress(conf)
    
    # Face Recognition Results
    with col2:
        st.subheader("👤 Face Recognition")
        identity = result['face_recognition']['identity']
        face_conf = result['face_recognition']['confidence']
        
        if identity == "Unknown":
            st.warning(f"Identity: **{identity}**")
        elif identity == "No Face":
            st.info(f"**{identity}**")
        else:
            st.success(f"Identity: **{identity}**")
        
        st.metric("Confidence", f"{face_conf*100:.2f}%")
        st.metric("Faces Detected", result['face_recognition']['num_faces'])
    
    # Object Detection Results
    with col3:
        st.subheader("📦 Object Detection")
        num_objects = len(result['objects'])
        num_suspicious = len(result['suspicious_objects'])
        
        st.metric("Objects Detected", num_objects)
        st.metric("Suspicious Items", num_suspicious)
        
        if num_suspicious > 0:
            st.error(f"⚠️ {', '.join(result['suspicious_objects'])}")
    
    # Detailed Results in Expanders (only if show_expanders is True)
    if show_expanders:
        with st.expander("📊 Detailed Results"):
            st.subheader("Risk Assessment Details")
            for reason in result['risk_assessment']['reasons']:
                st.write(f"- {reason}")
            
            st.subheader("Component Scores")
            st.json(result['risk_assessment']['scores'])
        
        with st.expander("🎯 Detected Objects"):
            if result['objects']:
                for obj in result['objects']:
                    st.write(f"- **{obj['label']}**: {obj['confidence']:.2%} @ {obj['bbox']}")
            else:
                st.write("No objects detected")
        
        with st.expander("💾 Raw JSON Output"):
            # Remove annotated image from JSON display
            display_result = {k: v for k, v in result.items() if k != 'annotated_image'}
            st.json(display_result)
    else:
        # Compact view for video frames
        st.write(f"**Objects:** {', '.join([obj['label'] for obj in result['objects'][:5]])}" if result['objects'] else "No objects")
        st.write(f"**Reasons:** {', '.join(result['risk_assessment']['reasons'])}")
    
    # Display annotated image
    if image is not None and 'annotated_image' in result:
        st.subheader("📸 Annotated Result")
        annotated = cv2_to_pil(result['annotated_image'])
        st.image(annotated, use_column_width=True)


# ===== Main App =====
def main():
    # Header
    st.markdown('<div class="main-header">🔍 VisionGuard AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Unified Computer Vision Security System</div>', 
                unsafe_allow_html=True)
    
    # Load pipeline
    try:
        pipeline = load_pipeline()
    except Exception as e:
        st.error(f"❌ Failed to load models: {str(e)}")
        st.info("Make sure all dependencies are installed: `pip install -r requirements.txt`")
        return
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        mode = st.radio(
            "Select Mode",
            ["📸 Image Analysis", "🎥 Video Analysis", "📹 Live Camera (CCTV)", "👥 Face Database"]
        )
        
        st.divider()
        st.subheader("About")
        st.info("""
        **VisionGuard AI** combines:
        - Deepfake Detection
        - Face Recognition
        - Object Detection
        
        Into a unified risk assessment system.
        """)
        
        st.divider()
        st.caption("Powered by PyTorch, YOLOv8, ArcFace & Vision Transformer")
    
    # ===== IMAGE ANALYSIS MODE =====
    if mode == "📸 Image Analysis":
        st.header("📸 Image Analysis")
        
        # Input method selection
        input_method = st.radio(
            "Select Input Method",
            ["📁 Upload Image (Drag & Drop)", "📷 Take Photo from Camera"],
            horizontal=True
        )
        
        image = None
        image_np = None
        
        if input_method == "📁 Upload Image (Drag & Drop)":
            st.info("💡 **Tip:** You can drag and drop an image file directly onto the upload box below!")
            
            uploaded_file = st.file_uploader(
                "Upload an image (JPG, PNG)",
                type=["jpg", "jpeg", "png"],
                help="Drag & drop your image here or click to browse"
            )
            
            if uploaded_file is not None:
                image = Image.open(uploaded_file)
                image_np = pil_to_cv2(image)
        
        else:  # Camera input
            st.info("📷 **Camera:** Click the button below to take a photo using your webcam")
            
            camera_photo = st.camera_input("Take a photo")
            
            if camera_photo is not None:
                image = Image.open(camera_photo)
                image_np = pil_to_cv2(image)
        
        # Process image if available
        if image is not None and image_np is not None:
            # Display original image
            col1, col2 = st.columns([1, 1])
            with col1:
                st.subheader("Original Image")
                st.image(image, use_column_width=True)
            
            # Analyze button
            if st.button("🔍 Analyze Image", type="primary"):
                with st.spinner("🔄 Processing image... Please wait..."):
                    start_time = time.time()
                    result = pipeline.process_image(image_np, return_annotated=True)
                    elapsed = time.time() - start_time
                
                st.success(f"✅ Analysis complete in {elapsed:.2f} seconds!")
                
                # Display results
                display_results(result, image_np)
    
    # ===== VIDEO ANALYSIS MODE =====
    elif mode == "🎥 Video Analysis":
        st.header("🎥 Video Analysis")
        
        uploaded_video = st.file_uploader(
            "Upload a video (MP4)",
            type=["mp4", "avi", "mov"],
            help="Upload a video file for frame-by-frame analysis"
        )
        
        frame_skip = st.slider("Frame Skip (process every Nth frame)", 1, 30, 5)
        
        if uploaded_video is not None:
            # Save video temporarily (cross-platform compatible)
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, uploaded_video.name)
            with open(temp_path, "wb") as f:
                f.write(uploaded_video.read())
            
            # Display video info
            cap = cv2.VideoCapture(temp_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            cap.release()
            
            st.info(f"📊 Video Info: {total_frames} frames @ {fps} FPS")
            st.info(f"Will process approximately {total_frames // frame_skip} frames")
            
            # Analyze button
            if st.button("🎬 Analyze Video", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                with st.spinner("🔄 Processing video..."):
                    start_time = time.time()
                    results = pipeline.process_video(temp_path, frame_skip=frame_skip)
                    elapsed = time.time() - start_time
                
                progress_bar.progress(100)
                st.success(f"✅ Video analysis complete in {elapsed:.2f} seconds!")
                
                # Summary statistics
                st.subheader("📊 Video Summary")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Frames Processed", len(results))
                with col2:
                    high_risk = sum(1 for r in results if r['risk_assessment']['risk_level'] == 'HIGH')
                    st.metric("High Risk Frames", high_risk)
                with col3:
                    fake_detected = sum(1 for r in results if r['deepfake']['status'] == 'fake')
                    st.metric("Fake Frames", fake_detected)
                with col4:
                    avg_score = np.mean([r['risk_assessment']['overall_score'] for r in results])
                    st.metric("Avg Risk Score", f"{avg_score:.3f}")
                
                # Frame-by-frame results
                st.subheader("📹 Frame Analysis")
                for i, result in enumerate(results):
                    with st.expander(f"Frame {result['frame_number']} - {result['summary']}"):
                        display_results(result, show_expanders=False)
                
                # Clean up
                # Note: Per project constraint, we do not delete temp files here.
                # temp_path is left on disk.
    
    # ===== LIVE CAMERA (CCTV) MODE =====
    elif mode == "📹 Live Camera (CCTV)":
        st.header("📹 Live Camera Surveillance (CCTV Mode)")
        
        st.info("🎥 **Real-time monitoring** - Continuous analysis like a security camera")
        
        # Camera settings
        col1, col2 = st.columns(2)
        with col1:
            camera_index = st.number_input("Camera Index", min_value=0, max_value=5, value=0, 
                                          help="Usually 0 for default webcam, 1 for external camera")
        with col2:
            frame_skip = st.slider("Process every N frames (for speed)", 1, 10, 2,
                                  help="Skip frames to improve performance. 2 = process every 2nd frame")
        
        alert_on_unknown = st.checkbox("🚨 Alert on Unknown Faces", value=True,
                                      help="Show high-risk alert when unknown person is detected")
        
        # Placeholders for live feed
        video_placeholder = st.empty()
        metrics_placeholder = st.empty()
        alert_placeholder = st.empty()
        
        # Start/Stop buttons
        col1, col2 = st.columns([1, 1])
        with col1:
            start_button = st.button("▶️ Start Live Monitoring", type="primary", key="start_camera")
        with col2:
            stop_button = st.button("⏹️ Stop", key="stop_camera")
        
        # Session state for camera control
        if 'camera_running' not in st.session_state:
            st.session_state.camera_running = False
        
        if start_button:
            st.session_state.camera_running = True
        
        if stop_button:
            st.session_state.camera_running = False
            alert_placeholder.empty()
            metrics_placeholder.empty()
            video_placeholder.info("📹 Camera stopped. Click 'Start Live Monitoring' to resume.")
        
        # Main camera loop
        if st.session_state.camera_running:
            cap = cv2.VideoCapture(camera_index)
            
            if not cap.isOpened():
                st.error(f"❌ Could not open camera {camera_index}")
                st.session_state.camera_running = False
            else:
                frame_count = 0
                
                # Info message
                st.success("✅ Camera active - Monitoring in progress...")
                st.info("💡 Press 'Stop' button above to end monitoring")
                
                while st.session_state.camera_running:
                    ret, frame = cap.read()
                    
                    if not ret:
                        st.error("Failed to read from camera")
                        break
                    
                    frame_count += 1
                    
                    # Process frame
                    if frame_count % frame_skip == 0:
                        # Analyze frame
                        result = pipeline.process_image(frame, return_annotated=True)
                        
                        # Display annotated frame
                        annotated_frame = result['annotated_image']
                        annotated_rgb = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
                        video_placeholder.image(annotated_rgb, channels="RGB", use_column_width=True)
                        
                        # Display metrics
                        risk_level = result['risk_assessment']['risk_level']
                        threat_category = result['risk_assessment'].get('threat_category', 'UNKNOWN')
                        risk_score = result['risk_assessment']['overall_score']
                        identity = result['face_recognition']['identity']
                        threats = result['risk_assessment'].get('threats', {})
                        
                        with metrics_placeholder.container():
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                if risk_level == "CRITICAL":
                                    st.metric("🚨 Risk Level", risk_level, delta="EMERGENCY", delta_color="inverse")
                                elif risk_level == "HIGH":
                                    st.metric("🚨 Risk Level", risk_level, delta=None, delta_color="inverse")
                                elif risk_level == "MEDIUM":
                                    st.metric("⚠️ Risk Level", risk_level)
                                else:
                                    st.metric("✅ Risk Level", risk_level)
                            
                            with col2:
                                st.metric("Threat Type", threat_category)
                            
                            with col3:
                                st.metric("Identity", identity)
                            
                            with col4:
                                st.metric("Frame", frame_count)
                        
                        # Specific threat alerts
                        if threats.get('has_weapon'):
                            weapons = ', '.join(threats.get('weapons_detected', []))
                            alert_placeholder.error(f"🚨🛑 **EMERGENCY - WEAPON DETECTED**: {weapons}")
                        elif threat_category == "MASKED UNKNOWN":
                            alert_placeholder.error("🚨 **HIGH RISK**: Masked unknown person detected!")
                        elif threat_category == "UNKNOWN PERSON":
                            alert_placeholder.warning("👤 **UNKNOWN PERSON ALERT**: Individual not in database!")
                        elif threat_category == "MASKED PERSON":
                            alert_placeholder.warning(f"🎭 **MASKED PERSON**: {identity}")
                        elif threat_category == "SUSPICIOUS ACTIVITY":
                            reasons = ", ".join(result['risk_assessment']['reasons'])
                            alert_placeholder.warning(f"⚠️ **SUSPICIOUS ACTIVITY**: {reasons}")
                        elif threat_category == "DEEPFAKE":
                            alert_placeholder.error("🎭 **DEEPFAKE DETECTED**: Manipulated image!")
                        elif risk_level == "HIGH":
                            reasons = ", ".join(result['risk_assessment']['reasons'])
                            alert_placeholder.error(f"🚨 **HIGH RISK**: {reasons}")
                        elif risk_level == "MEDIUM":
                            alert_placeholder.warning(f"⚠️ **MODERATE RISK**: {result['summary']}")
                        else:
                            alert_placeholder.empty()
                    
                    else:
                        # Just display frame without processing
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        video_placeholder.image(frame_rgb, channels="RGB", use_column_width=True)
                    
                    # Check if stop was pressed
                    if not st.session_state.camera_running:
                        break
                    
                    # Small delay to prevent overwhelming
                    time.sleep(0.01)
                
                cap.release()
                st.session_state.camera_running = False
    
    # ===== FACE DATABASE MODE =====
    elif mode == "👥 Face Database":
        st.header("👥 Face Database Management")
        
        # Display current identities
        identities = pipeline.face_recognizer.list_identities()
        st.subheader(f"📋 Current Database ({len(identities)} identities)")
        
        if identities:
            for name in identities:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"👤 {name}")
                with col2:
                    if st.button("🗑️", key=f"del_{name}"):
                        pipeline.face_recognizer.remove_identity(name)
                        st.rerun()
        else:
            st.info("No identities in database yet")
        
        st.divider()
        
        # Add new identity
        st.subheader("➕ Add New Identity")
        
        new_name = st.text_input("Enter name/identifier")
        
        # Input method for face photo
        face_input_method = st.radio(
            "Select Photo Input Method",
            ["📁 Upload Photo", "📷 Take Photo with Camera"],
            horizontal=True,
            key="face_input_method"
        )
        
        new_image_np = None
        
        if face_input_method == "📁 Upload Photo":
            new_image = st.file_uploader(
                "Upload face image",
                type=["jpg", "jpeg", "png"],
                help="Upload a clear face image or drag & drop here"
            )
            
            if new_image is not None:
                image = Image.open(new_image)
                new_image_np = pil_to_cv2(image)
                # Preview the uploaded photo
                st.image(image, caption="Preview", width=300)
        
        else:  # Camera input
            camera_face = st.camera_input("Take a photo of your face")
            
            if camera_face is not None:
                image = Image.open(camera_face)
                new_image_np = pil_to_cv2(image)
        
        if st.button("➕ Add to Database", type="primary", disabled=not (new_name and new_image_np is not None)):
            with st.spinner(f"Adding {new_name}..."):
                success = pipeline.face_recognizer.add_identity(new_image_np, new_name)
            
            if success:
                st.success(f"✅ {new_name} added successfully!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Failed to add identity.")
                st.warning("**Possible issues:**")
                st.write("1. InsightFace not installed - Install with: `pip install insightface onnxruntime`")
                st.write("2. No face detected in the image - Try better lighting or different angle")
                st.write("3. Check the terminal/console for detailed error messages")


# ===== Run App =====
if __name__ == "__main__":
    main()
