# from ultralytics import YOLO

# model = YOLO("runs/detect/yolo_ui_s_model/weights/best.pt")

# Method 1: Try with explicit full precision
# model.export(
#     format='tflite',
#     imgsz=640,
#     int8=False,
#     half=False,
#     dynamic=False,
#     simplify=True
# )

# model.export(
#     format='tflite',
#     imgsz=640,
#     int8=False,
#     optimize=False
# )

from ultralytics import YOLO
import tensorflow as tf

# Load the trained model
#model = YOLO("runs/detect/yolo_ui_s_model/weights/best.pt")
model = YOLO("runs/detect/google_toxic_detector/weights/best.pt")

print("=" * 60)
print("Exporting YOLO model to TFLite with optimal settings")
print("=" * 60)

# Export with settings that preserve detection quality
# Key changes:
# 1. No quantization (int8=False, half=False)
# 2. No simplification (can remove operations)
# 3. Explicit image size
model.export(
    format="tflite",
    imgsz=640,
    int8=False,        # No int8 quantization
    half=False,        # No FP16 quantization
    dynamic=False,     # Static input shape
    simplify=False,    # Don't simplify ONNX graph (can lose accuracy)
    nms=False,         # CRITICAL: Export without NMS baked in
    optimize=False     # No TFLite optimization
)

print("\n" + "=" * 60)
print("✅ Export complete!")
print("=" * 60)
print("\nIMPORTANT: Model exported WITHOUT built-in NMS")
print("Your inference script handles NMS separately, which gives you control")
print("\nTest with: python inference_tflite.py")
print("=" * 60)