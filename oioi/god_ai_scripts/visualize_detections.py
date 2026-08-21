import cv2
import numpy as np
from PIL import Image, ImageOps

IMAGE_PATH = "shits.jpg"

# Your current detections (from the log)
detections = [
    {"box": [527, 551, 1066, 878], "conf": 0.135, "name": "Box 0"},
    {"box": [32, 1063, 547, 1416], "conf": 0.056, "name": "Box 3"},
    {"box": [20, 1515, 550, 1892], "conf": 0.018, "name": "Box 9"},
]

# Padding settings
PAD_SIDE_PCT = 0.40
PAD_TOP_PCT = 0.20
PAD_BOTTOM_PCT = 0.60

# Load image
pil_img = Image.open(IMAGE_PATH)
pil_img = ImageOps.exif_transpose(pil_img)
img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
orig_h, orig_w = img_cv.shape[:2]

# Draw original boxes in RED
img_boxes = img_cv.copy()
for det in detections:
    x1, y1, x2, y2 = det["box"]
    cv2.rectangle(img_boxes, (x1, y1), (x2, y2), (0, 0, 255), 3)
    cv2.putText(img_boxes, f"{det['name']}: {det['conf']:.3f}", 
                (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

# Draw padded boxes in GREEN
img_padded = img_cv.copy()
for det in detections:
    x1, y1, x2, y2 = det["box"]
    
    w_box = x2 - x1
    h_box = y2 - y1
    
    pad_x_mask = int(w_box * PAD_SIDE_PCT)
    pad_top = int(h_box * PAD_TOP_PCT)
    pad_bottom = int(h_box * PAD_BOTTOM_PCT)
    
    nx1 = max(0, x1 - pad_x_mask)
    ny1 = max(0, y1 - pad_top)
    nx2 = min(orig_w, x2 + pad_x_mask)
    ny2 = min(orig_h, y2 + pad_bottom)
    
    cv2.rectangle(img_padded, (nx1, ny1), (nx2, ny2), (0, 255, 0), 3)
    cv2.putText(img_padded, f"{det['name']} padded", 
                (nx1, ny1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    print(f"{det['name']}:")
    print(f"  Original: [{x1}, {y1}, {x2}, {y2}] size={w_box}x{h_box}")
    print(f"  Padding: sides=±{pad_x_mask}px, top=±{pad_top}px, bottom=+{pad_bottom}px")
    print(f"  Padded:   [{nx1}, {ny1}, {nx2}, {ny2}] size={nx2-nx1}x{ny2-ny1}")
    print()

# Save visualizations
cv2.imwrite("debug_original_boxes.jpg", img_boxes)
cv2.imwrite("debug_padded_boxes.jpg", img_padded)

print("=" * 60)
print("Saved visualization files:")
print("  debug_original_boxes.jpg - Shows raw detection boxes (RED)")
print("  debug_padded_boxes.jpg   - Shows padded boxes (GREEN)")
print("=" * 60)
print("\nCheck if the GREEN boxes cover all visible content")
print("If not, the model is genuinely missing detections")
print("=" * 60)

# Analyze coverage gaps
print("\nCoverage Analysis:")
print(f"Image dimensions: {orig_w}x{orig_h}")

# Check vertical gaps
detections_sorted = sorted(detections, key=lambda d: d["box"][1])  # Sort by y1

for i in range(len(detections_sorted) - 1):
    det1 = detections_sorted[i]
    det2 = detections_sorted[i + 1]
    
    x1, y1, x2, y2 = det1["box"]
    w_box = x2 - x1
    h_box = y2 - y1
    pad_bottom = int(h_box * PAD_BOTTOM_PCT)
    padded_y2 = min(orig_h, y2 + pad_bottom)
    
    next_x1, next_y1, next_x2, next_y2 = det2["box"]
    next_h_box = next_y2 - next_y1
    next_pad_top = int(next_h_box * PAD_TOP_PCT)
    next_padded_y1 = max(0, next_y1 - next_pad_top)
    
    if padded_y2 < next_padded_y1:
        gap = next_padded_y1 - padded_y2
        print(f"⚠️  Vertical gap found: {gap}px between {det1['name']} and {det2['name']}")
        print(f"   Gap region: y={padded_y2} to y={next_padded_y1}")
    else:
        overlap = padded_y2 - next_padded_y1
        print(f"✅ Vertical overlap: {overlap}px between {det1['name']} and {det2['name']}")

# Check horizontal coverage for first box (the problematic one)
det = detections[0]
x1, y1, x2, y2 = det["box"]
w_box = x2 - x1
pad_x = int(w_box * PAD_SIDE_PCT)
nx1 = max(0, x1 - pad_x)
nx2 = min(orig_w, x2 + pad_x)

print(f"\nBox 0 horizontal coverage:")
print(f"  Left edge: x={nx1} (covers left {nx1/orig_w*100:.1f}% of image)")
print(f"  Right edge: x={nx2} (covers right {(orig_w-nx2)/orig_w*100:.1f}% uncovered)")

if nx1 > orig_w * 0.25:
    print(f"  ⚠️  Large portion of left side ({nx1}px) is uncovered!")
    print(f"     Content at x=0-{nx1} may be visible")
else:
    print(f"  ✅ Good left coverage")