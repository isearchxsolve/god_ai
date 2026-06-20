import os, sys, onnx
try:
    from onnx import _mapping
    onnx.mapping = _mapping
except ImportError:
    pass
from onnx_tf.backend import prepare
import tensorflow as tf
import paddle2onnx

def convert(paddle_dir, output_file, shape_dict):
    onnx_file = output_file + ".onnx"
    sm_path = output_file + "_sm"
    
    print(f"Stage 1: Paddle -> ONNX (Applying 13-arg signature)")
    
    # Exact positional arguments required by your environment:
    # 0:model, 1:params, 2:opset, 3:auto_upgrade, 4:verbose, 5:checker, 
    # 6:experimental, 7:optimize, 8:custom_ops, 9:backend, 10:calibration, 
    # 11:external, 12:fp16
    
    paddle2onnx.export(
        os.path.join(paddle_dir, 'inference.pdmodel'), # arg0
        os.path.join(paddle_dir, 'inference.pdiparams'),# arg1
        13,                 # arg2: opset
        True,               # arg3: auto_upgrade
        True,               # arg4: verbose
        True,               # arg5: checker
        True,               # arg6: experimental
        True,               # arg7: optimize
        shape_dict,         # arg8: custom_ops/input_shape_dict
        "onnxruntime",      # arg9: deploy_backend
        "",                 # arg10: calibration_file
        "",                 # arg11: external_filename
        False               # arg12: export_fp16_model
    )
    
    print("Stage 2: ONNX -> TF SavedModel")
    onnx_model = onnx.load(onnx_file)
    tf_rep = prepare(onnx_model)
    tf_rep.export_graph(sm_path)
    
    print("Stage 3: TF -> TFLite (FP16)")
    converter = tf.lite.TFLiteConverter.from_saved_model(sm_path)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    with open(output_file, 'wb') as f:
        f.write(converter.convert())

if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2], eval(sys.argv[3]))
