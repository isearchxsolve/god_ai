import tensorflow as tf
import sys
try:
    interpreter = tf.lite.Interpreter(model_path=sys.argv[1])
    interpreter.allocate_tensors()
    print(f"Model verified. Input shape: {interpreter.get_input_details()[0]['shape']}")
except Exception as e:
    print(f"Verification failed: {e}")
    sys.exit(1)
