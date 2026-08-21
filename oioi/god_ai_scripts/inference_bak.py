#!/usr/bin/env python3
"""
ONNX Runtime Inference Example
Usage: python inference.py <image_path>
"""
import onnxruntime as ort
import numpy as np
from PIL import Image
import sys

def preprocess_image(image_path):
    """Load and preprocess image for EfficientNet"""
    img = Image.open(image_path).convert("RGB").resize((224, 224))
    
    # Convert to numpy array and normalize
    img_array = np.array(img, dtype=np.float32) / 255.0
    
    # ImageNet normalization
    mean = np.array([0.485, 0.456, 0.406])
    std = np.array([0.229, 0.224, 0.225])
    img_array = (img_array - mean) / std
    
    # Convert HWC to NCHW format
    img_array = np.transpose(img_array, (2, 0, 1))
    img_array = np.expand_dims(img_array, axis=0)
    
    return img_array.astype(np.float32)

def predict(image_path, model_path="toxic_detector.onnx"):
    """Run inference on an image"""
    # Load model
    session = ort.InferenceSession(model_path)
    input_name = session.get_inputs()[0].name
    
    # Preprocess image
    img_array = preprocess_image(image_path)
    
    # Run inference
    outputs = session.run(None, {input_name: img_array})
    predictions = outputs[0][0]  # [safe_score, unsafe_score]
    
    # Get result
    safe_score = predictions[0]
    unsafe_score = predictions[1]
    is_safe = safe_score > unsafe_score
    
    return {
        "is_safe": bool(is_safe),
        "safe_score": float(safe_score),
        "unsafe_score": float(unsafe_score),
        "confidence": float(max(safe_score, unsafe_score))
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inference.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    result = predict(image_path)
    
    print(f"\nImage: {image_path}")
    print(f"Safe: {result['is_safe']}")
    print(f"Safe score: {result['safe_score']:.4f}")
    print(f"Unsafe score: {result['unsafe_score']:.4f}")
    print(f"Confidence: {result['confidence']:.4f}")
