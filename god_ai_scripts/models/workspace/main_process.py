import os, sys, subprocess, onnx, numpy as np
try:
    from onnx import _mapping
    onnx.mapping = _mapping
except ImportError:
    pass
from onnx_tf.backend import prepare
import tensorflow as tf

def convert_and_test(paddle_dir, output_file, shape_str, venv_bin):
    onnx_file = output_file + ".onnx"
    sm_path = output_file + "_sm"
    p2o_cmd = os.path.join(venv_bin, "paddle2onnx.exe")
    
    # Stage 1: Paddle -> ONNX
    print(f"Stage 1: Paddle -> ONNX")
    cmd = [
        p2o_cmd,
        "--model_dir", paddle_dir,
        "--model_filename", "inference.pdmodel",
        "--params_filename", "inference.pdiparams",
        "--save_file", onnx_file,
        "--opset_version", "13",
        "--enable_onnx_checker", "True",
        "--input_shape", shape_str
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"CLI Error:\n{res.stderr}"); sys.exit(1)
    
    # Stage 2: ONNX -> TF
    print("Stage 2: ONNX -> TF SavedModel")
    onnx_model = onnx.load(onnx_file)
    tf_rep = prepare(onnx_model)
    tf_rep.export_graph(sm_path)
    
    # Stage 3: TF -> TFLite (FP16 Optimization)
    print("Stage 3: TF -> TFLite (FP16)")
    converter = tf.lite.TFLiteConverter.from_saved_model(sm_path)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    tflite_model = converter.convert()
    
    with open(output_file, 'wb') as f:
        f.write(tflite_model)
    
    print(f"SUCCESS: Generated {os.path.basename(output_file)}")

if __name__ == '__main__':
    # sys.argv[4] is the path to the venv Scripts folder
    convert_and_test(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
