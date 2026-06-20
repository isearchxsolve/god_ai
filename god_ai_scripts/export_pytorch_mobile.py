# from ultralytics import YOLO
# import torch

# print("=" * 60)
# print("Exporting YOLO to PyTorch Mobile (TorchScript)")
# print("=" * 60)

# # Load your trained model
# model = YOLO("runs/detect/google_toxic_detector/weights/best.pt")

# # Export to TorchScript (optimized for mobile)
# # This preserves full model accuracy
# model.export(
#     format="torchscript",
#     imgsz=640,
#     optimize=True,  # Mobile optimization
#     half=False,     # Keep FP32 for accuracy
#     dynamic=False,  # Static input size
#     simplify=False  # Don't simplify graph
# )

# print("\n" + "=" * 60)
# print("✅ Export complete!")
# print("=" * 60)
# print("\nOutput file: runs/detect/google_toxic_detector/weights/best.torchscript")
# print("\nNext steps:")
# print("1. Copy best.torchscript to app/src/main/assets/")
# print("2. Update build.gradle with PyTorch dependencies")
# print("3. Replace ToxicDetector.kt with PyTorch version")
# print("=" * 60)


from ultralytics import YOLO

# 1. Load your best trained weights
model = YOLO("runs/detect/google_toxic_detector/weights/best.pt")

print("Exporting Optimized Model for Android (320x320)...")

# 2. Export to TorchScript optimized for mobile
# REMOVED: int8=True (not supported for TorchScript)
# KEY CHANGE: imgsz=320 (This provides the 4x speedup)
model.export(
    format="torchscript",
    imgsz=320,          # 320x320 input (4x faster than 640x640)
    optimize=True,      # Applies torch.utils.mobile_optimizer
    half=False,         # Keep FP32 for compatibility
    dynamic=False,
    simplify=True
)

print("✅ Done! File saved as 'best.torchscript'.")
print("👉 Rename this file to 'best_quantized.torchscript' and move it to your Android assets folder.")