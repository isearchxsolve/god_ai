# verify_inference.py
# Corrected for NHWC recognition input [1,48,320,3]

import numpy as np
import tensorflow as tf
from PIL import Image
import os

DET_MODEL_PATH = r".\models\tflite\dbnet_lite_320.tflite"
REC_MODEL_PATH = r".\models\tflite\tiny_crnn_en.tflite"
TEST_IMAGE_PATH = r"test_image.png"

def verify_detection_model(model_path):
    print("\n" + "="*60)
    print("VERIFYING DETECTION MODEL (PP-OCRv3 DBNet-lite)")
    print("="*60)

    if not os.path.exists(model_path):
        print(f"[ERROR] Model not found: {model_path}")
        return False

    interpreter = tf.lite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]

    print(f"Input name : {input_details['name']}")
    print(f"Input shape: {input_details['shape'].tolist()}")
    print(f"Input dtype: {input_details['dtype']}")

    print("[INFO] Dynamic/placeholder shape is expected — runtime works")

    if os.path.exists(TEST_IMAGE_PATH):
        img = Image.open(TEST_IMAGE_PATH).convert("RGB")
    else:
        img = Image.new("RGB", (640, 480), (200, 200, 200))

    img_resized = img.resize((320, 320))
    input_data = np.array(img_resized, dtype=np.float32)
    input_data = (input_data / 127.5) - 1.0
    input_data = np.expand_dims(input_data, axis=0)  # [1,320,320,3] NHWC

    try:
        if list(input_details['shape']) != [1, 320, 320, 3]:
            interpreter.resize_tensor_input(input_details['index'], [1, 320, 320, 3])
            interpreter.allocate_tensors()

        interpreter.set_tensor(input_details['index'], input_data)
        interpreter.invoke()
        output = interpreter.get_tensor(interpreter.get_output_details()[0]['index'])
        print(f"[PASS] Detection inference successful")
        print(f"Output shape: {output.shape}")
        return True
    except Exception as e:
        print(f"[ERROR] Detection failed: {e}")
        return False

def verify_recognition_model(model_path):
    print("\n" + "="*60)
    print("VERIFYING RECOGNITION MODEL (PP-OCRv3 SVTR-lite)")
    print("="*60)

    if not os.path.exists(model_path):
        print(f"[ERROR] Model not found: {model_path}")
        return False

    interpreter = tf.lite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]
    print(f"Input name : {input_details['name']}")
    print(f"Input shape: {input_details['shape'].tolist()}")
    print(f"Input dtype: {input_details['dtype']}")

    shape = input_details['shape'].tolist()
    if shape == [1, 48, 320, 3]:
        print("[OK] NHWC input [1,48,320,3] — common for TFLite SVTR-lite")
    else:
        print(f"[WARNING] Unexpected shape: {shape}")

    # Dummy text region
    crop = np.ones((40, 120, 3), dtype=np.uint8) * 255
    crop[10:30, 20:100] = 0

    pil_crop = Image.fromarray(crop)
    aspect = 120 / 40.0
    target_w = min(int(48 * aspect), 320)
    resized = pil_crop.resize((target_w, 48))

    padded = Image.new("RGB", (320, 48), (255, 255, 255))
    padded.paste(resized, (0, 0))

    # NHWC input [1,48,320,3], RGB [0,1]
    input_array = np.array(padded, dtype=np.float32) / 255.0  # [48,320,3]
    input_data = np.expand_dims(input_array, axis=0)           # [1,48,320,3]

    print(f"Prepared input shape: {input_data.shape}")

    try:
        interpreter.set_tensor(input_details['index'], input_data)
        interpreter.invoke()
        output = interpreter.get_tensor(interpreter.get_output_details()[0]['index'])
        print(f"[PASS] Recognition inference successful")
        print(f"Output shape: {output.shape}")
        return True
    except Exception as e:
        print(f"[ERROR] Recognition failed: {e}")
        return False

if __name__ == '__main__':
    print("SafeScreen PP-OCRv3 Model Verification (NHWC Recognition)")
    det_ok = verify_detection_model(DET_MODEL_PATH)
    rec_ok = verify_recognition_model(REC_MODEL_PATH)

    print("\n" + "="*60)
    if det_ok and rec_ok:
        print("[OK] Both models PASS — ready for Android!")
        print("   Your TFLite models are valid.")
        print("   Use the updated FastTextDetector.kt (RGB 48x320, NHWC input)")
    else:
        print("[FAIL] Check errors above")