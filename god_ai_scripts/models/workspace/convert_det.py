import os, sys, onnx
import tensorflow as tf
from onnx_tf.backend import prepare
import paddle2onnx

def convert(paddle_dir, output_file):
    onnx_file = output_file + ".onnx"
    model_file = os.path.join(paddle_dir, 'inference.pdmodel')
    params_file = os.path.join(paddle_dir, 'inference.pdiparams')
    
    print("Exporting Paddle to ONNX (Corrected Signature)...")
    # Correct 13-argument signature:
    # 0:model_file, 1:params_file, 2:opset_version (INT), 3:auto_upgrade, 4:verbose, 
    # 5:enable_onnx_checker, 6:enable_experimental_op, 7:enable_optimize, 
    # 8:custom_ops, 9:deploy_backend, 10:calibration_file, 11:external_file, 12:export_fp16_model
    
    onnx_bytes = paddle2onnx.export(
        model_file,         # arg0: str (model path)
        params_file,        # arg1: str (params path)
        13,                 # arg2: int (opset_version) - THIS MUST BE AN INTEGER
        True,               # arg3: bool (auto_upgrade)
        True,               # arg4: bool (verbose)
        True,               # arg5: bool (enable_onnx_checker)
        True,               # arg6: bool (enable_experimental_op)
        True,               # arg7: bool (enable_optimize)
        {},                 # arg8: dict[str, str] (custom_ops)
        "onnxruntime",      # arg9: str (deploy_backend)
        "",                 # arg10: str (calibration_file)
        "",                 # arg11: str (external_file)
        False               # arg12: bool (export_fp16_model)
    )
    
    # Save ONNX model
    with open(onnx_file, 'wb') as f:
        f.write(onnx_bytes)
    
    print(f"ONNX model saved to {onnx_file}")
    
    print("Converting ONNX to TensorFlow...")
    onnx_model = onnx.load(onnx_file)
    tf_rep = prepare(onnx_model)
    sm_path = output_file + "_sm"
    tf_rep.export_graph(sm_path)
    
    print("Optimizing TensorFlow to TFLite...")
    converter = tf.lite.TFLiteConverter.from_saved_model(sm_path)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    
    tflite_model = converter.convert()
    with open(output_file, 'wb') as f:
        f.write(tflite_model)
    
    print(f"TFLite model saved to {output_file}")

if __name__ == '__main__':
    try:
        convert(sys.argv[1], sys.argv[2])
    except Exception as e:
        print(f"Python Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
