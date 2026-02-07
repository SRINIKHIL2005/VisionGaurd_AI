"""
Image Utilities Module

Helper functions for image/video processing using OpenCV and PIL.
Handles format conversions, preprocessing, visualization, and I/O.

Tech Stack:
- OpenCV - Image/video processing
- PIL - Image handling
- NumPy - Array operations
"""

import cv2
import numpy as np
from PIL import Image
from typing import Union, Tuple, List, Optional
import os


def load_image(path: str) -> np.ndarray:
    """
    Load image from file path.
    
    Args:
        path: Image file path
        
    Returns:
        Image as BGR numpy array
    """
    image = cv2.imread(path)
    if image is None:
        raise ValueError(f"Cannot load image from: {path}")
    return image


def save_image(image: np.ndarray, path: str) -> bool:
    """
    Save image to file.
    
    Args:
        image: Image array (BGR format)
        path: Output file path
        
    Returns:
        Success status
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return cv2.imwrite(path, image)


def resize_image(
    image: np.ndarray,
    width: Optional[int] = None,
    height: Optional[int] = None,
    max_size: Optional[Tuple[int, int]] = None,
    keep_aspect_ratio: bool = True
) -> np.ndarray:
    """
    Resize image with various options.
    
    Args:
        image: Input image
        width: Target width
        height: Target height
        max_size: Maximum (width, height)
        keep_aspect_ratio: Maintain aspect ratio
        
    Returns:
        Resized image
    """
    h, w = image.shape[:2]
    
    if max_size:
        # Resize to fit within max_size
        max_w, max_h = max_size
        scale = min(max_w / w, max_h / h)
        if scale < 1:
            new_w = int(w * scale)
            new_h = int(h * scale)
            return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return image
    
    if width and height:
        if keep_aspect_ratio:
            scale = min(width / w, height / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    
    if width:
        scale = width / w
        new_h = int(h * scale)
        return cv2.resize(image, (width, new_h), interpolation=cv2.INTER_AREA)
    
    if height:
        scale = height / h
        new_w = int(w * scale)
        return cv2.resize(image, (new_w, height), interpolation=cv2.INTER_AREA)
    
    return image


def bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    """Convert BGR to RGB"""
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def rgb_to_bgr(image: np.ndarray) -> np.ndarray:
    """Convert RGB to BGR"""
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


def pil_to_cv2(pil_image: Image.Image) -> np.ndarray:
    """Convert PIL Image to OpenCV format (BGR)"""
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)


def cv2_to_pil(cv2_image: np.ndarray) -> Image.Image:
    """Convert OpenCV image (BGR) to PIL Image (RGB)"""
    return Image.fromarray(cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB))


def draw_circle(
    image: np.ndarray,
    bbox: List[int],
    label: str = "",
    confidence: Optional[float] = None,
    color: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
    font_scale: float = 0.6
) -> np.ndarray:
    """
    Draw circle around face/person with label.
    
    Args:
        image: Input image (will be modified)
        bbox: [x1, y1, x2, y2]
        label: Person label/identity
        confidence: Confidence score
        color: Circle color (B, G, R)
        thickness: Circle line thickness
        font_scale: Font size scale
        
    Returns:
        Image with drawn circle
    """
    x1, y1, x2, y2 = bbox
    
    # Calculate center and radius
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    radius = max((x2 - x1), (y2 - y1)) // 2
    
    # Draw circle
    cv2.circle(image, (center_x, center_y), radius, color, thickness)
    
    # Prepare label text
    if confidence is not None:
        text = f"{label} {confidence:.2f}"
    else:
        text = label
    
    if text:
        # Get text size
        (text_width, text_height), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        
        # Position text above circle
        text_y = y1 - 10
        text_x = center_x - text_width // 2
        
        # Draw background rectangle for text
        cv2.rectangle(
            image,
            (text_x - 2, text_y - text_height - baseline - 5),
            (text_x + text_width + 2, text_y),
            color,
            -1
        )
        
        # Draw text
        cv2.putText(
            image,
            text,
            (text_x, text_y - baseline - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            thickness - 1
        )
    
    return image


def draw_bbox(
    image: np.ndarray,
    bbox: List[int],
    label: str = "",
    confidence: Optional[float] = None,
    color: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
    font_scale: float = 0.6
) -> np.ndarray:
    """
    Draw bounding box with label on image.
    
    Args:
        image: Input image (will be modified)
        bbox: [x1, y1, x2, y2]
        label: Object label
        confidence: Confidence score
        color: Box color (B, G, R)
        thickness: Box line thickness
        font_scale: Font size scale
        
    Returns:
        Image with drawn bbox
    """
    x1, y1, x2, y2 = bbox
    
    # Draw rectangle
    cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
    
    # Prepare label text
    if confidence is not None:
        text = f"{label} {confidence:.2f}"
    else:
        text = label
    
    if text:
        # Get text size
        (text_width, text_height), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        
        # Draw background rectangle for text
        cv2.rectangle(
            image,
            (x1, y1 - text_height - baseline - 5),
            (x1 + text_width, y1),
            color,
            -1
        )
        
        # Draw text
        cv2.putText(
            image,
            text,
            (x1, y1 - baseline - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            thickness - 1
        )
    
    return image


def draw_multiple_bboxes(
    image: np.ndarray,
    detections: List[dict],
    bbox_key: str = 'bbox',
    label_key: str = 'label',
    conf_key: str = 'confidence',
    color: Tuple[int, int, int] = (0, 255, 0)
) -> np.ndarray:
    """
    Draw multiple bounding boxes from detection results.
    
    Args:
        image: Input image
        detections: List of detection dicts
        bbox_key: Key for bbox in dict
        label_key: Key for label in dict
        conf_key: Key for confidence in dict
        color: Default color
        
    Returns:
        Annotated image
    """
    img_copy = image.copy()
    
    for det in detections:
        bbox = det.get(bbox_key)
        label = det.get(label_key, "")
        conf = det.get(conf_key)
        
        if bbox:
            draw_bbox(img_copy, bbox, label, conf, color)
    
    return img_copy


def draw_text(
    image: np.ndarray,
    text: str,
    position: Tuple[int, int],
    font_scale: float = 1.0,
    color: Tuple[int, int, int] = (255, 255, 255),
    thickness: int = 2,
    bg_color: Optional[Tuple[int, int, int]] = None
) -> np.ndarray:
    """
    Draw text on image with optional background.
    
    Args:
        image: Input image
        text: Text to draw
        position: (x, y) position
        font_scale: Font size scale
        color: Text color
        thickness: Text thickness
        bg_color: Background color (optional)
        
    Returns:
        Image with text
    """
    x, y = position
    
    # Get text size
    (text_width, text_height), baseline = cv2.getTextSize(
        text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
    )
    
    # Draw background if specified
    if bg_color:
        cv2.rectangle(
            image,
            (x, y - text_height - baseline),
            (x + text_width, y + baseline),
            bg_color,
            -1
        )
    
    # Draw text
    cv2.putText(
        image,
        text,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        color,
        thickness
    )
    
    return image


def extract_frames(
    video_path: str,
    output_dir: str,
    frame_skip: int = 1,
    max_frames: Optional[int] = None
) -> List[str]:
    """
    Extract frames from video file.
    
    Args:
        video_path: Path to video
        output_dir: Directory to save frames
        frame_skip: Extract every Nth frame
        max_frames: Maximum frames to extract
        
    Returns:
        List of saved frame paths
    """
    os.makedirs(output_dir, exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    
    frame_paths = []
    frame_count = 0
    saved_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        # Skip frames
        if frame_count % frame_skip != 0:
            continue
        
        # Save frame
        frame_path = os.path.join(output_dir, f"frame_{saved_count:06d}.jpg")
        cv2.imwrite(frame_path, frame)
        frame_paths.append(frame_path)
        saved_count += 1
        
        # Check max frames
        if max_frames and saved_count >= max_frames:
            break
    
    cap.release()
    print(f"✅ Extracted {saved_count} frames to {output_dir}")
    
    return frame_paths


def create_video_from_frames(
    frame_paths: List[str],
    output_path: str,
    fps: int = 30
) -> bool:
    """
    Create video from image frames.
    
    Args:
        frame_paths: List of frame image paths
        output_path: Output video path
        fps: Frames per second
        
    Returns:
        Success status
    """
    if not frame_paths:
        return False
    
    # Read first frame to get dimensions
    first_frame = cv2.imread(frame_paths[0])
    if first_frame is None:
        return False
    
    height, width = first_frame.shape[:2]
    
    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    for frame_path in frame_paths:
        frame = cv2.imread(frame_path)
        if frame is not None:
            writer.write(frame)
    
    writer.release()
    print(f"✅ Video saved to {output_path}")
    
    return True


def stack_images(images: List[np.ndarray], direction: str = 'horizontal') -> np.ndarray:
    """
    Stack multiple images horizontally or vertically.
    
    Args:
        images: List of images (must have same dimensions)
        direction: 'horizontal' or 'vertical'
        
    Returns:
        Stacked image
    """
    if direction == 'horizontal':
        return np.hstack(images)
    else:
        return np.vstack(images)


def add_overlay(
    image: np.ndarray,
    overlay: np.ndarray,
    position: Tuple[int, int],
    alpha: float = 0.7
) -> np.ndarray:
    """
    Add semi-transparent overlay to image.
    
    Args:
        image: Base image
        overlay: Overlay image
        position: (x, y) position
        alpha: Transparency (0-1)
        
    Returns:
        Image with overlay
    """
    x, y = position
    h, w = overlay.shape[:2]
    
    # Ensure overlay fits
    if y + h > image.shape[0] or x + w > image.shape[1]:
        return image
    
    # Blend
    roi = image[y:y+h, x:x+w]
    blended = cv2.addWeighted(roi, 1-alpha, overlay, alpha, 0)
    image[y:y+h, x:x+w] = blended
    
    return image


def normalize_image(image: np.ndarray) -> np.ndarray:
    """Normalize image to 0-255 range"""
    return cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)


def enhance_contrast(image: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
    """Enhance image contrast using CLAHE"""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    l = clahe.apply(l)
    
    enhanced = cv2.merge([l, a, b])
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)


if __name__ == "__main__":
    print("🧪 Testing Image Utilities...\n")
    
    # Create test image
    test_img = np.zeros((480, 640, 3), dtype=np.uint8)
    test_img[:] = (100, 150, 200)
    
    # Test drawing
    test_img = draw_bbox(test_img, [100, 100, 300, 300], "Test Object", 0.95)
    test_img = draw_text(test_img, "VisionGuard AI", (20, 40), bg_color=(0, 0, 0))
    
    print("✅ Image utilities working correctly!")
    print(f"   Image shape: {test_img.shape}")
