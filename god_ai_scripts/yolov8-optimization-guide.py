#!/usr/bin/env python3
"""
YOLOv8 Model Optimization for Mobile
Convert your slow 278ms model to a fast 30-50ms model

DIAGNOSIS: Your current model is likely:
- Float32 (not Float16 despite filename)
- YOLOv8-large/medium (too big for mobile)
- Missing TFLite optimizations

TARGET: 30-50ms inference on mobile CPU
"""

import numpy as np
import tensorflow as tf
from pathlib import Path

# ============================================================================
# STEP 1: Check Your Current Model
# ============================================================================

def diagnose_current_model(model_path='best_float16.tflite'):
    """
    Analyze why your current model is slow
    """
    print("=" * 70)
    print("🔍 DIAGNOSING YOUR CURRENT MODEL")
    print("=" * 70)
    
    if not Path(model_path).exists():
        print(f"❌ Model not found: {model_path}")
        return
    
    # Load model
    interpreter = tf.lite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    
    # Get details
    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]
    
    print(f"\n📋 Model Info:")
    print(f"  Input shape:  {input_details['shape']}")
    print(f"  Input dtype:  {input_details['dtype']}")
    print(f"  Output shape: {output_details['shape']}")
    print(f"  Output dtype: {output_details['dtype']}")
    
    # Check model size
    model_size_mb = Path(model_path).stat().st_size / (1024 * 1024)
    print(f"  Model size:   {model_size_mb:.2f} MB")
    
    # Diagnose issues
    print(f"\n🔍 Diagnosis:")
    
    if input_details['dtype'] == np.float32:
        print(f"  ⚠️  ISSUE #1: Model is Float32 (not Float16)")
        print(f"      Impact: 2-3x slower than Float16")
        print(f"      Fix: Re-export with proper Float16 quantization")
    
    if model_size_mb > 20:
        print(f"  ⚠️  ISSUE #2: Model too large ({model_size_mb:.1f}MB)")
        print(f"      Likely: YOLOv8m/l/x (medium/large/xlarge)")
        print(f"      Impact: 3-5x slower than YOLOv8n/s")
        print(f"      Fix: Use YOLOv8n (6MB) or YOLOv8s (22MB)")
    
    # Benchmark
    print(f"\n⏱️  Running quick benchmark...")
    import time
    
    test_input = np.random.randn(*input_details['shape']).astype(input_details['dtype'])
    times = []
    
    for _ in range(20):
        start = time.perf_counter()
        interpreter.set_tensor(input_details['index'], test_input)
        interpreter.invoke()
        times.append((time.perf_counter() - start) * 1000)
    
    avg_time = sum(times) / len(times)
    print(f"  Average inference: {avg_time:.2f}ms")
    
    if avg_time > 100:
        print(f"  ❌ CRITICAL: 3-9x slower than target (30-50ms)")
    elif avg_time > 60:
        print(f"  ⚠️  Slower than optimal (target: 30-50ms)")
    else:
        print(f"  ✅ Performance is good!")
    
    print("\n" + "=" * 70)


# ============================================================================
# STEP 2: Export Optimized YOLOv8 (RECOMMENDED METHOD)
# ============================================================================

def export_optimized_yolov8():
    """
    Export YOLOv8 with proper mobile optimization
    This is the BEST approach - start fresh with correct settings
    """
    print("\n" + "=" * 70)
    print("🚀 EXPORTING OPTIMIZED YOLOv8")
    print("=" * 70)
    
    try:
        from ultralytics import YOLO
    except ImportError:
        print("❌ ultralytics not installed")
        print("   Install: pip install ultralytics")
        return
    
    print("\n📦 Step 1: Choose model size")
    print("  • YOLOv8n (nano):   6MB,  25-35ms ⭐ RECOMMENDED for mobile")
    print("  • YOLOv8s (small):  22MB, 40-55ms ⭐ Good accuracy/speed balance")
    print("  • YOLOv8m (medium): 50MB, 80-120ms ❌ Too slow for mobile")
    print("  • YOLOv8l (large):  87MB, 150-200ms ❌ Way too slow")
    
    # Use nano for best mobile performance
    model_variant = 'yolov8n'  # Change to 'yolov8s' if you need more accuracy
    
    print(f"\n📥 Loading {model_variant}.pt...")
    model = YOLO(f'{model_variant}.pt')
    
    # ========================================================================
    # OPTION A: Float16 (RECOMMENDED)
    # ========================================================================
    print("\n⚙️  Option A: Exporting with Float16 quantization (RECOMMENDED)")
    print("   Expected: 30-50ms inference time")
    
    model.export(
        format='tflite',
        imgsz=640,
        int8=False,
        half=True,  # Float16 quantization
        optimize=True,
        simplify=True
    )
    
    output_name_fp16 = f'{model_variant}_float16.tflite'
    print(f"   ✅ Exported: {output_name_fp16}")
    
    # ========================================================================
    # OPTION B: INT8 (FASTEST)
    # ========================================================================
    print("\n⚙️  Option B: Exporting with INT8 quantization (FASTEST)")
    print("   Expected: 20-35ms inference time")
    print("   Note: Requires calibration data (using COCO128)")
    
    try:
        model.export(
            format='tflite',
            imgsz=640,
            int8=True,  # INT8 quantization
            data='coco128.yaml',  # Calibration dataset
            optimize=True,
            simplify=True
        )
        
        output_name_int8 = f'{model_variant}_int8.tflite'
        print(f"   ✅ Exported: {output_name_int8}")
    except Exception as e:
        print(f"   ⚠️  INT8 export failed: {e}")
        print(f"   Use Float16 model instead")
    
    print("\n" + "=" * 70)
    print("✅ EXPORT COMPLETE!")
    print("=" * 70)
    print(f"\nNext steps:")
    print(f"1. Copy {output_name_fp16} to your Android assets folder")
    print(f"2. Replace 'best_float16.tflite' with the new model")
    print(f"3. Run benchmark to verify 30-50ms inference time")


# ============================================================================
# STEP 3: Post-Training Quantization (if you can't re-export)
# ============================================================================

def quantize_existing_model(input_path='best_float16.tflite', 
                            output_path='best_optimized.tflite'):
    """
    Try to optimize an existing TFLite model
    This is a FALLBACK if you can't re-export from source
    """
    print("\n" + "=" * 70)
    print("🔧 POST-TRAINING QUANTIZATION (Fallback Method)")
    print("=" * 70)
    
    if not Path(input_path).exists():
        print(f"❌ Model not found: {input_path}")
        return
    
    print(f"\n⚠️  WARNING: This method has limitations:")
    print(f"   • Can't change model architecture (if it's too large)")
    print(f"   • May not achieve optimal performance")
    print(f"   • Better to re-export from PyTorch with correct settings")
    
    print(f"\n📥 Loading {input_path}...")
    
    # Load the model
    with open(input_path, 'rb') as f:
        tflite_model = f.read()
    
    # Try to optimize
    try:
        # Convert back to TF model (may fail for complex models)
        interpreter = tf.lite.Interpreter(model_content=tflite_model)
        interpreter.allocate_tensors()
        
        print(f"\n⚠️  This model appears to already be in TFLite format")
        print(f"   Cannot re-quantize without access to the original model")
        print(f"\n💡 RECOMMENDATION:")
        print(f"   1. Find your original YOLOv8 PyTorch weights (.pt file)")
        print(f"   2. Re-export using the export_optimized_yolov8() function")
        print(f"   3. This is the ONLY way to fix a YOLOv8m/l model → YOLOv8n")
        
    except Exception as e:
        print(f"❌ Failed: {e}")


# ============================================================================
# STEP 4: Benchmark and Compare Models
# ============================================================================

def benchmark_model(model_path, num_runs=50):
    """Benchmark a model and return average time"""
    import time
    
    interpreter = tf.lite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    
    input_details = interpreter.get_input_details()[0]
    test_input = np.random.randn(*input_details['shape']).astype(input_details['dtype'])
    
    # Warmup
    for _ in range(10):
        interpreter.set_tensor(input_details['index'], test_input)
        interpreter.invoke()
    
    # Benchmark
    times = []
    for _ in range(num_runs):
        start = time.perf_counter()
        interpreter.set_tensor(input_details['index'], test_input)
        interpreter.invoke()
        times.append((time.perf_counter() - start) * 1000)
    
    return {
        'mean': sum(times) / len(times),
        'min': min(times),
        'max': max(times)
    }


def compare_models():
    """Compare old vs new model performance"""
    print("\n" + "=" * 70)
    print("📊 MODEL COMPARISON")
    print("=" * 70)
    
    models = {
        'Original (slow)': 'best_float16.tflite',
        'Optimized Float16': 'yolov8n_float16.tflite',
        'Optimized INT8': 'yolov8n_int8.tflite',
    }
    
    results = {}
    
    for name, path in models.items():
        if not Path(path).exists():
            print(f"\n⏭️  Skipping {name}: {path} not found")
            continue
        
        print(f"\n🔄 Benchmarking {name}...")
        try:
            result = benchmark_model(path)
            results[name] = result
            print(f"   Mean: {result['mean']:.2f}ms")
            print(f"   Min:  {result['min']:.2f}ms")
            print(f"   Max:  {result['max']:.2f}ms")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
    
    # Print comparison
    if len(results) > 1:
        print("\n" + "=" * 70)
        print("🏆 PERFORMANCE COMPARISON")
        print("=" * 70)
        
        baseline = results.get('Original (slow)')
        if baseline:
            for name, result in results.items():
                if name != 'Original (slow)':
                    speedup = baseline['mean'] / result['mean']
                    print(f"\n{name}:")
                    print(f"  {result['mean']:.2f}ms ({speedup:.1f}x faster)")


# ============================================================================
# STEP 5: Verify Model in Python Before Android Testing
# ============================================================================

def verify_optimized_model(model_path):
    """
    Verify the optimized model works correctly
    """
    print("\n" + "=" * 70)
    print(f"✅ VERIFYING: {model_path}")
    print("=" * 70)
    
    if not Path(model_path).exists():
        print(f"❌ Model not found: {model_path}")
        return False
    
    interpreter = tf.lite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    
    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]
    
    # Check specs
    print(f"\n📋 Model Specifications:")
    print(f"  Input shape:  {input_details['shape']}")
    print(f"  Input dtype:  {input_details['dtype']}")
    print(f"  Output shape: {output_details['shape']}")
    print(f"  Model size:   {Path(model_path).stat().st_size / (1024*1024):.2f} MB")
    
    # Verify correct shape
    expected_input = [1, 640, 640, 3]
    if not list(input_details['shape']) == expected_input:
        print(f"  ⚠️  WARNING: Expected input {expected_input}")
        return False
    
    # Benchmark
    result = benchmark_model(model_path)
    print(f"\n⏱️  Performance:")
    print(f"  Average: {result['mean']:.2f}ms")
    
    # Verify performance
    if result['mean'] < 60:
        print(f"  ✅ EXCELLENT! Within target (30-50ms)")
        return True
    elif result['mean'] < 100:
        print(f"  ⚠️  Acceptable but not optimal")
        return True
    else:
        print(f"  ❌ Still too slow! Check model variant and quantization")
        return False


# ============================================================================
# MAIN WORKFLOW
# ============================================================================

def main():
    print("🎯 YOLOv8 MOBILE OPTIMIZATION TOOLKIT")
    print("=" * 70)
    
    import sys
    
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python optimize_yolov8.py diagnose           # Check current model")
        print("  python optimize_yolov8.py export             # Export new optimized model")
        print("  python optimize_yolov8.py compare            # Compare models")
        print("  python optimize_yolov8.py verify <model>     # Verify a model")
        print("\nQuick start:")
        print("  1. Run: python optimize_yolov8.py diagnose")
        print("  2. Run: python optimize_yolov8.py export")
        print("  3. Run: python optimize_yolov8.py verify yolov8n_float16.tflite")
        return
    
    command = sys.argv[1]
    
    if command == 'diagnose':
        diagnose_current_model('best_float16.tflite')
        
    elif command == 'export':
        export_optimized_yolov8()
        
    elif command == 'compare':
        compare_models()
        
    elif command == 'verify':
        if len(sys.argv) < 3:
            print("Usage: python optimize_yolov8.py verify <model_path>")
        else:
            verify_optimized_model(sys.argv[2])
    
    else:
        print(f"Unknown command: {command}")


# ============================================================================
# QUICK REFERENCE: Model Size vs Performance
# ============================================================================

"""
YOLOv8 MOBILE PERFORMANCE GUIDE
================================

Model       Size    Inference   Mobile?   Use Case
--------   ------   ---------   -------   ---------------------------
YOLOv8n    6 MB     25-35ms     ✅ YES    Best for real-time mobile
YOLOv8s    22 MB    40-55ms     ✅ YES    Balance accuracy/speed  
YOLOv8m    50 MB    80-120ms    ❌ NO     Too slow for mobile
YOLOv8l    87 MB    150-200ms   ❌ NO     Desktop only
YOLOv8x    136 MB   250-350ms   ❌ NO     Desktop only

QUANTIZATION OPTIONS:
---------------------
Float32:    Baseline, 2-3x slower than Float16
Float16:    ⭐ RECOMMENDED - 30-50ms, good accuracy
INT8:       Fastest (20-35ms), slight accuracy loss

YOUR CURRENT MODEL: 278ms
Likely issue: YOLOv8l/m with Float32
Target: YOLOv8n/s with Float16 → 30-50ms (6-9x faster!)
"""


if __name__ == "__main__":
    main()
