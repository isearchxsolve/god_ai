import tensorflow as tf
import sys
import os

def verify(model_path):
    try:
        print(f"\nVerifying: {os.path.basename(model_path)}")
        interpreter = tf.lite.Interpreter(model_path=model_path)
        interpreter.allocate_tensors()
        
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        print("-" * 30)
        for i, detail in enumerate(input_details):
            print(f"INPUT {i}: {detail['name']} | Shape: {detail['shape']} | Type: {detail['dtype']}")
        
        for i, detail in enumerate(output_details):
            print(f"OUTPUT {i}: {detail['name']} | Shape: {detail['shape']} | Type: {detail['dtype']}")
        print("-" * 30)
        return True
    except Exception as e:
        print(f"VERIFICATION FAILED: {e}")
        return False

if __name__ == '__main__':
    if not verify(sys.argv[1]):
        sys.exit(1)
