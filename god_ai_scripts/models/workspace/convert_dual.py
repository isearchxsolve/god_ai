import os, sys, subprocess, onnx, tensorflow as tf
from onnx_tf.backend import prepare

def convert(paddle_dir, output_file, input_shape=None):
    onnx_file = output_file + ".onnx"
    sm_path = output_file + "_sm"
    
    print(f"Stage 1: Paddle -> ONNX for {os.path.basename(paddle_dir)}")
    cmd = [
        "paddle2onnx",
        "--model_dir", paddle_dir,
        "--model_filename", "inference.pdmodel",
        "--params_filename", "inference.pdiparams",
        "--save_file", onnx_file,
        "--opset_version", "13",
        "--enable_onnx_checker", "True"
    ]
    if input_shape:
        cmd.extend(["--input_shape_dict", input_shape])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"CLI Error: {result.stderr}")
        sys.exit(1)
    
    print("Stage 2: ONNX -> TF SavedModel")
    onnx_model = onnx.load(onnx_file)
    tf_rep = prepare(onnx_model)
    tf_rep.export_graph(sm_path)
    
    print("Stage 3: TF -> TFLite (FP16 Optimization)")
    converter = tf.lite.TFLiteConverter.from_saved_model(sm_path)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    converter.inference_input_type = tf.float32
    converter.inference_output_type = tf.float32
    
    tflite_model = converter.convert()
    with open(output_file, 'wb') as f:
        f.write(tflite_model)

if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
