import tensorflow as tf
import numpy as np
from ultralytics import YOLO
from PIL import Image, ImageOps
from pathlib import Path
import cv2

# === CONFIGURATION ===
PT_MODEL_PATH = "runs/detect/yolo_ui_s_model/weights/best.pt"
TFLITE_MODEL_PATH = "runs/detect/yolo_ui_s_model/weights/best_saved_model/best_float32.tflite"
IMAGE_PATH = "shits.jpg"
IMG_SIZE = 640

def letterbox_image(image, size):
    """Resize image with padding to fit model input size while maintaining aspect ratio."""
    iw, ih = image.size
    w, h = size
    scale = min(w / iw, h / ih)
    nw = int(iw * scale)
    nh = int(ih * scale)

    image = image.resize((nw, nh), Image.BICUBIC)
    
    # Create new image with gray padding (114, 114, 114)
    new_image = Image.new('RGB', size, (114, 114, 114))
    new_image.paste(image, ((w - nw) // 2, (h - nh) // 2))
    
    return new_image, scale, (w - nw) // 2, (h - nh) // 2

def sigmoid(x):
    """Apply sigmoid activation"""
    return 1 / (1 + np.exp(-np.clip(x, -100, 100)))

def run_pytorch_inference(model_path, image_path):
    """Run PyTorch model and return raw details"""
    print("\n" + "="*70)
    print("🔵 PYTORCH MODEL ANALYSIS")
    print("="*70)
    
    try:
        model = YOLO(model_path)
        pil_img = Image.open(image_path)
        pil_img = ImageOps.exif_transpose(pil_img)
        
        # Run inference with verbose output
        results = model.predict(pil_img, conf=0.005, imgsz=IMG_SIZE, verbose=True)
        result = results[0]
        
        boxes = result.boxes.xyxy.cpu().numpy()
        scores = result.boxes.conf.cpu().numpy()
        
        print(f"\n📊 Detection Summary:")
        print(f"   Total detections: {len(boxes)}")
        if len(scores) > 0:
            print(f"   Confidence range: {scores.min():.4f} - {scores.max():.4f}")
            print(f"   Mean confidence: {scores.mean():.4f}")
        
        print(f"\n📋 Individual Detections:")
        for i, (box, score) in enumerate(zip(boxes, scores)):
            x1, y1, x2, y2 = box
            w, h = x2 - x1, y2 - y1
            print(f"   [{i+1}] Conf: {score:.4f} | Box: ({int(x1)}, {int(y1)}, {int(x2)}, {int(y2)}) | Size: {int(w)}x{int(h)}")
        
        return boxes, scores
        
    except Exception as e:
        print(f"❌ PyTorch Error: {e}")
        return None, None

def run_tflite_inference(model_path, image_path, apply_sigmoid=False):
    """Run TFLite model and return raw details"""
    print("\n" + "="*70)
    print(f"🟢 TFLITE MODEL ANALYSIS {'(WITH SIGMOID)' if apply_sigmoid else '(RAW)'}")
    print("="*70)
    
    try:
        # Load interpreter
        interpreter = tf.lite.Interpreter(model_path=model_path)
        interpreter.allocate_tensors()
        
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        input_shape = input_details[0]['shape']
        input_h, input_w = input_shape[1], input_shape[2]
        
        print(f"ℹ️  Input shape: {input_shape}")
        print(f"ℹ️  Input dtype: {input_details[0]['dtype']}")
        print(f"ℹ️  Output shape: {output_details[0]['shape']}")
        print(f"ℹ️  Output dtype: {output_details[0]['dtype']}")
        
        # Load and preprocess image
        pil_img = Image.open(image_path)
        pil_img = ImageOps.exif_transpose(pil_img)
        orig_w, orig_h = pil_img.size
        
        # Letterbox
        input_img, scale, pad_x, pad_y = letterbox_image(pil_img, (input_w, input_h))
        
        # Normalize
        input_data = np.array(input_img, dtype=np.float32) / 255.0
        input_data = np.expand_dims(input_data, axis=0)
        
        print(f"\n📊 Input Statistics:")
        print(f"   Min: {input_data.min():.4f}")
        print(f"   Max: {input_data.max():.4f}")
        print(f"   Mean: {input_data.mean():.4f}")
        print(f"   Std: {input_data.std():.4f}")
        
        # Run inference
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        
        # Get output
        output_data = interpreter.get_tensor(output_details[0]['index'])[0]
        
        # Transpose if needed
        if output_data.shape[0] < output_data.shape[1]:
            output_data = output_data.T
        
        print(f"\n📊 Raw Output Statistics:")
        print(f"   Output shape: {output_data.shape}")
        print(f"   Confidence column (raw) - Min: {output_data[:, 4].min():.4f}, Max: {output_data[:, 4].max():.4f}, Mean: {output_data[:, 4].mean():.4f}")
        
        # Apply sigmoid if requested
        if apply_sigmoid:
            output_data[:, 4] = sigmoid(output_data[:, 4])
            print(f"   Confidence column (sigmoid) - Min: {output_data[:, 4].min():.4f}, Max: {output_data[:, 4].max():.4f}, Mean: {output_data[:, 4].mean():.4f}")
        
        # Analyze detection distribution
        thresholds = [0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 0.75]
        print(f"\n📊 Detection Count by Threshold:")
        for thresh in thresholds:
            count = (output_data[:, 4] > thresh).sum()
            print(f"   > {thresh:.3f}: {count} detections")
        
        # Get top detections
        sorted_indices = np.argsort(output_data[:, 4])[::-1][:10]
        print(f"\n📋 Top 10 Detections:")
        
        boxes = []
        scores = []
        
        for rank, idx in enumerate(sorted_indices):
            score = output_data[idx, 4]
            cx, cy, w, h = output_data[idx, :4]
            
            # Denormalize if needed
            if cx < 1.0 and w < 1.0:
                cx *= input_w
                cy *= input_h
                w *= input_w
                h *= input_h
            
            # Transform to original image space
            x_padded = cx - w / 2
            y_padded = cy - h / 2
            
            x_orig = (x_padded - pad_x) / scale
            y_orig = (y_padded - pad_y) / scale
            w_orig = w / scale
            h_orig = h / scale
            
            x1, y1 = int(x_orig), int(y_orig)
            x2, y2 = int(x_orig + w_orig), int(y_orig + h_orig)
            
            print(f"   [{rank+1}] Conf: {score:.4f} | Box: ({x1}, {y1}, {x2}, {y2}) | Size: {x2-x1}x{y2-y1}")
            
            if score > 0.005:
                boxes.append([x1, y1, x2, y2])
                scores.append(score)
        
        return np.array(boxes), np.array(scores)
        
    except Exception as e:
        print(f"❌ TFLite Error: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def compare_models():
    """Run diagnostic comparison between PyTorch and TFLite models"""
    print("\n" + "="*70)
    print("🔬 MODEL DIAGNOSTIC COMPARISON TOOL")
    print("="*70)
    print(f"📷 Image: {IMAGE_PATH}")
    print(f"🎯 PyTorch Model: {PT_MODEL_PATH}")
    print(f"🎯 TFLite Model: {TFLITE_MODEL_PATH}")
    
    # Check files exist
    if not Path(PT_MODEL_PATH).exists():
        print(f"❌ PyTorch model not found: {PT_MODEL_PATH}")
        return
    if not Path(TFLITE_MODEL_PATH).exists():
        print(f"❌ TFLite model not found: {TFLITE_MODEL_PATH}")
        return
    if not Path(IMAGE_PATH).exists():
        print(f"❌ Image not found: {IMAGE_PATH}")
        return
    
    # Run PyTorch inference
    pt_boxes, pt_scores = run_pytorch_inference(PT_MODEL_PATH, IMAGE_PATH)
    
    # Run TFLite inference (raw)
    tflite_boxes_raw, tflite_scores_raw = run_tflite_inference(TFLITE_MODEL_PATH, IMAGE_PATH, apply_sigmoid=False)
    
    # Run TFLite inference (with sigmoid)
    tflite_boxes_sig, tflite_scores_sig = run_tflite_inference(TFLITE_MODEL_PATH, IMAGE_PATH, apply_sigmoid=True)
    
    # Final comparison
    print("\n" + "="*70)
    print("📊 FINAL COMPARISON")
    print("="*70)
    
    if pt_scores is not None:
        print(f"PyTorch: {len(pt_scores)} detections (conf > 0.005)")
    if tflite_scores_raw is not None:
        print(f"TFLite (raw): {len(tflite_scores_raw)} detections (conf > 0.005)")
    if tflite_scores_sig is not None:
        print(f"TFLite (sigmoid): {len(tflite_scores_sig)} detections (conf > 0.005)")
    
    print("\n💡 RECOMMENDATIONS:")
    if tflite_scores_sig is not None and pt_scores is not None:
        if len(tflite_scores_sig) > len(tflite_scores_raw):
            print("   ✅ Applying sigmoid SIGNIFICANTLY improves TFLite detections!")
            print("   ➡️  Add sigmoid activation to your TFLite inference code:")
            print("      output_data[:, 4] = 1 / (1 + np.exp(-np.clip(output_data[:, 4], -100, 100)))")
        elif abs(len(pt_scores) - len(tflite_scores_raw)) < 2:
            print("   ✅ TFLite and PyTorch are detecting similar numbers of objects")
            print("   ⚠️  Check confidence score calibration differences")
        else:
            print("   ⚠️  TFLite is still underperforming compared to PyTorch")
            print("   ➡️  Consider re-exporting the model or using SavedModel format")

if __name__ == "__main__":
    compare_models()
