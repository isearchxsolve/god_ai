#!/usr/bin/env python3
"""
TFLite Model Benchmark Script
Measures actual inference time for your SafeScreen models
"""

import numpy as np
import time
import statistics
from pathlib import Path

try:
    import tensorflow as tf
except ImportError:
    print("ERROR: TensorFlow not found. Install with: pip install tensorflow")
    exit(1)

def benchmark_model(model_path, input_shape, input_range=(0, 1), num_warmup=10, num_runs=100, normalize=True):
    """
    Benchmark a TFLite model with realistic inputs
    
    Args:
        model_path: Path to .tflite model file
        input_shape: Tuple of (batch, height, width, channels)
        input_range: Tuple of (min, max) for random input values
        num_warmup: Number of warmup iterations
        num_runs: Number of benchmark iterations
        normalize: Whether to normalize input to [-1, 1] or [0, 1]
    """
    print(f"\n{'='*70}")
    print(f"📊 Benchmarking: {model_path}")
    print(f"{'='*70}")
    
    if not Path(model_path).exists():
        print(f"❌ Model file not found: {model_path}")
        return None
    
    # Load TFLite model
    interpreter = tf.lite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    
    # Get input/output details
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    
    print(f"\n📋 Model Info:")
    print(f"  Input shape: {input_details[0]['shape']}")
    print(f"  Input dtype: {input_details[0]['dtype']}")
    print(f"  Output shape: {output_details[0]['shape']}")
    print(f"  Output dtype: {output_details[0]['dtype']}")
    
    # Verify input shape matches
    expected_shape = input_details[0]['shape']
    if tuple(expected_shape) != input_shape:
        print(f"\n⚠️  WARNING: Provided shape {input_shape} doesn't match model shape {tuple(expected_shape)}")
        print(f"   Using model's expected shape instead")
        input_shape = tuple(expected_shape)
    
    # Generate random input data
    if normalize:
        # For models expecting [-1, 1] range (like your detection models)
        input_data = np.random.uniform(-1.0, 1.0, input_shape).astype(np.float32)
    else:
        # For models expecting [0, 1] range (like your recognition model)
        input_data = np.random.uniform(0.0, 1.0, input_shape).astype(np.float32)
    
    print(f"\n🔥 Warming up ({num_warmup} iterations)...")
    for i in range(num_warmup):
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        if (i + 1) % 5 == 0:
            print(f"  Warmup progress: {i+1}/{num_warmup}")
    
    print(f"\n⏱️  Running benchmark ({num_runs} iterations)...")
    times = []
    
    for i in range(num_runs):
        # Measure only the inference time
        start = time.perf_counter()
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        end = time.perf_counter()
        
        elapsed_ms = (end - start) * 1000
        times.append(elapsed_ms)
        
        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{num_runs} - Current: {elapsed_ms:.2f}ms")
    
    # Calculate statistics
    mean_time = statistics.mean(times)
    median_time = statistics.median(times)
    std_dev = statistics.stdev(times)
    min_time = min(times)
    max_time = max(times)
    p95_time = sorted(times)[int(len(times) * 0.95)]
    p99_time = sorted(times)[int(len(times) * 0.99)]
    
    print(f"\n📈 Results:")
    print(f"  Mean:      {mean_time:7.2f} ms")
    print(f"  Median:    {median_time:7.2f} ms")
    print(f"  Std Dev:   {std_dev:7.2f} ms")
    print(f"  Min:       {min_time:7.2f} ms")
    print(f"  Max:       {max_time:7.2f} ms")
    print(f"  P95:       {p95_time:7.2f} ms")
    print(f"  P99:       {p99_time:7.2f} ms")
    
    # Estimate FPS
    fps = 1000 / mean_time
    print(f"\n🎯 Estimated FPS: {fps:.1f}")
    
    return {
        'mean': mean_time,
        'median': median_time,
        'std_dev': std_dev,
        'min': min_time,
        'max': max_time,
        'p95': p95_time,
        'p99': p99_time,
        'fps': fps
    }


def main():
    print("🚀 SafeScreen Model Benchmark")
    print("=" * 70)
    
    # Model configurations based on your code
    models = [
        {
            'name': 'Visual Detection (ToxicDetector)',
            'path': 'best_float16.tflite',
            'input_shape': (1, 640, 640, 3),
            'normalize': True,  # [-1, 1] range
        },
        {
            'name': 'Text Detection (DBNet)',
            'path': 'dbnet_lite_320.tflite',
            'input_shape': (1, 320, 320, 3),
            'normalize': True,  # [-1, 1] range
        },
        {
            'name': 'Text Recognition (Tiny CRNN)',
            'path': 'tiny_crnn_en.tflite',
            'input_shape': (1, 48, 320, 3),
            'normalize': False,  # [0, 1] range
        },
    ]
    
    results = {}
    
    for model_config in models:
        result = benchmark_model(
            model_path=model_config['path'],
            input_shape=model_config['input_shape'],
            num_warmup=10,
            num_runs=100,
            normalize=model_config['normalize']
        )
        
        if result:
            results[model_config['name']] = result
    
    # Print summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY - Expected Inference Times")
    print("=" * 70)
    
    total_mean = 0
    for name, result in results.items():
        print(f"\n{name}:")
        print(f"  ⚡ Typical: {result['median']:.2f} ms")
        print(f"  📈 Average: {result['mean']:.2f} ms")
        print(f"  🎯 P95:     {result['p95']:.2f} ms")
        total_mean += result['mean']
    
    if len(results) == 3:
        print(f"\n{'='*70}")
        print(f"🔥 COMBINED PIPELINE ESTIMATE:")
        print(f"  Visual Detection:     ~{results['Visual Detection (ToxicDetector)']['median']:.0f} ms")
        print(f"  Text Detection:       ~{results['Text Detection (DBNet)']['median']:.0f} ms")
        print(f"  Text Recognition:     ~{results['Text Recognition (Tiny CRNN)']['median']:.0f} ms × N regions")
        print(f"\n  💡 Parallel execution (Visual + Text Detection): ~{max(results['Visual Detection (ToxicDetector)']['median'], results['Text Detection (DBNet)']['median']):.0f} ms")
        print(f"  💡 + Text Recognition (5 regions): ~{results['Text Recognition (Tiny CRNN)']['median'] * 5:.0f} ms")
        
        estimated_frame_time = max(
            results['Visual Detection (ToxicDetector)']['median'],
            results['Text Detection (DBNet)']['median']
        ) + results['Text Recognition (Tiny CRNN)']['median'] * 5
        
        print(f"\n  🎯 TOTAL FRAME TIME: ~{estimated_frame_time:.0f} ms ({1000/estimated_frame_time:.1f} FPS)")
    
    print(f"\n{'='*70}")
    print("\n💡 Tips:")
    print("  - These are PURE inference times (no preprocessing)")
    print("  - Add ~5-10ms for bitmap resizing/copying")
    print("  - Add ~10-20ms for postprocessing (NMS, CTC decoding)")
    print("  - Actual app performance = inference + overhead")
    print("\n  ⚠️  If your app is 10x+ slower, the bottleneck is:")
    print("     → Multiple redundant bitmap resizes")
    print("     → Excessive memory allocations")
    print("     → Processing on wrong thread")
    print("     → Not reusing buffers")


if __name__ == "__main__":
    main()
