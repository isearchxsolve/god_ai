from ultralytics import YOLO
import onnxruntime as ort
import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageOps

MODEL_PT = "runs/detect/yolo_ui_s_model/weights/best.pt"
MODEL_ONNX = "runs/detect/yolo_ui_s_model/weights/best.onnx"
IMAGE_PATH = "shits.jpg"
CONF_THRESHOLD = 0.005

def letterbox_resize(image, new_shape=(640, 640)):
    """Standard letterbox resize"""
    shape = image.shape[:2]
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))
    
    dw = new_shape[1] - new_unpad[0]
    dh = new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2
    
    if shape[::-1] != new_unpad:
        image = cv2.resize(image, new_unpad, interpolation=cv2.INTER_LINEAR)
    
    top = int(round(dh - 0.1))
    bottom = int(round(dh + 0.1))
    left = int(round(dw - 0.1))
    right = int(round(dw + 0.1))
    
    image = cv2.copyMakeBorder(image, top, bottom, left, right, 
                               cv2.BORDER_CONSTANT, value=(114, 114, 114))
    
    return image, r, (left, top)

def test_pytorch():
    """Test PyTorch model and print raw outputs"""
    print("="*60)
    print("PYTORCH MODEL TEST")
    print("="*60)
    
    model = YOLO(MODEL_PT)
    
    # Load image
    pil_img = Image.open(IMAGE_PATH)
    pil_img = ImageOps.exif_transpose(pil_img)
    
    # Run with verbose to see what's happening
    results = model.predict(
        pil_img, 
        conf=CONF_THRESHOLD,
        imgsz=640,
        verbose=True
    )
    
    result = results[0]
    boxes = result.boxes
    
    print(f"\n📊 PyTorch Results:")
    print(f"   Total detections: {len(boxes)}")
    print(f"   Image shape used: {result.orig_shape}")
    
    # Print all boxes with their scores
    if len(boxes) > 0:
        print(f"\n📦 Boxes (xyxy format):")
        for i, (box, conf) in enumerate(zip(boxes.xyxy.cpu().numpy(), boxes.conf.cpu().numpy())):
            x1, y1, x2, y2 = box
            w, h = x2 - x1, y2 - y1
            print(f"   Box {i+1}: [{int(x1):4d}, {int(y1):4d}, {int(x2):4d}, {int(y2):4d}] "
                  f"Size: {int(w):3d}x{int(h):3d} Conf: {conf:.4f}")
    
    return boxes.xyxy.cpu().numpy(), boxes.conf.cpu().numpy()

def test_onnx():
    """Test ONNX model and print raw outputs"""
    print("\n" + "="*60)
    print("ONNX MODEL TEST")
    print("="*60)
    
    session = ort.InferenceSession(MODEL_ONNX, providers=['CPUExecutionProvider'])
    input_name = session.get_inputs()[0].name
    
    # Load and preprocess
    pil_img = Image.open(IMAGE_PATH)
    pil_img = ImageOps.exif_transpose(pil_img)
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    orig_h, orig_w = img.shape[:2]
    
    img_resized, scale, (pad_w, pad_h) = letterbox_resize(img, (640, 640))
    
    print(f"\n📐 Preprocessing:")
    print(f"   Original: {orig_w}x{orig_h}")
    print(f"   Resized: {img_resized.shape[1]}x{img_resized.shape[0]}")
    print(f"   Scale: {scale:.4f}, Padding: ({pad_w}, {pad_h})")
    
    # Prepare input
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    img_input = img_rgb.astype(np.float32) / 255.0
    img_input = img_input.transpose(2, 0, 1)[np.newaxis, ...]
    
    # Run inference
    outputs = session.run(None, {input_name: img_input})
    
    # Process output
    if outputs[0].shape[1] == 5:
        predictions = outputs[0].transpose(0, 2, 1)[0]
    else:
        predictions = outputs[0][0]
    
    print(f"\n📊 ONNX Raw Output:")
    print(f"   Output shape: {outputs[0].shape}")
    print(f"   Predictions shape: {predictions.shape}")
    
    # Filter by confidence
    confidences = predictions[:, 4]
    mask = confidences > CONF_THRESHOLD
    
    boxes_cxcywh = predictions[mask, :4]
    filtered_conf = confidences[mask]
    
    print(f"\n📌 Before NMS: {len(boxes_cxcywh)} detections")
    
    # Convert to xyxy and scale back
    boxes_xyxy = np.zeros_like(boxes_cxcywh)
    boxes_xyxy[:, 0] = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2
    boxes_xyxy[:, 1] = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2
    boxes_xyxy[:, 2] = boxes_cxcywh[:, 0] + boxes_cxcywh[:, 2] / 2
    boxes_xyxy[:, 3] = boxes_cxcywh[:, 1] + boxes_cxcywh[:, 3] / 2
    
    # Remove padding and scale back
    boxes_xyxy[:, [0, 2]] -= pad_w
    boxes_xyxy[:, [1, 3]] -= pad_h
    boxes_xyxy /= scale
    
    # Clip
    boxes_xyxy[:, [0, 2]] = np.clip(boxes_xyxy[:, [0, 2]], 0, orig_w)
    boxes_xyxy[:, [1, 3]] = np.clip(boxes_xyxy[:, [1, 3]], 0, orig_h)
    
    # Print all boxes before NMS
    print(f"\n📦 Boxes before NMS (sorted by confidence):")
    sorted_indices = np.argsort(filtered_conf)[::-1]
    for i in sorted_indices:
        x1, y1, x2, y2 = boxes_xyxy[i]
        w, h = x2 - x1, y2 - y1
        print(f"   Box {i+1}: [{int(x1):4d}, {int(y1):4d}, {int(x2):4d}, {int(y2):4d}] "
              f"Size: {int(w):3d}x{int(h):3d} Conf: {filtered_conf[i]:.4f}")
    
    # Try multiple NMS thresholds
    print(f"\n🔍 Testing different NMS thresholds:")
    for iou_thresh in [0.3, 0.45, 0.5, 0.6, 0.7, 0.8]:
        indices = cv2.dnn.NMSBoxes(
            boxes_xyxy.tolist(),
            filtered_conf.tolist(),
            CONF_THRESHOLD,
            iou_thresh
        )
        print(f"   IOU={iou_thresh}: {len(indices)} detections")
    
    return boxes_xyxy, filtered_conf

def compare_outputs(pt_boxes, pt_conf, onnx_boxes, onnx_conf):
    """Compare PyTorch and ONNX outputs"""
    print("\n" + "="*60)
    print("COMPARISON")
    print("="*60)
    
    print(f"\nPyTorch: {len(pt_boxes)} detections")
    print(f"ONNX (before NMS): {len(onnx_boxes)} detections")
    
    # Check if any PyTorch boxes are missing from ONNX
    print(f"\n🔍 Checking if PyTorch boxes exist in ONNX output...")
    
    for i, (pt_box, pt_c) in enumerate(zip(pt_boxes, pt_conf)):
        found = False
        for j, (onnx_box, onnx_c) in enumerate(zip(onnx_boxes, onnx_conf)):
            # Check if boxes overlap significantly
            iou = calculate_iou(pt_box, onnx_box)
            if iou > 0.5:
                conf_diff = abs(pt_c - onnx_c)
                print(f"   PyTorch Box {i+1} ≈ ONNX Box {j+1} (IOU: {iou:.2f}, "
                      f"Conf diff: {conf_diff:.4f})")
                found = True
                break
        
        if not found:
            print(f"   ⚠️  PyTorch Box {i+1} NOT FOUND in ONNX output!")
            print(f"       [{int(pt_box[0])}, {int(pt_box[1])}, {int(pt_box[2])}, {int(pt_box[3])}] "
                  f"Conf: {pt_c:.4f}")

def calculate_iou(box1, box2):
    """Calculate IoU between two boxes"""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection
    
    return intersection / union if union > 0 else 0

if __name__ == "__main__":
    if not Path(MODEL_PT).exists() or not Path(MODEL_ONNX).exists():
        print("❌ Model files not found!")
    elif not Path(IMAGE_PATH).exists():
        print("❌ Image not found!")
    else:
        pt_boxes, pt_conf = test_pytorch()
        onnx_boxes, onnx_conf = test_onnx()
        compare_outputs(pt_boxes, pt_conf, onnx_boxes, onnx_conf)