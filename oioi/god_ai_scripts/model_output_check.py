import tensorflow as tf
import numpy as np

interpreter = tf.lite.Interpreter(model_path="best_float32.tflite")
interpreter.allocate_tensors()

output_details = interpreter.get_output_details()
print(f"Output shape: {output_details[0]['shape']}")
print(f"Output dtype: {output_details[0]['dtype']}")

# Run dummy inference
input_details = interpreter.get_input_details()
dummy_input = np.random.rand(1, 640, 640, 3).astype(np.float32)
interpreter.set_tensor(input_details[0]['index'], dummy_input)
interpreter.invoke()

output = interpreter.get_tensor(output_details[0]['index'])
print(f"\nActual output shape: {output.shape}")
print(f"Sample cx values: {output[0, 0, :5]}")  # First 5 cx values
print(f"Sample conf values: {output[0, 4, :5]}")  # First 5 confidence values

# Check if normalized (0-1) or absolute (0-640)
if output.shape[1] == 5:  # [1, 5, 8400]
    print(f"\nMax cx: {output[0, 0, :].max()}")
    print(f"Min cx: {output[0, 0, :].min()}")