import tensorflow as tf
import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageOps

# === CONFIGURATION ===
MODEL_PATH = "runs/detect/google_toxic_detector_v2/weights/verified/best_saved_model/best_float16.tflite" 
IMAGE_PATH = "shits.png" 

# 🛑 TUNING 1: Lower Confidence to catch missed content
# Was 0.55 -> Now 0.30 (Catch faint detections)
CONF_THRESHOLD = 0.5    

# 🛑 TUNING 2: Moderate NMS
# Keeps distinct boxes but merges tight overlaps
IOU_THRESHOLD = 0.7      

# 🛑 TUNING 3: Relaxed Size Filter
# Was 0.12 (12%) -> Now 0.05 (5%)
# Ensures we don't delete valid small thumbnails in a grid
MIN_BOX_SIZE_RATIO = 0.05

# 🛑 TUNING 4: Aggressive Containment
# If 70% of a box is inside another, delete it.
CONTAINMENT_THRESHOLD = 0.70

IMG_SIZE = 640            

# Masking Padding
PAD_SIDE_PCT = 0.40  
PAD_TOP_PCT = 0.20   
PAD_BOTTOM_PCT = 0.60 

def letterbox_resize(img, size=320):
    """Resizes image to square size with gray padding (Letterbox)"""
    h, w = img.shape[:2]
    scale = min(size / h, size / w)
    nh, nw = int(h * scale), int(w * scale)
    img_resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    pad_x = (size - nw) // 2
    pad_y = (size - nh) // 2
    canvas[pad_y:pad_y+nh, pad_x:pad_x+nw] = img_resized
    return canvas, scale, pad_x, pad_y

def is_rect_contained(inner, outer, threshold=0.70):
    """Checks if 'inner' box is >70% contained inside 'outer' box"""
    ix1, iy1, ix2, iy2 = inner
    ox1, oy1, ox2, oy2 = outer

    # Calculate Intersection
    xx1 = max(ix1, ox1)
    yy1 = max(iy1, oy1)
    xx2 = min(ix2, ox2)
    yy2 = min(iy2, oy2)

    w = max(0, xx2 - xx1)
    h = max(0, yy2 - yy1)
    inter_area = w * h
    
    inner_area = (ix2 - ix1) * (iy2 - iy1)
    
    # If intersection covers >70% of the inner box, consider it contained
    return inner_area > 0 and (inter_area / inner_area) > threshold

def filter_contained_boxes(boxes, scores):
    """Removes boxes that are inside larger boxes (Fixes Center Overlap)"""
    if not boxes: return [], []
    
    # Calculate area for each box
    areas = [(b[2]-b[0]) * (b[3]-b[1]) for b in boxes]
    
    # Sort by Area DESCENDING (Largest boxes processed first)
    # Structure: (box, score, area)
    combined = zip(boxes, scores, areas)
    sorted_items = sorted(combined, key=lambda x: x[2], reverse=True)
    
    final_boxes = []
    final_scores = []
    
    for box, score, area in sorted_items:
        is_redundant = False
        # Check if this box is largely inside any of the ALREADY ACCEPTED larger boxes
        for big_box in final_boxes:
            if is_rect_contained(box, big_box, CONTAINMENT_THRESHOLD):
                is_redundant = True
                break
        
        if not is_redundant:
            final_boxes.append(box)
            final_scores.append(score)
            
    return final_boxes, final_scores

def run_tflite_inference(model_path, image_path):
    print("=" * 60)
    print(f"🚀 SafeScreen Logic Debugger (Tuned V2)")
    print("=" * 60)
    
    try:
        interpreter = tf.lite.Interpreter(model_path=model_path)
        interpreter.allocate_tensors()
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        return

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    
    try:
        pil_img = Image.open(image_path)
        pil_img = ImageOps.exif_transpose(pil_img)
        img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        orig_h, orig_w = img_cv.shape[:2]
        print(f"🖼️  Image Loaded: {orig_w}x{orig_h}")
    except Exception as e:
        print(f"❌ Error loading image: {e}")
        return
    
    # Preprocess
    img_padded, scale, pad_x, pad_y = letterbox_resize(img_cv, IMG_SIZE)
    input_data = img_padded.astype(np.float32) / 255.0
    input_data = np.expand_dims(input_data, axis=0)
    
    # Inference
    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()
    output_data = interpreter.get_tensor(output_details[0]['index']) 
    
    output = output_data[0] 
    num_anchors = output.shape[1]
    
    boxes = []
    scores = []
    
    min_pixel_size = IMG_SIZE * MIN_BOX_SIZE_RATIO 
    
    print(f"🔍 Filtering anchors (Min Size: {min_pixel_size:.1f}px)...")
    
    for i in range(num_anchors):
        conf = output[4, i]
        
        if conf > CONF_THRESHOLD:
            cx = output[0, i]
            cy = output[1, i]
            w  = output[2, i]
            h  = output[3, i]
            
            # Normalization Check
            if w < 2.0 and h < 2.0:
                cx *= IMG_SIZE; cy *= IMG_SIZE
                w *= IMG_SIZE; h *= IMG_SIZE
            
            # 🛑 FILTER 1: Size Check
            if w < min_pixel_size or h < min_pixel_size:
                continue

            # Coordinate Mapping
            x_unpad = (cx - w/2) - pad_x
            y_unpad = (cy - h/2) - pad_y
            x2_unpad = (cx + w/2) - pad_x
            y2_unpad = (cy + h/2) - pad_y
            
            x1 = int(x_unpad / scale)
            y1 = int(y_unpad / scale)
            x2 = int(x2_unpad / scale)
            y2 = int(y2_unpad / scale)
            
            # Clip
            x1 = max(0, min(orig_w, x1))
            y1 = max(0, min(orig_h, y1))
            x2 = max(0, min(orig_w, x2))
            y2 = max(0, min(orig_h, y2))
            
            if x2 > x1 and y2 > y1:
                boxes.append([x1, y1, x2, y2]) 
                scores.append(float(conf))

    if not boxes:
        print("❌ No detections passed filters.")
        return

    # 🛑 PASS 1: Standard NMS (Fixes duplicates)
    nms_input_boxes = [[b[0], b[1], b[2]-b[0], b[3]-b[1]] for b in boxes]
    indices = cv2.dnn.NMSBoxes(nms_input_boxes, scores, CONF_THRESHOLD, IOU_THRESHOLD)
    
    if len(indices) == 0:
        print("❌ No detections after NMS.")
        return

    # Extract NMS results
    kept_boxes = []
    kept_scores = []
    for i in indices:
        idx = i[0] if isinstance(i, (list, tuple, np.ndarray)) else i
        kept_boxes.append(boxes[idx])
        kept_scores.append(scores[idx])

    # 🛑 PASS 2: Containment Filter (Fixes boxes inside boxes)
    final_boxes, final_scores = filter_contained_boxes(kept_boxes, kept_scores)
    
    print(f"✅ Final Detections: {len(final_boxes)} (Cleaned from {len(indices)} raw)")

    # Draw
    vis_img = img_cv.copy()
    
    for i in range(len(final_boxes)):
        x1, y1, x2, y2 = final_boxes[i]
        conf = final_scores[i]
        w = x2 - x1
        h = y2 - y1
        
        # Masking Padding
        px = int(w * PAD_SIDE_PCT)
        pt = int(h * PAD_TOP_PCT)
        pb = int(h * PAD_BOTTOM_PCT)
        
        mx1 = max(0, x1 - px)
        my1 = max(0, y1 - pt)
        mx2 = min(orig_w, x2 + px)
        my2 = min(orig_h, y2 + pb)
        
        # Draw Red Bounding Box
        cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 0, 255), 3)
        
        # Draw Black Mask
        overlay = vis_img.copy()
        cv2.rectangle(overlay, (mx1, my1), (mx2, my2), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, vis_img, 0.4, 0, vis_img)
        
        # Label
        label = f"{conf:.2f}"
        cv2.putText(vis_img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        print(f"   🔹 Box: {w}x{h} Conf: {conf:.2f}")

    # Save
    out_path = f"tuned_v2_{Path(image_path).name}"
    cv2.imwrite(out_path, vis_img)
    print(f"\n💾 Saved result to: {out_path}")

if __name__ == "__main__":
    if not Path(MODEL_PATH).exists():
        print(f"❌ Model not found at: {MODEL_PATH}")
    else:
        run_tflite_inference(MODEL_PATH, IMAGE_PATH)