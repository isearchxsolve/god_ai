from ultralytics import YOLO
import sys
import os

# === FIX 1: Windows Console Encoding ===
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# === FIX 2: VRAM Fragmentation Handling ===
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

def main():
    print("Loading YOLOv8 Small model...")
    model = YOLO("yolov8s.pt") 

    print("Starting Training (Safe Mode)...")
    
    results = model.train(
        data="toxic_ui.yaml", 
        
        # === 4GB VRAM SAFE SETTINGS ===
        epochs=50,             
        imgsz=640,
        batch=4,        # FIXED: Keep at 4 for stability with amp=False
        
        # === STABILITY FIXES ===
        workers=0,      # FIXED: Single-threaded (safest for Windows)
        
        amp=False,      # Disable Mixed Precision (prevents NaN loss)
        
        box=7.5,        # FIXED: Lower than default to prevent gradient explosion
        
        lr0=0.01,       # Conservative learning rate
        
        # === SYSTEM SETTINGS ===
        cache=False,
        device=0,
        exist_ok=True,
        name="yolo_ui_s_model"  # FIXED: Match inference script
    )

    print("Exporting to TFLite...")
    model.export(format="tflite", int8=True, imgsz=640) 

if __name__ == "__main__":
    main()