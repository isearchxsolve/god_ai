#!/usr/bin/env python3
"""
Batch inference example
Usage: python batch_inference.py <folder_path>
"""
import onnxruntime as ort
import numpy as np
from PIL import Image
from pathlib import Path
import sys

def preprocess_image(image_path):
    """Load and preprocess image"""
    img = Image.open(image_path).convert("RGB").resize((224, 224))
    img_array = np.array(img, dtype=np.float32) / 255.0
    img_array = (img_array - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    img_array = np.transpose(img_array, (2, 0, 1))
    img_array = np.expand_dims(img_array, axis=0)
    return img_array.astype(np.float32)

def batch_predict(folder_path, model_path="toxic_detector.onnx"):
    """Process all images in a folder"""
    session = ort.InferenceSession(model_path)
    input_name = session.get_inputs()[0].name
    
    folder = Path(folder_path)
    image_files = list(folder.glob("*.jpg")) + list(folder.glob("*.png"))
    
    results = []
    for idx, img_path in enumerate(image_files, 1):
        try:
            img_array = preprocess_image(img_path)
            outputs = session.run(None, {input_name: img_array})
            predictions = outputs[0][0]
            
            is_safe = predictions[0] > predictions[1]
            results.append({
                "file": img_path.name,
                "is_safe": bool(is_safe),
                "safe_score": float(predictions[0]),
                "unsafe_score": float(predictions[1])
            })
            
            if idx % 10 == 0:
                print(f"Processed {idx}/{len(image_files)} images...")
                
        except Exception as e:
            print(f"Error processing {img_path.name}: {e}")
    
    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python batch_inference.py <folder_path>")
        sys.exit(1)
    
    folder_path = sys.argv[1]
    results = batch_predict(folder_path)
    
    print(f"\nProcessed {len(results)} images")
    safe_count = sum(1 for r in results if r["is_safe"])
    print(f"Safe: {safe_count}, Unsafe: {len(results) - safe_count}")
    
    # Save results
    import json
    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Results saved to results.json")
