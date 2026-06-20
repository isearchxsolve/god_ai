"""
TFLite Model Inspector - Diagnose input/output signatures
"""
import tensorflow as tf
import numpy as np

MODEL_PATH = r".\models\tflite\dbnet_lite_320.tflite"

def inspect_model(model_path):
    print("="*70)
    print("TFLITE MODEL DEEP INSPECTION")
    print("="*70)
    
    interpreter = tf.lite.Interpreter(model_path=model_path)
    
    # Get ALL details before allocation
    print("\n[1] INPUT DETAILS (before allocation):")
    for idx, detail in enumerate(interpreter.get_input_details()):
        print(f"\nInput #{idx}:")
        print(f"  Name  : {detail['name']}")
        print(f"  Shape : {detail['shape'].tolist()}")
        print(f"  Dtype : {detail['dtype']}")
        print(f"  Index : {detail['index']}")
        if 'quantization' in detail:
            print(f"  Quant : {detail['quantization']}")
    
    print("\n[2] OUTPUT DETAILS (before allocation):")
    for idx, detail in enumerate(interpreter.get_output_details()):
        print(f"\nOutput #{idx}:")
        print(f"  Name  : {detail['name']}")
        print(f"  Shape : {detail['shape'].tolist()}")
        print(f"  Dtype : {detail['dtype']}")
        print(f"  Index : {detail['index']}")
    
    # Check for signature information
    try:
        print("\n[3] SIGNATURE DEFS:")
        sig_list = interpreter.get_signature_list()
        if sig_list:
            for sig_key in sig_list:
                print(f"\n  Signature: {sig_key}")
                sig_runner = interpreter.get_signature_runner(sig_key)
                # This may not work on all TFLite versions, but try
                print(f"    Available")
        else:
            print("  No signature definitions found")
    except Exception as e:
        print(f"  Signature inspection not available: {e}")
    
    # Now allocate and check actual tensor properties
    print("\n[4] ALLOCATING TENSORS...")
    try:
        interpreter.allocate_tensors()
        print("  ✓ Allocation successful")
        
        # Check allocated input tensor
        input_details = interpreter.get_input_details()[0]
        tensor = interpreter.get_tensor(input_details['index'])
        print(f"\n  Allocated input tensor shape: {tensor.shape}")
        print(f"  Total bytes: {tensor.nbytes}")
        
    except Exception as e:
        print(f"  ⚠ Allocation failed: {e}")
        print("  This suggests the model REQUIRES input shape to be set first")
    
    # Attempt to resize and re-allocate
    print("\n[5] ATTEMPTING RESIZE TO [1,320,320,3]...")
    try:
        input_details = interpreter.get_input_details()[0]
        interpreter.resize_tensor_input(input_details['index'], [1, 320, 320, 3])
        interpreter.allocate_tensors()
        print("  ✓ Resize successful")
        
        # Create dummy input
        dummy_input = np.random.randn(1, 320, 320, 3).astype(np.float32)
        interpreter.set_tensor(input_details['index'], dummy_input)
        
        print("\n[6] RUNNING INFERENCE TEST...")
        interpreter.invoke()
        
        output_details = interpreter.get_output_details()[0]
        output = interpreter.get_tensor(output_details['index'])
        print(f"  ✓ Inference successful")
        print(f"  Output shape: {output.shape}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Resize/inference failed: {e}")
        return False

def suggest_fix(success):
    print("\n" + "="*70)
    print("DIAGNOSIS & FIX")
    print("="*70)
    
    if success:
        print("""
✓ MODEL IS VALID - but requires explicit tensor resizing

Your Android code needs this fix in initializeModels():

textDetector = Interpreter(loadModelFile("dbnet_lite_320.tflite"), detOptions).apply {
    // CRITICAL: Must resize BEFORE allocateTensors()
    resizeInput(0, intArrayOf(1, 320, 320, 3))
    allocateTensors()
    Log.i(TAG, "Detection model ready: ${getInputTensor(0).shape().contentToString()}")
}

This is the ONLY way to handle dynamic-shaped TFLite models properly.
""")
    else:
        print("""
✗ MODEL HAS STRUCTURAL ISSUES

The model may have:
1. Multiple inputs (shape parameter + image)
2. Incorrect conversion from ONNX/PyTorch
3. Incompatible signature

RECOMMENDED FIXES:
A. Re-export the model with fixed input shape [1,320,320,3]
B. Use TFLite Model Maker with proper configuration
C. Convert using:
   
   converter = tf.lite.TFLiteConverter.from_saved_model(saved_model_dir)
   converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
   # Force input shape
   converter.experimental_new_converter = True
   tflite_model = converter.convert()
""")

if __name__ == '__main__':
    success = inspect_model(MODEL_PATH)
    suggest_fix(success)
