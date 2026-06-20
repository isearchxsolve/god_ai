import argparse
from ultralytics import YOLO
import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageOps

# Visual feedback colors (BGR format)
COLOR_BOX = (0, 255, 255)      # Yellow for detection box
COLOR_MASK = (0, 0, 0)         # Black for final mask
COLOR_TEXT = (255, 255, 255)   # White for labels

# Padding strategy for masking
PAD_SIDE_PCT = 0.10
PAD_TOP_PCT = 0.10
PAD_BOTTOM_PCT = 0.40

def load_model(model_path):
    """Load custom YOLO model with error handling."""
    try:
        model = YOLO(model_path)
        print(f"✅ Loaded model: {model_path}")
        return model
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        print(f"   Attempted path: {model_path}")
        exit(1)

def load_image(image_path):
    """Load image with EXIF rotation handling."""
    try:
        pil_img = Image.open(image_path)
        pil_img = ImageOps.exif_transpose(pil_img)
        img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return pil_img, img_cv
    except Exception as e:
        print(f"❌ Error loading image: {e}")
        return None, None

def apply_nms(boxes, confidences, conf_threshold, iou_threshold=0.5):
    """Apply Non-Maximum Suppression to remove overlapping boxes."""
    if len(boxes) == 0:
        return []
    
    boxes_array = np.array(boxes)
    confidences_array = np.array(confidences)
    
    indices = cv2.dnn.NMSBoxes(
        boxes_array.tolist(),
        confidences_array.tolist(),
        conf_threshold,
        iou_threshold
    )
    
    if len(indices) > 0:
        return [boxes[i] for i in indices.flatten()]
    return []

def expand_box(x1, y1, x2, y2, w_orig, h_orig):
    """Expand detection box with asymmetric padding."""
    w_box = x2 - x1
    h_box = y2 - y1
    
    pad_x = int(w_box * PAD_SIDE_PCT)
    pad_top = int(h_box * PAD_TOP_PCT)
    pad_bottom = int(h_box * PAD_BOTTOM_PCT)
    
    # Apply expansion and clamp to boundaries
    nx1 = max(0, x1 - pad_x)
    ny1 = max(0, y1 - pad_top)
    nx2 = min(w_orig, x2 + pad_x)
    ny2 = min(h_orig, y2 + pad_bottom)
    
    return nx1, ny1, nx2, ny2

def draw_debug_overlay(img, boxes, confidences, save_path):
    """Create debug visualization showing detections before masking."""
    debug_img = img.copy()
    
    for idx, (box, conf) in enumerate(zip(boxes, confidences)):
        x1, y1, x2, y2 = box
        
        # Draw bounding box
        cv2.rectangle(debug_img, (x1, y1), (x2, y2), COLOR_BOX, 2)
        
        # Add label with confidence
        label = f"#{idx+1}: {conf:.2%}"
        (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(debug_img, (x1, y1 - text_h - 10), (x1 + text_w, y1), COLOR_BOX, -1)
        cv2.putText(debug_img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_TEXT, 2)
    
    cv2.imwrite(save_path, debug_img)
    print(f"   📊 Debug overlay saved: {save_path}")

def detect_and_mask(image_path, model_path, conf_threshold, iou_threshold, save_debug=True):
    """Main detection and masking pipeline."""
    model = load_model(model_path)
    
    # Load image
    pil_img, img_cv = load_image(image_path)
    if img_cv is None:
        return
    
    h_orig, w_orig = img_cv.shape[:2]
    print(f"\n📷 Processing: {image_path}")
    print(f"   Resolution: {w_orig}x{h_orig}")
    print(f"   Confidence threshold: {conf_threshold}")
    print(f"   IOU threshold: {iou_threshold}")

    # Determine mode description
    if conf_threshold <= 0.20:
        mode = "AGGRESSIVE (High Recall)"
    elif conf_threshold >= 0.40:
        mode = "CONSERVATIVE (High Precision)"
    else:
        mode = "BALANCED (Standard)"
    print(f"   Mode: {mode}")
    
    # Run inference
    results = model.predict(
        pil_img,
        conf=conf_threshold,
        imgsz=640,
        iou=iou_threshold,
        verbose=False
    )
    result = results[0]
    
    # Extract detections
    boxes = result.boxes.xyxy.cpu().numpy()
    confidences = result.boxes.conf.cpu().numpy()
    
    if len(boxes) == 0:
        print("   ✅ No toxic content detected")
        return
    
    print(f"\n🔍 Raw detections: {len(boxes)}")
    
    # Show individual detection confidences
    for idx, (box, conf) in enumerate(zip(boxes, confidences)):
        x1, y1, x2, y2 = map(int, box)
        print(f"   Detection #{idx+1}: confidence={conf:.4f} bbox=[{x1},{y1},{x2},{y2}]")
    
    # Apply NMS to remove overlaps
    boxes_list = [list(map(int, box)) for box in boxes]
    filtered_boxes = apply_nms(boxes_list, confidences, conf_threshold, iou_threshold)
    
    print(f"\n✂️  After NMS filtering: {len(filtered_boxes)} regions")
    
    if len(filtered_boxes) == 0:
        print("   ✅ All detections filtered out (likely false positives)")
        return
    
    # Save debug visualization if requested
    if save_debug:
        debug_path = f"debug_{Path(image_path).name}"
        # Match filtered boxes back to their confidences for display
        # Note: This simple mapping assumes NMS returns boxes in original order or we find them. 
        # For strict correctness, NMS indices are better, but this visualizer is approximate.
        # Re-extracting correct confidences for visualization:
        debug_confidences = []
        for fbox in filtered_boxes:
            # Find matching original box to get confidence
            for i, obox in enumerate(boxes_list):
                if fbox == obox:
                    debug_confidences.append(confidences[i])
                    break
            else:
                debug_confidences.append(0.0)

        draw_debug_overlay(img_cv, filtered_boxes, debug_confidences, debug_path)
    
    # Apply masking
    masked_img = img_cv.copy()
    print(f"\n🎨 Applying masks:")
    
    for idx, box in enumerate(filtered_boxes):
        x1, y1, x2, y2 = box
        
        # Expand box
        nx1, ny1, nx2, ny2 = expand_box(x1, y1, x2, y2, w_orig, h_orig)
        
        # Draw black mask
        cv2.rectangle(masked_img, (nx1, ny1), (nx2, ny2), COLOR_MASK, -1)
        
        print(f"   Block #{idx+1}: {nx2-nx1}x{ny2-ny1} at ({nx1},{ny1})")
    
    # Save output
    output_path = f"masked_{Path(image_path).name}"
    cv2.imwrite(output_path, masked_img)
    print(f"\n✅ Output saved: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLO Toxic Content Detection Inference")
    
    parser.add_argument("--source", type=str, required=True, help="Path to input image")
    parser.add_argument("--weights", type=str, default="runs/detect/google_toxic_detector_v2/weights/best.pt", help="Path to trained model weights")
    parser.add_argument("--conf", type=float, default=0.8, help="Confidence threshold (Default: 0.25). Use 0.15 for high recall, 0.45 for precision.")
    parser.add_argument("--iou", type=float, default=0.7, help="NMS IOU threshold (Default: 0.5)")
    parser.add_argument("--no-debug", action="store_true", help="Disable saving debug overlay image")

    args = parser.parse_args()
    
    if not Path(args.source).exists():
        print(f"❌ Error: Source file '{args.source}' not found")
        exit(1)

    detect_and_mask(
        image_path=args.source,
        model_path=args.weights,
        conf_threshold=args.conf,
        iou_threshold=args.iou,
        save_debug=not args.no_debug
    )