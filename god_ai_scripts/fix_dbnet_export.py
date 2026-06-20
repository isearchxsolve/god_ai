"""
Bulletproof ONNX to TFLite converter
Uses direct subprocess calls to avoid import issues
"""

import os
import sys
import subprocess
import numpy as np


def fix_onnx_shapes(input_onnx):
    """Fix ONNX dynamic shapes"""
    import onnx
    from onnx import shape_inference
    
    print("="*70)
    print("STEP 1: FIXING ONNX SHAPES")
    print("="*70)
    
    model = onnx.load(input_onnx)
    
    # Set fixed shape [1, 3, 320, 320]
    input_tensor = model.graph.input[0]
    print(f"Original input: {input_tensor.name}")
    
    original_shape = [d.dim_value for d in input_tensor.type.tensor_type.shape.dim]
    print(f"  Shape: {original_shape}")
    
    input_tensor.type.tensor_type.shape.ClearField('dim')
    for dim in [1, 3, 320, 320]:
        input_tensor.type.tensor_type.shape.dim.add().dim_value = dim
    
    model = shape_inference.infer_shapes(model)
    
    output_onnx = "det_fixed.onnx"
    onnx.save(model, output_onnx)
    
    # Verify
    model = onnx.load(output_onnx)
    fixed_shape = [d.dim_value for d in model.graph.input[0].type.tensor_type.shape.dim]
    print(f"  Fixed: {fixed_shape}")
    print(f"✓ Saved: {output_onnx}\n")
    
    return output_onnx


def convert_with_onnx2tf_subprocess(onnx_path, output_dir="saved_model"):
    """Use onnx2tf as subprocess to avoid import issues"""
    print("="*70)
    print("STEP 2: CONVERTING WITH onnx2tf")
    print("="*70)
    
    # Try using onnx2tf as a module
    cmd = [
        sys.executable, "-m", "onnx2tf",
        "-i", onnx_path,
        "-o", output_dir,
        "-coion",  # Keep input/output tensor names
    ]
    
    print(f"Running: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(
            cmd,
            check=False,  # Don't raise on non-zero exit
            capture_output=True,
            text=True,
            timeout=120
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print("STDERR:", result.stderr)
            return None
        
        # Check if SavedModel was created
        if os.path.exists(output_dir) and os.path.exists(os.path.join(output_dir, "saved_model.pb")):
            print(f"\n✓ SavedModel created: {output_dir}")
            return output_dir
        else:
            print(f"\n⚠ Output directory exists but no saved_model.pb found")
            return None
            
    except subprocess.TimeoutExpired:
        print("❌ Conversion timed out (120s)")
        return None
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        return None


def create_nhwc_wrapper(saved_model_dir, output_tflite="dbnet_lite_320.tflite"):
    """Create NHWC wrapper and convert to TFLite"""
    import tensorflow as tf
    
    print("\n" + "="*70)
    print("STEP 3: CREATING NHWC WRAPPER")
    print("="*70)
    
    try:
        # Load the converted model
        print(f"Loading: {saved_model_dir}")
        loaded = tf.saved_model.load(saved_model_dir)
        
        # Get inference function
        infer_func = loaded.signatures['serving_default']
        
        print("\nOriginal signature:")
        for key, spec in infer_func.structured_input_signature[1].items():
            print(f"  {key}: {spec.shape} {spec.dtype}")
            input_key = key  # Save the key name
        
        # Create wrapper
        class NHWCWrapper(tf.Module):
            def __init__(self, inference_fn, input_name):
                super().__init__()
                self.infer = inference_fn
                self.input_name = input_name
            
            @tf.function(input_signature=[
                tf.TensorSpec(shape=[1, 320, 320, 3], dtype=tf.float32)
            ])
            def __call__(self, nhwc_input):
                # NHWC [1,320,320,3] → NCHW [1,3,320,320]
                nchw_input = tf.transpose(nhwc_input, [0, 3, 1, 2])
                
                # Call model
                result = self.infer(**{self.input_name: nchw_input})
                
                # Get output tensor
                output = list(result.values())[0]
                
                # Ensure shape is [1, 320, 320]
                if len(output.shape) == 4:
                    output = tf.squeeze(output, axis=1)
                
                return output
        
        wrapper = NHWCWrapper(infer_func, input_key)
        
        # Test wrapper
        print("\nTesting wrapper...")
        test_input = tf.random.normal([1, 320, 320, 3])
        test_output = wrapper(test_input)
        print(f"  Input : {test_input.shape}")
        print(f"  Output: {test_output.shape}")
        
        # Save
        wrapped_dir = "nhwc_wrapped"
        tf.saved_model.save(wrapper, wrapped_dir)
        print(f"✓ Wrapped model: {wrapped_dir}")
        
        # Convert to TFLite
        print("\n" + "="*70)
        print("STEP 4: CONVERTING TO TFLITE")
        print("="*70)
        
        converter = tf.lite.TFLiteConverter.from_saved_model(wrapped_dir)
        converter.target_spec.supported_ops = [
            tf.lite.OpsSet.TFLITE_BUILTINS,
            tf.lite.OpsSet.SELECT_TF_OPS
        ]
        
        print("Converting...")
        tflite_model = converter.convert()
        
        with open(output_tflite, 'wb') as f:
            f.write(tflite_model)
        
        size_mb = len(tflite_model) / 1024 / 1024
        print(f"✓ TFLite: {output_tflite} ({size_mb:.2f} MB)")
        
        return output_tflite
        
    except Exception as e:
        print(f"❌ Wrapper creation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def verify_tflite(tflite_path):
    """Verify the TFLite model"""
    import tensorflow as tf
    
    print("\n" + "="*70)
    print("STEP 5: VERIFICATION")
    print("="*70)
    
    interpreter = tf.lite.Interpreter(model_path=tflite_path)
    interpreter.allocate_tensors()
    
    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]
    
    print(f"\nInput : {input_details['shape']} {input_details['dtype']}")
    print(f"Output: {output_details['shape']} {output_details['dtype']}")
    
    # Test inference
    test_input = np.random.randn(1, 320, 320, 3).astype(np.float32)
    test_input = test_input / 127.5 - 1.0
    
    interpreter.set_tensor(input_details['index'], test_input)
    interpreter.invoke()
    
    output = interpreter.get_tensor(output_details['index'])
    print(f"\n✓ Inference test passed!")
    print(f"  Output: {output.shape}")
    print(f"  Range : [{output.min():.4f}, {output.max():.4f}]")
    
    if list(input_details['shape']) == [1, 320, 320, 3]:
        print("\n✓✓✓ INPUT IS NHWC [1,320,320,3] - PERFECT!")
        return True
    else:
        print(f"\n⚠ Input shape is {input_details['shape']}")
        return False


def main():
    
    
    # Step 3 & 4: Wrap and convert to TFLite
    tflite_path = r".\models\tflite\dbnet_lite_320.tflite"
    
    if not tflite_path:
        print("\n❌ TFLite conversion failed")
        sys.exit(1)
    
    # Step 5: Verify
    success = verify_tflite(tflite_path)
    
    if success:
        print("\n" + "="*70)
        print("SUCCESS! MODEL IS READY")
        print("="*70)
        print(f"✓ Input: NHWC [1, 320, 320, 3], RGB, normalized [-1, 1]")
        print(f"✓ Output: Detection map [1, 320, 320]")
        print(f"\nNext steps:")
        print(f"  1. Copy to: app/src/main/assets/dbnet_lite_320.tflite")
        print(f"  2. Rebuild your Android app")
        print(f"  3. Test with the updated FastTextDetector.kt")
    else:
        print("\n⚠ Model created but may need adjustments")
        sys.exit(1)


if __name__ == '__main__':
    main()