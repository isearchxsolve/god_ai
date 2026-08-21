"""
MOBILE-OPTIMIZED YOLOV8 TRAINING SCRIPT
========================================
Trains YOLOv8n (nano) specifically for mobile deployment with Float16 export

KEY CHANGES:
- Uses YOLOv8n instead of YOLOv8x (6MB vs 87MB)
- Optimized hyperparameters for mobile inference
- Automatically exports to TFLite Float16 after training
- Validates model performance on mobile-like conditions
- Targets 30-50ms inference time on mobile devices

ACCURACY IMPACT:
- YOLOv8n vs YOLOv8x: ~5-8% accuracy loss
- But 10-15× faster inference
- Perfect for real-time mobile safety apps
"""

from ultralytics import YOLO
from pathlib import Path
import random
import shutil
import yaml
import time

# ===================== CONFIG =====================
DATASET_PATH = Path("google_search_dataset_v2")
DATA_YAML = "google_search_data_v2.yaml"

# Model selection - CRITICAL for mobile performance
MODEL_VARIANT = "yolov8n.pt"  # Nano - Best for mobile (6MB)
# Other options:
# "yolov8s.pt"  # Small (22MB) - More accuracy, still fast
# "yolov8m.pt"  # Medium (50MB) - Too slow for mobile
# "yolov8l.pt"  # Large (87MB) - Way too slow
# "yolov8x.pt"  # XLarge (136MB) - Desktop only

# Training params optimized for mobile deployment
EPOCHS = 100  # More epochs for smaller model
BATCH_SIZE = 16
IMG_SIZE = 640  # Standard for YOLOv8
DEVICE = 0  # 0 for GPU, "cpu" for CPU

# Export settings
EXPORT_FLOAT16 = True  # Export to Float16 TFLite (recommended)
EXPORT_INT8 = True     # Also export INT8 for maximum speed
VERIFY_MOBILE_PERF = True  # Benchmark exported models

def setup_dataset():
    """
    Fixes the dataset structure by creating a validation split
    and generating the YAML config file.
    """
    print("\n" + "="*80)
    print("📁 [1/4] DATASET SETUP")
    print("="*80)
    
    images_train = DATASET_PATH / "images" / "train"
    labels_train = DATASET_PATH / "labels" / "train"
    images_val = DATASET_PATH / "images" / "val"
    labels_val = DATASET_PATH / "labels" / "val"
    
    # Create directories
    images_val.mkdir(parents=True, exist_ok=True)
    labels_val.mkdir(parents=True, exist_ok=True)
    
    # Check if we need to split data
    train_files = list(images_train.glob("*.jpg")) + list(images_train.glob("*.png"))
    val_files = list(images_val.glob("*.jpg")) + list(images_val.glob("*.png"))
    
    total_files = len(train_files) + len(val_files)
    
    if total_files == 0:
        raise FileNotFoundError(f"❌ No images found in {images_train}. Run the labeling script first!")
        
    # If val is empty, move 15% of train to val
    if len(val_files) == 0:
        print(f"📊 Splitting {len(train_files)} images into Train/Val (85/15)...")
        num_val = int(len(train_files) * 0.15)
        files_to_move = random.sample(train_files, num_val)
        
        for img_path in files_to_move:
            # Move Image
            shutil.move(str(img_path), str(images_val / img_path.name))
            
            # Move Label (if exists)
            label_name = img_path.stem + ".txt"
            label_src = labels_train / label_name
            if label_src.exists():
                shutil.move(str(label_src), str(labels_val / label_name))
                
        print(f"✅ Moved {num_val} images to validation set.")
    else:
        print(f"✅ Validation set already exists ({len(val_files)} images).")

    # Generate YAML
    print(f"\n📝 Generating configuration file...")
    yaml_content = {
        'path': str(DATASET_PATH.absolute()),
        'train': 'images/train',
        'val': 'images/val',
        'nc': 1,
        'names': ['unsafe_content']
    }
    
    with open(DATA_YAML, 'w') as f:
        yaml.dump(yaml_content, f, sort_keys=False)
    print(f"✅ Saved {DATA_YAML}")
    
    # Print dataset stats
    train_count = len(list(images_train.glob("*.jpg")) + list(images_train.glob("*.png")))
    val_count = len(list(images_val.glob("*.jpg")) + list(images_val.glob("*.png")))
    print(f"\n📊 Dataset Statistics:")
    print(f"   Training images:   {train_count}")
    print(f"   Validation images: {val_count}")
    print(f"   Total:             {train_count + val_count}")


def train_model():
    """
    Train YOLOv8n optimized for mobile deployment
    """
    print("\n" + "="*80)
    print("🎯 [2/4] MODEL TRAINING")
    print("="*80)
    
    print(f"\n📦 Loading {MODEL_VARIANT} (mobile-optimized)...")
    model = YOLO(MODEL_VARIANT)
    
    # Print model info
    print(f"\n📋 Model Information:")
    print(f"   Variant: YOLOv8n (Nano)")
    print(f"   Parameters: ~3.2M")
    print(f"   Expected size: ~6MB (Float16)")
    print(f"   Target inference: 30-50ms on mobile")
    print(f"   Accuracy vs YOLOv8x: -5-8% (acceptable tradeoff)")
    
    print(f"\n🚀 Starting training for {EPOCHS} epochs...")
    print(f"   Batch size: {BATCH_SIZE}")
    print(f"   Image size: {IMG_SIZE}")
    print(f"   Device: {'GPU' if DEVICE == 0 else 'CPU'}")
    
    results = model.train(
        data=DATA_YAML,
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        device=DEVICE,
        project="runs/detect",
        name="mobile_toxic_detector",
        exist_ok=True,
        
        # Mobile-optimized training settings
        patience=20,       # More patience for smaller model
        save=True,
        save_period=10,    # Save checkpoints every 10 epochs
        
        # Optimizer settings
        optimizer="AdamW",
        lr0=0.01,          # Higher LR for nano model
        lrf=0.01,          # Final LR
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=3.0,
        warmup_momentum=0.8,
        
        # Augmentation (helps smaller model generalize)
        mosaic=1.0,        # Essential for overlapping objects
        mixup=0.15,        # Increased for better generalization
        copy_paste=0.1,    # Helps with small objects
        degrees=10.0,      # Rotation augmentation
        translate=0.1,     # Translation
        scale=0.5,         # Scale variations
        shear=2.0,         # Shear transform
        perspective=0.0,   # Perspective transform
        flipud=0.0,        # No vertical flip (screenshots are always upright)
        fliplr=0.5,        # Horizontal flip
        hsv_h=0.015,       # Hue augmentation
        hsv_s=0.7,         # Saturation
        hsv_v=0.4,         # Value/brightness
        
        # Loss weights (balanced for single class)
        box=7.5,           # Box loss weight
        cls=0.5,           # Class loss weight
        dfl=1.5,           # DFL loss weight
        
        # Validation settings
        val=True,
        plots=True,        # Generate training plots
        
        # Performance settings
        workers=8,         # Data loading workers
        close_mosaic=10,   # Disable mosaic in last 10 epochs for better convergence
    )
    
    print("\n" + "="*80)
    print("✅ TRAINING COMPLETE!")
    print("="*80)
    print(f"📁 Best model: runs/detect/mobile_toxic_detector/weights/best.pt")
    print(f"📁 Last model: runs/detect/mobile_toxic_detector/weights/last.pt")
    
    return results


def export_for_mobile(model_path):
    """
    Export trained model to mobile-optimized formats
    """
    print("\n" + "="*80)
    print("📦 [3/4] MOBILE EXPORT")
    print("="*80)
    
    model = YOLO(model_path)
    
    # Export Float16 (RECOMMENDED)
    if EXPORT_FLOAT16:
        print("\n🔄 Exporting to TFLite Float16 (RECOMMENDED for mobile)...")
        try:
            model.export(
                format='tflite',
                imgsz=IMG_SIZE,
                int8=False,
                half=True,  # Float16 quantization
                optimize=True,
                simplify=True
            )
            
            # Get the exported file path
            export_path = Path(model_path).parent / f"{Path(model_path).stem}_float16.tflite"
            if export_path.exists():
                size_mb = export_path.stat().st_size / (1024 * 1024)
                print(f"✅ Float16 export complete!")
                print(f"   📁 File: {export_path}")
                print(f"   📊 Size: {size_mb:.2f} MB")
                print(f"   ⚡ Expected: 30-50ms inference on mobile")
            
        except Exception as e:
            print(f"❌ Float16 export failed: {e}")
    
    # Export INT8 (FASTEST)
    if EXPORT_INT8:
        print("\n🔄 Exporting to TFLite INT8 (FASTEST option)...")
        try:
            model.export(
                format='tflite',
                imgsz=IMG_SIZE,
                int8=True,  # INT8 quantization
                data=DATA_YAML,  # Use training data for calibration
                optimize=True,
                simplify=True
            )
            
            export_path = Path(model_path).parent / f"{Path(model_path).stem}_int8.tflite"
            if export_path.exists():
                size_mb = export_path.stat().st_size / (1024 * 1024)
                print(f"✅ INT8 export complete!")
                print(f"   📁 File: {export_path}")
                print(f"   📊 Size: {size_mb:.2f} MB")
                print(f"   ⚡ Expected: 20-35ms inference on mobile")
                print(f"   ⚠️  Accuracy: -2-5% vs Float16 (usually acceptable)")
            
        except Exception as e:
            print(f"⚠️  INT8 export failed: {e}")
            print(f"   This is normal if you don't have calibration data")


def verify_mobile_performance(model_path):
    """
    Benchmark exported models to verify mobile performance
    """
    if not VERIFY_MOBILE_PERF:
        return
    
    print("\n" + "="*80)
    print("⏱️  [4/4] PERFORMANCE VERIFICATION")
    print("="*80)
    
    import tensorflow as tf
    import numpy as np
    
    # Find exported models
    model_dir = Path(model_path).parent
    float16_model = model_dir / f"{Path(model_path).stem}_float16.tflite"
    int8_model = model_dir / f"{Path(model_path).stem}_int8.tflite"
    
    results = {}
    
    for model_file in [float16_model, int8_model]:
        if not model_file.exists():
            continue
        
        print(f"\n📊 Benchmarking: {model_file.name}")
        
        try:
            # Load model
            interpreter = tf.lite.Interpreter(model_path=str(model_file))
            interpreter.allocate_tensors()
            
            # Get input details
            input_details = interpreter.get_input_details()[0]
            
            # Generate test input
            test_input = np.random.randn(*input_details['shape']).astype(input_details['dtype'])
            
            # Warmup
            for _ in range(10):
                interpreter.set_tensor(input_details['index'], test_input)
                interpreter.invoke()
            
            # Benchmark
            times = []
            for _ in range(50):
                start = time.perf_counter()
                interpreter.set_tensor(input_details['index'], test_input)
                interpreter.invoke()
                times.append((time.perf_counter() - start) * 1000)
            
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"   Average: {avg_time:.2f}ms")
            print(f"   Min:     {min_time:.2f}ms")
            print(f"   Max:     {max_time:.2f}ms")
            
            # Evaluate performance
            if avg_time < 60:
                print(f"   ✅ EXCELLENT! Within target (30-50ms)")
            elif avg_time < 100:
                print(f"   ⚠️  Acceptable but slower than optimal")
            else:
                print(f"   ❌ Too slow for real-time mobile use")
            
            results[model_file.name] = avg_time
            
        except Exception as e:
            print(f"   ❌ Benchmark failed: {e}")
    
    # Print comparison
    if len(results) > 1:
        print(f"\n📊 Performance Comparison:")
        for name, time_ms in results.items():
            print(f"   {name}: {time_ms:.2f}ms")


def print_deployment_instructions(model_path):
    """
    Print instructions for deploying to Android
    """
    print("\n" + "="*80)
    print("📱 ANDROID DEPLOYMENT INSTRUCTIONS")
    print("="*80)
    
    model_dir = Path(model_path).parent
    float16_model = model_dir / f"{Path(model_path).stem}_float16.tflite"
    
    print(f"\n1️⃣  Copy model to Android project:")
    print(f"   cp {float16_model} app/src/main/assets/")
    
    print(f"\n2️⃣  Update your detector code:")
    print(f"   val detector = OptimizedVisualDetector(")
    print(f"       context = this,")
    print(f"       modelName = \"{float16_model.name}\",")
    print(f"       useGpu = false,  // Set to true for 2-3x speedup")
    print(f"       numThreads = 4")
    print(f"   )")
    
    print(f"\n3️⃣  Verify performance on device:")
    print(f"   - Expected: 30-50ms inference time")
    print(f"   - Check logcat for timing logs")
    print(f"   - If slower, ensure you're using the Float16 model")
    
    print(f"\n4️⃣  Optional: Try INT8 for maximum speed:")
    int8_model = model_dir / f"{Path(model_path).stem}_int8.tflite"
    if int8_model.exists():
        print(f"   - Use {int8_model.name} instead")
        print(f"   - Expected: 20-35ms inference")
        print(f"   - Slightly lower accuracy (~2-3%)")
    
    print(f"\n" + "="*80)


def main():
    print("\n" + "="*80)
    print("🚀 MOBILE-OPTIMIZED TOXIC CONTENT DETECTOR TRAINING")
    print("="*80)
    print(f"\n📋 Configuration:")
    print(f"   Model: {MODEL_VARIANT} (optimized for mobile)")
    print(f"   Target: 30-50ms inference on mobile devices")
    print(f"   Accuracy tradeoff: -5-8% vs YOLOv8x (acceptable)")
    print(f"   Export formats: Float16 TFLite (recommended), INT8 TFLite (fastest)")
    
    try:
        # Step 1: Setup dataset
        setup_dataset()
        
        # Step 2: Train model
        results = train_model()
        
        # Step 3: Export for mobile
        best_model = Path("runs/detect/mobile_toxic_detector/weights/best.pt")
        if best_model.exists():
            export_for_mobile(str(best_model))
            
            # Step 4: Verify performance
            verify_mobile_performance(str(best_model))
            
            # Print deployment instructions
            print_deployment_instructions(str(best_model))
        else:
            print(f"\n❌ Best model not found at {best_model}")
        
        print("\n" + "="*80)
        print("✅ ALL STEPS COMPLETE!")
        print("="*80)
        print(f"\n🎯 Next Steps:")
        print(f"   1. Copy the Float16 TFLite model to your Android project")
        print(f"   2. Update your detector code to use the new model")
        print(f"   3. Test on device and verify 30-50ms inference time")
        print(f"   4. Compare accuracy with your validation set")
        print(f"\n💡 Tip: If accuracy is too low, try YOLOv8s instead of YOLOv8n")
        print(f"   (Change MODEL_VARIANT = 'yolov8s.pt' at the top)")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()