from ultralytics import YOLO
import tensorflow as tf
import cv2
import numpy as np
from PIL import Image, ImageOps

IMAGE_PATH = "shits.jpg"
PT_MODEL = "runs/detect/yolo_ui_s_model/weights/best.pt"
TFLITE_MODEL = "runs/detect/yolo_ui_s_model/weights/best_saved_model/best_float32.tflite"
CONF_THRESHOLD = 0.005

def letterbox_resize(img, size=640):
    """OpenCV letterbox matching both implementations"""
    h, w = img.shape[:2]
    scale = min(size / h, size / w)
    nh, nw = int(h * scale), int(w * scale)
    
    img_resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    pad_x = (size - nw) // 2
    pad_y = (size - nh) // 2
    canvas[pad_y:pad_y+nh, pad_x:pad_x+nw] = img_resized
    
    return canvas, scale, pad_x, pad_y

# Load image
pil_img = Image.open(IMAGE_PATH)
pil_img = ImageOps.exif_transpose(pil_img)
img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
orig_h, orig_w = img_cv.shape[:2]

print("=" * 60)
print("PYTORCH MODEL")
print("=" * 60)

# PyTorch inference
pt_model = YOLO(PT_MODEL)
results = pt_model.predict(pil_img, conf=CONF_THRESHOLD, imgsz=640, verbose=False)
pt_boxes = results[0].boxes.xyxy.cpu().numpy()
pt_scores = results[0].boxes.conf.cpu().numpy()

print(f"PyTorch detections: {len(pt_boxes)}")
for i, (box, score) in enumerate(zip(pt_boxes, pt_scores)):
    x1, y1, x2, y2 = map(int, box)
    print(f"  Box {i}: conf={score:.3f}, coords=[{x1}, {y1}, {x2}, {y2}], size={x2-x1}x{y2-y1}")

print("\n" + "=" * 60)
print("TFLITE MODEL")
print("=" * 60)

# TFLite inference
interpreter = tf.lite.Interpreter(model_path=TFLITE_MODEL)
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# Preprocess
img_padded, scale, pad_x, pad_y = letterbox_resize(img_cv, 640)
img_rgb = cv2.cvtColor(img_padded, cv2.COLOR_BGR2RGB)
input_data = img_rgb.astype(np.float32) / 255.0
input_data = np.expand_dims(input_data, axis=0)

# Inference
interpreter.set_tensor(input_details[0]['index'], input_data)
interpreter.invoke()
output_data = interpreter.get_tensor(output_details[0]['index'])

# Parse (no NMS yet)
cx_norm = output_data[0, 0, :]
cy_norm = output_data[0, 1, :]
w_norm = output_data[0, 2, :]
h_norm = output_data[0, 3, :]
conf = output_data[0, 4, :]

mask = conf > CONF_THRESHOLD
tflite_raw_count = mask.sum()
print(f"TFLite raw detections (before NMS): {tflite_raw_count}")

# Convert to pixel coordinates
cx_640 = cx_norm[mask] * 640
cy_640 = cy_norm[mask] * 640
w_640 = w_norm[mask] * 640
h_640 = h_norm[mask] * 640
conf_filtered = conf[mask]

x1_640 = cx_640 - w_640 / 2
y1_640 = cy_640 - h_640 / 2
x2_640 = cx_640 + w_640 / 2
y2_640 = cy_640 + h_640 / 2

tflite_boxes = []
tflite_scores = []

for i in range(len(conf_filtered)):
    x1 = (x1_640[i] - pad_x) / scale
    y1 = (y1_640[i] - pad_y) / scale
    x2 = (x2_640[i] - pad_x) / scale
    y2 = (y2_640[i] - pad_y) / scale
    
    x1 = max(0, min(orig_w, x1))
    y1 = max(0, min(orig_h, y1))
    x2 = max(0, min(orig_w, x2))
    y2 = max(0, min(orig_h, y2))
    
    if x2 > x1 and y2 > y1:
        tflite_boxes.append([int(x1), int(y1), int(x2), int(y2)])
        tflite_scores.append(float(conf_filtered[i]))

# Sort by confidence
sorted_indices = sorted(range(len(tflite_scores)), key=lambda i: tflite_scores[i], reverse=True)

print(f"TFLite valid boxes (before NMS): {len(tflite_boxes)}")
for idx in sorted_indices[:10]:  # Show top 10
    box = tflite_boxes[idx]
    score = tflite_scores[idx]
    x1, y1, x2, y2 = box
    print(f"  Box {idx}: conf={score:.3f}, coords=[{x1}, {y1}, {x2}, {y2}], size={x2-x1}x{y2-y1}")

print("\n" + "=" * 60)
print("COMPARISON")
print("=" * 60)
print(f"PyTorch detections (with built-in NMS): {len(pt_boxes)}")
print(f"TFLite raw detections (before NMS): {len(tflite_boxes)}")
print(f"\nTop PyTorch confidence: {pt_scores.max():.3f}")
print(f"Top TFLite confidence: {max(tflite_scores):.3f}")

if len(pt_boxes) > len(tflite_boxes):
    print(f"\n⚠️  PyTorch found {len(pt_boxes) - len(tflite_boxes)} more detections")
    print("Possible causes:")
    print("  1. TFLite model has lower confidence scores")
    print("  2. Export process changed model behavior")
    print("  3. Different preprocessing between PT and TFLite")
elif len(tflite_boxes) > len(pt_boxes):
    print(f"\n✅ TFLite has more raw detections ({len(tflite_boxes)} vs {len(pt_boxes)})")
    print("   After NMS in your script, count will be reduced")
else:
    print(f"\n✅ Same number of detections!")
    
print("\n" + "=" * 60)
print("RECOMMENDATIONS")
print("=" * 60)
if max(tflite_scores) < pt_scores.max() * 0.5:
    print("❌ TFLite confidence scores are much lower than PyTorch")
    print("   → Try re-exporting with: nms=False, simplify=False")
elif len(tflite_boxes) >= len(pt_boxes):
    print("✅ TFLite is detecting enough regions")
    print("   → Adjust NMS settings (lower IOU threshold)")
    print("   → Or increase padding in inference script")
else:
    print("⚠️  TFLite is missing some detections")
    print("   → Re-export the model with better preservation")
    print("   → Check preprocessing differences")

print("=" * 60)