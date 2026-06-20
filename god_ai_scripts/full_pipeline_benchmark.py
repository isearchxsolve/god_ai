#!/usr/bin/env python3
"""
Complete Pipeline Benchmark (Fixed for Dynamic Shapes)
Measures: preprocessing, inference, and postprocessing.
"""

import numpy as np
import time
import statistics
from pathlib import Path
from PIL import Image

try:
    import tensorflow as tf
except ImportError:
    print("ERROR: Install dependencies: pip install tensorflow pillow")
    exit(1)

class PipelineBenchmark:
    def __init__(self, model_path, target_shape=None):
        self.model_path = model_path
        self.interpreter = tf.lite.Interpreter(model_path=str(model_path))
        
        # CRITICAL FIX: Explicitly resize input if a target shape is provided
        # This matches the 'resizeInput' call in FastTextDetector.kt
        if target_shape:
            print(f"🔧 Resizing model input to: {target_shape}")
            self.interpreter.resize_tensor_input(0, target_shape)
            
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        
    def benchmark_preprocessing(self, source_size, target_size, num_runs=50):
        print(f"\n📐 Preprocessing: {source_size} → {target_size}")
        source = Image.new('RGB', source_size, color='red')
        source_array = np.array(source)
        
        times = []
        for _ in range(num_runs):
            start = time.perf_counter()
            resized = Image.fromarray(source_array).resize(target_size, Image.BILINEAR)
            resized_array = np.array(resized)
            # Normalization simulation
            _ = (resized_array.astype(np.float32) / 127.5) - 1.0
            times.append((time.perf_counter() - start) * 1000)
        
        median_time = statistics.median(times)
        print(f"  Median: {median_time:.2f} ms")
        return median_time
    
    def benchmark_inference(self, input_shape, num_runs=50):
        print(f"⚡ Inference: {input_shape}")
        input_data = np.random.uniform(-1.0, 1.0, input_shape).astype(np.float32)
        
        # Warmup
        for _ in range(5):
            self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
            self.interpreter.invoke()
        
        times = []
        for _ in range(num_runs):
            start = time.perf_counter()
            self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
            self.interpreter.invoke()
            times.append((time.perf_counter() - start) * 1000)
        
        median_time = statistics.median(times)
        print(f"  Median: {median_time:.2f} ms")
        return median_time

def main():
    print("🔬 UPDATED PIPELINE BENCHMARK (Fixed for 320x320 Resize)")
    print("=" * 70)
    results = {}

    # 1. Visual Detection Pipeline
    if Path("best_float16.tflite").exists():
        print("\n🎯 VISUAL DETECTION (ToxicDetector)")
        bench = PipelineBenchmark("best_float16.tflite")
        p = bench.benchmark_preprocessing((1080, 2424), (640, 640))
        i = bench.benchmark_inference((1, 640, 640, 3))
        results['visual'] = p + i + 8.0 # +8ms NMS estimate

    # 2. Text Detection Pipeline (DBNet)
    if Path("dbnet_lite_320.tflite").exists():
        print("\n📝 TEXT DETECTION (DBNet)")
        # APPLYING THE KOTLIN FIX: Resizing 1x1 to 320x320
        text_det_bench = PipelineBenchmark("dbnet_lite_320.tflite", target_shape=[1, 320, 320, 3])
        p = text_det_bench.benchmark_preprocessing((640, 640), (320, 320))
        i = text_det_bench.benchmark_inference((1, 320, 320, 3))
        results['text_detection'] = p + i + 5.0 # +5ms Floodfill estimate

    # 3. Text Recognition Pipeline (CRNN)
    if Path("tiny_crnn_en.tflite").exists():
        print("\n🔤 TEXT RECOGNITION (Tiny CRNN)")
        # Shape defined in FastTextDetector.kt
        text_rec_bench = PipelineBenchmark("tiny_crnn_en.tflite")
        p = text_rec_bench.benchmark_preprocessing((100, 50), (320, 48))
        i = text_rec_bench.benchmark_inference((1, 48, 320, 3))
        results['text_recognition'] = p + i + 2.0 # +2ms CTC estimate

    # Final Summary Logic
    if all(k in results for k in ['visual', 'text_detection', 'text_recognition']):
        print("\n" + "=" * 70)
        parallel_time = max(results['visual'], results['text_detection'])
        rec_total = results['text_recognition'] * 5 # Top 5 regions
        total_time = parallel_time + rec_total
        print(f"🔥 TOTAL ESTIMATED FRAME TIME: {total_time:.1f} ms")
        print(f"🔥 ESTIMATED FPS: {1000/total_time:.1f}")
        print("=" * 70)

if __name__ == "__main__":
    main()