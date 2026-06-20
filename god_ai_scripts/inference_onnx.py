import onnxruntime as ort
import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageOps

# === CONFIGURATION ===
MODEL_PATH = "runs/detect/yolo_ui_s_model/weights/best.onnx"
IMAGE_PATH = "shits.jpg"
CONF_THRESHOLD = 0.005      # Increased from 0.005 to reduce noise
IOU_THRESHOLD = 0.7       # Standard NMS threshold
TARGET_SIZE = 640          # Model expects strict 640x640

def letterbox_resize(image, target_size=640):
    """
    Resize and PAD image to strictly meet target_size (640x640).
    The model requires a square input, so we add gray borders.
    """
    shape = image.shape[:2]  # current shape [height, width]
    
    # Calculate scale ratio (new / old) to fit into target_size
    r = min(target_size / shape[0], target_size / shape[1])

    # Compute new unpadded size
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    
    # Compute padding (width, height)
    dw, dh = target_size - new_unpad[0], target_size - new_unpad[1]

    # Divide padding by 2 to center the image
    dw /= 2  
    dh /= 2

    # Resize the image if necessary
    if shape[::-1] != new_unpad:
        image = cv2.resize(image, new_unpad, interpolation=cv2.INTER_LINEAR)

    # Add border (color 114 is standard YOLO gray)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    
    # This creates the exact 640x640 image
    image = cv2.copyMakeBorder(image, top, bottom, left, right, 
                               cv2.BORDER_CONSTANT, value=(114, 114, 114))

    # Return image, scale ratio, and padding (x, y)
    return image, r, (left, top)

def preprocess_image(image_path, target_size=640):
    """Load and preprocess image for YOLO inference."""
    # Load with PIL to handle EXIF rotation automatically
    pil_img = Image.open(image_path)
    pil_img = ImageOps.exif_transpose(pil_img)
    
    # Convert to OpenCV format (BGR)
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    original_image = img.copy()
    orig_h, orig_w = img.shape[:2]
    
    print(f"📷 Original Image: {orig_w}x{orig_h}")
    
    # Apply letterbox resize (add padding to make it square)
    img_resized, scale, (pad_w, pad_h) = letterbox_resize(img, target_size)
    
    print(f"📐 Resized Input: {img_resized.shape[1]}x{img_resized.shape[0]} "
          f"(scale={scale:.3f}, pad_w={pad_w}, pad_h={pad_h})")
    
    # Convert BGR to RGB
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    
    # Normalize to [0, 1]
    img_normalized = img_rgb.astype(np.float32) / 255.0
    
    # Transpose HWC -> CHW and add batch dimension -> BCHW
    img_input = np.expand_dims(img_normalized.transpose(2, 0, 1), axis=0)
    
    return img_input, original_image, scale, (pad_w, pad_h), (orig_w, orig_h)

def postprocess_output(output, orig_size, scale, padding, conf_thresh, iou_thresh):
    """Filter boxes and map coordinates back to original image."""
    orig_w, orig_h = orig_size
    pad_w, pad_h = padding
    
    # Handle output shape [1, 5, 8400] vs [1, 8400, 5]
    predictions = output[0].transpose(1, 0) if output.shape[1] == 5 else output[0]
    
    # Extract columns
    boxes_cxcywh = predictions[:, :4]
    scores = predictions[:, 4]
    
    # Filter by confidence
    mask = scores > conf_thresh
    boxes_cxcywh = boxes_cxcywh[mask]
    scores = scores[mask]
    
    if len(boxes_cxcywh) == 0:
        return []

    # Convert center-xywh to top-left-xyxy
    boxes_xyxy = np.zeros_like(boxes_cxcywh)
    boxes_xyxy[:, 0] = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2  # x1
    boxes_xyxy[:, 1] = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2  # y1
    boxes_xyxy[:, 2] = boxes_cxcywh[:, 0] + boxes_cxcywh[:, 2] / 2  # x2
    boxes_xyxy[:, 3] = boxes_cxcywh[:, 1] + boxes_cxcywh[:, 3] / 2  # y2
    
    # === CRITICAL FIX: Remove Padding first, then Scale ===
    boxes_xyxy[:, [0, 2]] -= pad_w  # Remove x padding
    boxes_xyxy[:, [1, 3]] -= pad_h  # Remove y padding
    boxes_xyxy /= scale             # Scale back to original size
    
    # Clip boxes to image boundaries
    boxes_xyxy[:, [0, 2]] = np.clip(boxes_xyxy[:, [0, 2]], 0, orig_w)
    boxes_xyxy[:, [1, 3]] = np.clip(boxes_xyxy[:, [1, 3]], 0, orig_h)
    
    # NMS
    indices = cv2.dnn.NMSBoxes(
        boxes_xyxy.tolist(), scores.tolist(), conf_thresh, iou_thresh
    )
    
    final_boxes = []
    if len(indices) > 0:
        for idx in indices.flatten():
            x1, y1, x2, y2 = boxes_xyxy[idx]
            final_boxes.append([int(x1), int(y1), int(x2), int(y2), float(scores[idx])])
            
    return final_boxes

def draw_masked_boxes(image, boxes, inflate_pct=(0.10, 0.10, 0.40)):
    """Draw solid black boxes over detections."""
    result = image.copy()
    side_pct, top_pct, bottom_pct = inflate_pct
    
    for box in boxes:
        x1, y1, x2, y2, conf = box
        w, h = x2 - x1, y2 - y1
        
        # Calculate inflated coordinates
        nx1 = max(0, x1 - int(w * side_pct))
        ny1 = max(0, y1 - int(h * top_pct))
        nx2 = min(image.shape[1], x2 + int(w * side_pct))
        ny2 = min(image.shape[0], y2 + int(h * bottom_pct))
        
        cv2.rectangle(result, (nx1, ny1), (nx2, ny2), (0, 0, 0), -1)
        print(f"   [Mask] {nx2-nx1}x{ny2-ny1} at ({nx1},{ny1}) Conf: {conf:.2f}")
        
    return result

def run_onnx_inference():
    if not Path(MODEL_PATH).exists() or not Path(IMAGE_PATH).exists():
        print("❌ Error: Model or Image file not found.")
        return

    # Initialize Session - default to CPU to avoid DLL errors if CUDA is broken
    print(f"🚀 Loading Model: {MODEL_PATH}")
    try:
        session = ort.InferenceSession(MODEL_PATH, providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
    except Exception as e:
        print(f"⚠️ CUDA Provider failed, falling back to CPU. Error: {e}")
        session = ort.InferenceSession(MODEL_PATH, providers=['CPUExecutionProvider'])

    input_name = session.get_inputs()[0].name
    
    # Preprocess
    img_input, orig_img, scale, padding, orig_size = preprocess_image(IMAGE_PATH, TARGET_SIZE)
    
    # Inference
    print("🔍 Running inference...")
    outputs = session.run(None, {input_name: img_input})
    
    # Postprocess
    final_boxes = postprocess_output(
        outputs[0], orig_size, scale, padding, CONF_THRESHOLD, IOU_THRESHOLD
    )
    
    print(f"📊 Detections: {len(final_boxes)}")
    
    if final_boxes:
        result_img = draw_masked_boxes(orig_img, final_boxes)
        output_path = f"masked_{Path(IMAGE_PATH).name}"
        cv2.imwrite(output_path, result_img)
        print(f"✅ Saved to: {output_path}")
    else:
        print("🤷‍♂️ No detections found.")

if __name__ == "__main__":
    run_onnx_inference()