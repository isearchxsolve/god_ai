import cv2
import numpy as np
import random
from pathlib import Path
from tqdm import tqdm
import shutil
import sys

# === CONFIGURATION ===
TOXIC_SOURCE = Path("final_dataset/train/unsafe") 
BACKGROUNDS = Path("final_dataset/backgrounds")
OUTPUT_DIR = Path("yolo_ui_dataset")

# Minimum dataset size for good training.
# If your source images are fewer than this, we loop through them.
# If you have MORE source images, this number will increase automatically.
MIN_IMAGES_PER_EPOCH = 8000 

if sys.stdout.encoding != 'utf-8':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

# Colors for UI Cards (Light & Dark Mode)
CARD_COLORS = [
    (255, 255, 255), (245, 245, 245), (230, 230, 230), # Light
    (30, 30, 30), (18, 18, 18), (50, 50, 50)           # Dark
]

def setup_dirs():
    if OUTPUT_DIR.exists(): shutil.rmtree(OUTPUT_DIR)
    for split in ["train", "val"]:
        (OUTPUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

def add_drop_shadow(bg, x, y, w, h, blur=15):
    """Simulates Android elevation shadow"""
    h_bg, w_bg = bg.shape[:2]
    
    # Draw shadow rectangle slightly offset/larger
    sx, sy = x - 2, y + 2
    sw, sh = w + 4, h + 4
    
    # Boundary checks
    if sx < 0: sx = 0
    if sy < 0: sy = 0
    if sx + sw > w_bg: sw = w_bg - sx
    if sy + sh > h_bg: sh = h_bg - sy
    
    if sw <= 0 or sh <= 0: return

    # Create shadow mask
    shadow = np.zeros_like(bg, dtype=np.float32)
    shadow[sy:sy+sh, sx:sx+sw] = (0, 0, 0)
    shadow = cv2.GaussianBlur(shadow, (blur*2+1, blur*2+1), 0)
    
    # Blend (Multiply background by inverted shadow opacity)
    alpha = shadow / 255.0 * 0.3 
    roi = bg.astype(np.float32)
    bg[:] = (roi * (1.0 - alpha)).astype(np.uint8)

def create_ui_card(toxic_img, target_width):
    """Builds a UI card with image + fake text"""
    img_h, img_w = toxic_img.shape[:2]
    aspect = img_h / img_w
    
    padding = int(target_width * 0.04) 
    inner_width = target_width - (padding * 2)
    inner_height = int(inner_width * aspect)
    
    if inner_width <= 0 or inner_height <= 0: return None, 0, 0
    
    try:
        resized_toxic = cv2.resize(toxic_img, (inner_width, inner_height))
    except: return None, 0, 0

    # Text area height (random variance)
    text_area_height = int(target_width * random.uniform(0.2, 0.4))
    card_height = padding + inner_height + text_area_height + padding
    
    # Pick color
    if random.random() > 0.2:
        bg_val = random.randint(245, 255)
        bg_color = (bg_val, bg_val, bg_val)
    else:
        bg_color = (30, 30, 30)

    card = np.zeros((card_height, target_width, 3), dtype=np.uint8)
    card[:] = bg_color
    
    # Paste Image
    y_offset = padding
    x_offset = padding
    try:
        card[y_offset:y_offset+inner_height, x_offset:x_offset+inner_width] = resized_toxic
    except: return None, 0, 0

    # Draw Fake Text
    is_light = np.mean(bg_color) > 128
    text_color = (80, 80, 80) if is_light else (200, 200, 200)
    text_y = y_offset + inner_height + padding
    
    # Title Line
    cv2.rectangle(card, (padding, text_y), (target_width - padding*2, text_y + 12), text_color, -1)
    # Description Lines
    for i in range(2):
        line_y = text_y + 25 + (i * 15)
        width_var = int(target_width * random.uniform(0.5, 0.9))
        cv2.rectangle(card, (padding, line_y), (width_var, line_y + 8), text_color, -1)

    return card, target_width, card_height

def is_overlapping(new_rect, occupied_regions):
    """Prevents cards from sitting on top of each other"""
    nx, ny, nw, nh = new_rect
    for (ox, oy, ow, oh) in occupied_regions:
        if (nx < ox + ow and nx + nw > ox and
            ny < oy + oh and ny + nh > oy):
            return True
    return False

def generate_sample(bg_path, toxic_source_list, current_idx, image_id, split):
    """
    Generates 1 synthetic image containing 1-3 toxic cards.
    Uses 'current_idx' to pick the next sequential image from the list.
    Returns the new index.
    """
    bg = cv2.imread(str(bg_path))
    if bg is None: return current_idx
    
    bg_h, bg_w = bg.shape[:2]
    labels = []
    occupied_regions = [] # (x,y,w,h)
    
    # Place 1 to 3 cards per screenshot
    num_cards = random.randint(1, 3)
    
    for _ in range(num_cards):
        # === EXHAUSTIVE SELECTION ===
        # Use modulo to loop back to start if we run out of images
        real_idx = current_idx % len(toxic_source_list)
        toxic_path = toxic_source_list[real_idx]
        current_idx += 1
        
        toxic_img = cv2.imread(str(toxic_path))
        if toxic_img is None: continue

        # Randomize layout style (Grid vs List)
        if random.random() > 0.5:
            target_card_w = int(bg_w * random.uniform(0.42, 0.48)) # ~45% width
        else:
            target_card_w = int(bg_w * random.uniform(0.85, 0.95)) # ~90% width

        card, card_w, card_h = create_ui_card(toxic_img, target_card_w)
        if card is None: continue

        if bg_w - card_w <= 0 or bg_h - card_h <= 0: continue
        
        # Find valid position (Collision Detection)
        best_x, best_y = -1, -1
        found_spot = False
        
        for _ in range(25): # Try 25 random spots
            x = random.randint(0, bg_w - card_w)
            y = random.randint(0, bg_h - card_h)
            
            if not is_overlapping((x, y, card_w, card_h), occupied_regions):
                best_x, best_y = x, y
                found_spot = True
                break
        
        if not found_spot: continue

        # Apply Shadow if bg is light
        if np.mean(bg) > 100:
            add_drop_shadow(bg, best_x, best_y, card_w, card_h)

        # Paste
        bg[best_y:best_y+card_h, best_x:best_x+card_w] = card
        occupied_regions.append((best_x, best_y, card_w, card_h))

        # Label the CARD (Context)
        cx = (best_x + card_w / 2) / bg_w
        cy = (best_y + card_h / 2) / bg_h
        nw = card_w / bg_w
        nh = card_h / bg_h
        labels.append(f"0 {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

    # Save to disk
    out_name = f"ui_{image_id}.jpg"
    cv2.imwrite(str(OUTPUT_DIR / "images" / split / out_name), bg)
    with open(OUTPUT_DIR / "labels" / split / f"ui_{image_id}.txt", "w") as f:
        f.write("\n".join(labels))
        
    return current_idx

def main():
    setup_dirs()
    
    # 1. Load ALL toxic images
    print("Scanning for toxic images...")
    toxic_images = list(TOXIC_SOURCE.glob("*.*"))
    toxic_images = [p for p in toxic_images if p.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']]
    
    # Load backgrounds
    backgrounds = list(BACKGROUNDS.glob("*.*"))
    backgrounds = [p for p in backgrounds if p.suffix.lower() in ['.jpg', '.jpeg', '.png']]
    
    if not backgrounds:
        print("❌ Error: No background screenshots found in 'final_dataset/backgrounds'")
        return
    if not toxic_images:
        print(f"❌ Error: No toxic images found in {TOXIC_SOURCE}")
        return

    print(f"Found {len(toxic_images)} unique toxic source images.")
    
    # 2. Shuffle once (random order, but deterministic coverage)
    random.shuffle(toxic_images)

    # 3. Dynamic Epoch Size Calculation
    # We want to ensure every image is used at least once.
    # On average, we put ~2 cards per synthetic image.
    required_synthetic_images = int(len(toxic_images) / 1.5)
    
    # Use the larger of: (Requirement for full coverage) OR (Minimum set size)
    final_epoch_size = max(MIN_IMAGES_PER_EPOCH, required_synthetic_images)
    
    print(f"Goal: Ensure full coverage.")
    print(f"Generating {final_epoch_size} synthetic images for training.")

    # Create YAML config
    with open("toxic_ui.yaml", "w") as f:
        f.write(f"path: {OUTPUT_DIR.absolute().as_posix()}\ntrain: images/train\nval: images/val\nnames:\n  0: toxic_card")

    # 4. Generate Data (Sequential Access)
    train_cursor = 0
    val_cursor = 0 # Use separate cursor for validation to keep it diverse

    for i in tqdm(range(final_epoch_size), desc="Generating Train Set"):
        train_cursor = generate_sample(
            random.choice(backgrounds), 
            toxic_images, 
            train_cursor, 
            i, 
            "train"
        )
        
    for i in tqdm(range(500), desc="Generating Val Set"):
        val_cursor = generate_sample(
            random.choice(backgrounds), 
            toxic_images, 
            val_cursor, 
            i, 
            "val"
        )

    print("\n" + "="*60)
    print("✅ DATASET GENERATION COMPLETE")
    print(f"📁 Location: {OUTPUT_DIR}")
    print(f"🔄 Coverage: Each toxic image appeared approx {train_cursor // len(toxic_images)} times.")
    print("="*60)

if __name__ == "__main__":
    main()