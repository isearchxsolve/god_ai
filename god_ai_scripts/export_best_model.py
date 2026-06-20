from ultralytics import YOLO
import sys
import os

# Windows Console Fix
if sys.stdout.encoding != 'utf-8':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

def main():
    print("Attempting to rescue 'best.pt'...")
    
    # 1. Locate the Best Model
    # Check your folder structure. It might be 'yolo_ui_s_model', 'yolo_ui_s_model2', etc.
    # We look for the one with the 'inf' crash, which is likely the latest one.
    model_path = "runs/detect/yolo_ui_s_model/weights/best.pt"
    
    if not os.path.exists(model_path):
        print(f"❌ Error: Could not find {model_path}")
        print("Please check the 'runs/detect' folder and update the path in this script.")
        return

    print(f"✅ Found model: {model_path}")
    
    try:
        model = YOLO(model_path)
        
        # 2. Verify Health (Run validation)
        print("Verifying model health (checking for NaN/Inf)...")
        # We run validation on a tiny subset just to see if it crashes
        metrics = model.val(data="toxic_ui.yaml", batch=4, imgsz=640, device=0)
        
        print(f"✅ Model verification passed! mAP50: {metrics.box.map50:.3f}")
        
    except Exception as e:
        print(f"❌ Model seems corrupted: {e}")
        print("The 'Infinity' error might have poisoned 'best.pt' too.")
        return

    # 3. Export
    print("\nStarting Export to TFLite...")
    try:
        # int8 quantization is best for ML Kit speed
        output = model.export(format="tflite", int8=True, imgsz=640)
        print(f"\n🎉 SUCCESS! Exported to: {output}")
        print("Copy this file to your Android project as 'toxic_detector.tflite'")
    except Exception as e:
        print(f"❌ Export Failed: {e}")

if __name__ == "__main__":
    main()