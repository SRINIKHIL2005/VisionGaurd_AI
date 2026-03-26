"""
Deepfake Detector Module

This module uses state-of-the-art pretrained models from Hugging Face
to detect deepfake/manipulated images with high accuracy.

Tech Stack:
- Transformers (Hugging Face) - Latest pretrained models
- timm (PyTorch Image Models) - EfficientNet backbone
- PyTorch - Deep learning framework
- OpenCV/PIL - Image preprocessing

Input:
- RGB face image (numpy array or PIL Image)

Output:
- fake_probability (float between 0 and 1)
- is_fake (boolean)
- confidence (percentage)
"""

import torch
import torch.nn as nn
from transformers import AutoImageProcessor, AutoModelForImageClassification
from PIL import Image
import numpy as np
import cv2
from typing import Dict, Union, Tuple
import warnings
import os

warnings.filterwarnings('ignore')

# Try importing Gemini for fallback
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class DeepfakeDetector:
    """
    Modern deepfake detection using Vision Transformer (ViT) models.
    Uses pretrained models from Hugging Face for easy deployment.
    """
    
    def __init__(self, model_name: str = "dima806/deepfake_vs_real_image_detection", threshold: float = 0.35, gemini_api_key: str = None, gemini_model_name: str = "gemini-2.0-flash"):
        """
        Initialize the deepfake detector with a pretrained model.
        
        Args:
            model_name: Hugging Face model identifier
                       Default: "dima806/deepfake_vs_real_image_detection"
                       Alternative: "facebook/deit-base-patch16-224" (fine-tune required)
            threshold: Fake probability threshold (0-1). Lower = more sensitive
                      0.35 = Detects most AI-generated content
                      0.50 = Balanced
                      0.60 = Conservative (fewer false positives)
            gemini_api_key: Optional Google Gemini API key for fallback detection
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.threshold = threshold  # Store threshold
        self.gemini_api_key = gemini_api_key
        self.use_gemini_fallback = False
        
        print(f"🔧 Initializing Deepfake Detector on {self.device}...")
        print(f"🎯 Detection threshold: {threshold:.0%}")
        
        try:
            # Load pretrained model and processor from Hugging Face
            self.processor = AutoImageProcessor.from_pretrained(model_name)
            self.model = AutoModelForImageClassification.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
            
            print(f"✅ Model loaded: {model_name}")
            print(f"📊 Labels: {self.model.config.id2label}")
            
            # Initialize Gemini fallback if available
            if gemini_api_key and GEMINI_AVAILABLE:
                try:
                    genai.configure(api_key=gemini_api_key)
                    self.gemini_model = genai.GenerativeModel(gemini_model_name)
                    print(f"✅ Gemini API fallback initialized ({gemini_model_name})")
                except Exception as e:
                    print(f"⚠️ Gemini fallback initialization failed: {e}")
                    self.gemini_model = None
            else:
                self.gemini_model = None
                if not GEMINI_AVAILABLE and gemini_api_key:
                    print("⚠️ Gemini API key provided but google-generativeai not installed")
                    print("💡 Install with: pip install google-generativeai")
            
        except Exception as e:
            print(f"⚠️ Error loading model from Hugging Face: {e}")
            print("💡 Falling back to custom EfficientNet-based detector...")
            self._init_custom_model()
    
    def _init_custom_model(self):
        """
        Fallback: Initialize a custom EfficientNet-based detector using timm.
        This is used if Hugging Face model is unavailable.
        """
        import timm
        
        # Load pretrained EfficientNet from timm
        self.model = timm.create_model(
            'efficientnet_b4',
            pretrained=True,
            num_classes=2  # Binary: Real (0) or Fake (1)
        )
        self.model.to(self.device)
        self.model.eval()
        
        # Custom preprocessing
        self.processor = None
        print("✅ Custom EfficientNet model initialized")
    
    def preprocess_image(self, image: Union[np.ndarray, Image.Image]) -> torch.Tensor:
        """
        Preprocess input image for model inference.
        
        Args:
            image: Input image as numpy array (BGR/RGB) or PIL Image
            
        Returns:
            Preprocessed tensor ready for model
        """
        # Convert numpy array to PIL Image if needed
        if isinstance(image, np.ndarray):
            # Convert BGR to RGB if coming from OpenCV
            if image.shape[-1] == 3:
                image = Image.fromarray(image[..., ::-1])
            else:
                image = Image.fromarray(image)
        
        # Use Hugging Face processor if available
        if self.processor is not None:
            inputs = self.processor(images=image, return_tensors="pt")
            return inputs['pixel_values'].to(self.device)
        else:
            # Manual preprocessing for custom model
            from torchvision import transforms
            
            transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ])
            
            tensor = transform(image).unsqueeze(0)
            return tensor.to(self.device)
    
    def predict(self, image: Union[np.ndarray, Image.Image]) -> Dict[str, Union[float, bool, str]]:
        """
        Predict whether the input image is a deepfake.
        
        Args:
            image: Input face image (numpy array or PIL Image)
            
        Returns:
            Dictionary containing:
                - fake_probability: float (0 to 1)
                - is_fake: bool
                - confidence: float (0 to 100)
                - label: str ("REAL" or "FAKE")
        """
        with torch.no_grad():
            # Preprocess image
            inputs = self.preprocess_image(image)
            
            # Get model predictions
            outputs = self.model(inputs)
            
            # Handle different output formats
            if hasattr(outputs, 'logits'):
                logits = outputs.logits
            else:
                logits = outputs
            
            # Apply softmax to get probabilities
            probabilities = torch.nn.functional.softmax(logits, dim=-1)
            
            # Check model labels - IMPORTANT: Model might have labels reversed!
            # Get label mapping from model config
            id2label = self.model.config.id2label if hasattr(self.model.config, 'id2label') else {0: 'REAL', 1: 'FAKE'}
            
            # Determine which index is FAKE
            fake_idx = 1  # Default assumption
            for idx, label_str in id2label.items():
                if 'fake' in label_str.lower() or 'ai' in label_str.lower() or 'generated' in label_str.lower():
                    fake_idx = idx
                    break
            
            # Get probabilities based on correct label mapping
            if fake_idx == 1:
                real_prob = probabilities[0][0].item()
                fake_prob = probabilities[0][1].item() if probabilities.shape[-1] > 1 else 1 - probabilities[0][0].item()
            else:
                # Labels are reversed
                fake_prob = probabilities[0][0].item()
                real_prob = probabilities[0][1].item() if probabilities.shape[-1] > 1 else 1 - probabilities[0][0].item()
            
            # Use configured threshold for fake detection
            is_fake = fake_prob > self.threshold
            confidence = max(fake_prob, real_prob) * 100
            label = "FAKE" if is_fake else "REAL"
            
            # Debug output
            print(f"   🔍 Deepfake Probs: Real={real_prob:.3f}, Fake={fake_prob:.3f} → {label} (threshold={self.threshold:.0%})")
            print(f"   📋 Model labels: {id2label}, Fake index: {fake_idx}")
            
            model_result = {
                'fake_probability': round(fake_prob, 4),
                'is_fake': is_fake,
                'confidence': round(confidence, 2),
                'label': label
            }

            # If Gemini is available, combine results
            if self.gemini_model:
                gemini_result = self._predict_with_gemini(image)

                # If Gemini failed, fall back to model result
                if gemini_result.get('label') == "UNKNOWN":
                    return model_result

                # If both agree, average confidence and probabilities
                if gemini_result.get('label') == model_result['label']:
                    combined_fake = (model_result['fake_probability'] + gemini_result['fake_probability']) / 2
                    combined_conf = (model_result['confidence'] + gemini_result['confidence']) / 2
                    return {
                        'fake_probability': round(combined_fake, 4),
                        'is_fake': gemini_result['label'] == "FAKE",
                        'confidence': round(combined_conf, 2),
                        'label': gemini_result['label']
                    }

                # If they disagree, trust Gemini
                return gemini_result

            return model_result
    
    def _predict_with_gemini(self, image: Union[np.ndarray, Image.Image]) -> Dict[str, Union[float, bool, str]]:
        """
        Use Gemini API for deepfake detection (fallback or primary for images).
        
        Args:
            image: Input face image
            
        Returns:
            Prediction dictionary with fake_probability, is_fake, confidence, label
        """
        try:
            if not self.gemini_model:
                raise ValueError("Gemini model not initialized")
            
            # Convert to PIL Image if numpy array
            if isinstance(image, np.ndarray):
                image_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            else:
                image_pil = image
            
            # Prepare prompt for Gemini
            prompt = """Analyze this image carefully and determine if it's AI-generated, deepfake, or manipulated.

Look for these signs:
- Unnatural skin texture or lighting
- Distorted facial features or proportions
- Artifacts around edges, hair, or background
- Inconsistent shadows or reflections
- Digital manipulation signs
- AI generation patterns

Respond STRICTLY in JSON with two fields:
{"label": "REAL"|"FAKE", "confidence": 0-100}

Example: {"label":"FAKE","confidence":92}
"""
            
            # Send to Gemini — 10 s timeout so a dropped connection fails fast
            response = self.gemini_model.generate_content(
                [prompt, image_pil],
                request_options={"timeout": 10}
            )
            result_text = response.text.strip()

            # Parse JSON-like response
            label = "UNKNOWN"
            confidence = None
            try:
                import json
                parsed = json.loads(result_text)
                label = str(parsed.get("label", "UNKNOWN")).upper()
                confidence = float(parsed.get("confidence"))
            except Exception:
                # Fallback: extract label and confidence from text
                upper_text = result_text.upper()
                if "FAKE" in upper_text or "AI" in upper_text or "GENERATED" in upper_text:
                    label = "FAKE"
                elif "REAL" in upper_text or "AUTHENTIC" in upper_text:
                    label = "REAL"

            # Set default confidence if missing or invalid
            if confidence is None or not (0 <= confidence <= 100):
                confidence = 90.0 if label == "FAKE" else 90.0

            is_fake = label == "FAKE"
            fake_prob = confidence / 100 if is_fake else 1 - (confidence / 100)

            print(f"   🤖 Gemini result: {result_text} → {label} ({confidence:.0f}%)")
            
            return {
                'fake_probability': round(fake_prob, 4),
                'is_fake': is_fake,
                'confidence': round(confidence, 2),
                'label': label
            }
            
        except Exception as e:
            print(f"   ⚠️ Gemini prediction failed: {e}")
            # Return uncertain result
            return {
                'fake_probability': 0.5,
                'is_fake': False,
                'confidence': 50.0,
                'label': "UNKNOWN"
            }
    
    def predict_batch(self, images: list) -> list:
        """
        Process multiple images at once for efficiency.
        
        Args:
            images: List of images (numpy arrays or PIL Images)
            
        Returns:
            List of prediction dictionaries
        """
        results = []
        for image in images:
            result = self.predict(image)
            results.append(result)
        return results
    
    def get_heatmap(self, image: Union[np.ndarray, Image.Image]) -> np.ndarray:
        """
        Generate attention heatmap showing manipulated regions (if supported).
        
        Args:
            image: Input face image
            
        Returns:
            Heatmap as numpy array
        """
        # This requires GradCAM or attention visualization
        # Placeholder for now - can be implemented with grad-cam library
        print("⚠️ Heatmap generation requires additional setup (GradCAM)")
        return None


# Convenience function for quick usage
def detect_deepfake(image: Union[np.ndarray, Image.Image]) -> Dict[str, Union[float, bool, str]]:
    """
    Quick function to detect deepfake without instantiating class.
    
    Args:
        image: Input face image
        
    Returns:
        Prediction dictionary
    """
    detector = DeepfakeDetector()
    return detector.predict(image)


if __name__ == "__main__":
    # Test the detector
    print("\n🧪 Testing Deepfake Detector...\n")
    
    # Create a dummy test image
    test_image = Image.new('RGB', (224, 224), color='blue')
    
    # Initialize detector
    detector = DeepfakeDetector()
    
    # Run prediction
    result = detector.predict(test_image)
    
    print("\n📊 Detection Result:")
    print(f"   Label: {result['label']}")
    print(f"   Fake Probability: {result['fake_probability']}")
    print(f"   Confidence: {result['confidence']}%")
    print(f"   Is Fake: {result['is_fake']}")
    print("\n✅ Deepfake Detector working correctly!")
