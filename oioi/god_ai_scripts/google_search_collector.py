"""
Google Search Screenshot Dataset Builder
For training on FULL search result pages (multiple thumbnails in grid layout)
This is the correct format for your use case!
"""

import cv2
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import shutil

# === CONFIGURATION ===
OUTPUT_DIR = Path("google_search_dataset")
SCREENSHOTS_DIR = Path("search_screenshots")  # Put your phone screenshots here
ANNOTATIONS_FILE = "search_annotations.json"

class SearchScreenshotProcessor:
    def __init__(self):
        self.setup_directories()
        self.annotations = self.load_annotations()
        
    def setup_directories(self):
        """Create directory structure"""
        for split in ["train", "val"]:
            (OUTPUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
            (OUTPUT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)
        SCREENSHOTS_DIR.mkdir(exist_ok=True)
        
    def load_annotations(self):
        """Load existing annotations"""
        if Path(ANNOTATIONS_FILE).exists():
            with open(ANNOTATIONS_FILE, 'r') as f:
                return json.load(f)
        return {"images": []}
    
    def save_annotations(self):
        """Save annotations"""
        with open(ANNOTATIONS_FILE, 'w') as f:
            json.dump(self.annotations, f, indent=2)
    
    def print_collection_guide(self):
        """Show how to collect screenshots"""
        print("\n" + "="*70)
        print("📱 HOW TO COLLECT GOOGLE SEARCH SCREENSHOTS")
        print("="*70)
        print("\n🎯 PERFECT! You want to train on actual search result pages.")
        print("   This is the CORRECT approach for your detector!\n")
        
        print("📸 Step 1: Take Screenshots on Your Phone")
        print("-" * 70)
        print("1. Open Google app (or Chrome) on your Android phone")
        print("2. Turn OFF SafeSearch:")
        print("   Settings → Search Settings → SafeSearch filters → Off")
        print()
        print("3. Search for explicit terms:")
        print("   - porn")
        print("   - xxx")
        print("   - sex videos")
        print("   - nsfw")
        print("   - explicit content")
        print("   - adult videos")
        print()
        print("4. Click 'Images' tab (like in your screenshot)")
        print()
        print("5. Take screenshot of the FULL results page")
        print("   - Should show 4-8 thumbnails in grid")
        print("   - Include the search bar at top")
        print("   - Include SafeSearch toggle")
        print()
        print("6. Scroll down and take MORE screenshots")
        print("   - Get different results")
        print("   - Aim for 50-100 screenshots total")
        print()
        print("7. Also take SAFE screenshots (no toxic content):")
        print("   - Search: 'cats', 'food', 'nature', 'technology'")
        print("   - Take 20-30 safe screenshots")
        print("   - These are important for reducing false positives!")
        print()
        
        print("📤 Step 2: Transfer to Computer")
        print("-" * 70)
        print("1. Connect phone to computer via USB")
        print("2. Copy screenshots to: search_screenshots/")
        print("3. Rename them clearly:")
        print("   - porn_search_01.png")
        print("   - porn_search_02.png")
        print("   - safe_cats_01.png")
        print("   - safe_food_01.png")
        print()
        
        print("🏷️  Step 3: Label with LabelImg")
        print("-" * 70)
        print("1. Install LabelImg:")
        print("   pip install labelImg")
        print()
        print("2. Run LabelImg:")
        print("   labelImg search_screenshots/")
        print()
        print("3. Set format to YOLO:")
        print("   - Click 'PascalVOC' button → Change to 'YOLO'")
        print()
        print("4. Create class file:")
        print("   - When prompted, create 'classes.txt'")
        print("   - Add one line: toxic_card")
        print()
        print("5. Draw boxes around EACH toxic thumbnail:")
        print("   - Press 'W' to start drawing box")
        print("   - Draw tight box around pornographic thumbnail")
        print("   - Select class: toxic_card")
        print("   - Press 'Ctrl+S' to save")
        print("   - Press 'D' for next image")
        print()
        print("6. For SAFE images (cats, food, etc.):")
        print("   - Don't draw any boxes")
        print("   - Just press 'Ctrl+S' to save empty label")
        print("   - This teaches the model what's NOT toxic")
        print()
        
        print("💡 IMPORTANT LABELING TIPS:")
        print("-" * 70)
        print("✓ Label ONLY the thumbnail images (the actual porn/content)")
        print("✓ Do NOT label:")
        print("  - Search bar")
        print("  - SafeSearch toggle")
        print("  - Site names (18porn.sex, xHamster, etc.)")
        print("  - Title text")
        print("  - Navigation buttons")
        print()
        print("✓ Box should be TIGHT around the thumbnail image only")
        print("✓ If video has play button/duration, include it in box")
        print("✓ If thumbnail is blurred by SafeSearch, still label it")
        print()
        
    def validate_screenshots(self):
        """Check collected screenshots"""
        print("\n" + "="*70)
        print("📊 Validating Collected Screenshots")
        print("="*70)
        
        if not SCREENSHOTS_DIR.exists():
            print(f"\n❌ Directory not found: {SCREENSHOTS_DIR}")
            return
        
        screenshots = list(SCREENSHOTS_DIR.glob("*.png")) + \
                     list(SCREENSHOTS_DIR.glob("*.jpg"))
        
        labeled = []
        unlabeled = []
        
        for img_path in screenshots:
            label_path = SCREENSHOTS_DIR / (img_path.stem + ".txt")
            if label_path.exists():
                labeled.append(img_path)
            else:
                unlabeled.append(img_path)
        
        print(f"\n📸 Total screenshots: {len(screenshots)}")
        print(f"✅ Labeled: {len(labeled)}")
        print(f"⏳ Unlabeled: {len(unlabeled)}")
        
        if len(unlabeled) > 0:
            print(f"\n⚠️  Unlabeled images:")
            for img in unlabeled[:10]:  # Show first 10
                print(f"   - {img.name}")
            if len(unlabeled) > 10:
                print(f"   ... and {len(unlabeled) - 10} more")
        
        # Count toxic boxes
        total_boxes = 0
        empty_labels = 0
        
        for label_path in SCREENSHOTS_DIR.glob("*.txt"):
            with open(label_path, 'r') as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
                if len(lines) == 0:
                    empty_labels += 1
                else:
                    total_boxes += len(lines)
        
        print(f"\n📦 Annotation Stats:")
        print(f"   Total toxic boxes: {total_boxes}")
        print(f"   Safe images (no boxes): {empty_labels}")
        print(f"   Avg boxes per toxic image: {total_boxes / max(1, len(labeled) - empty_labels):.1f}")
        
        # Recommendations
        print("\n" + "="*70)
        print("📋 Recommendations:")
        print("="*70)
        
        if len(screenshots) < 50:
            print(f"⚠️  Need more screenshots! (have {len(screenshots)}, need 50+)")
        else:
            print(f"✅ Good number of screenshots ({len(screenshots)})")
        
        if total_boxes < 100:
            print(f"⚠️  Need more toxic boxes! (have {total_boxes}, need 100+)")
        else:
            print(f"✅ Good number of annotations ({total_boxes} boxes)")
        
        if empty_labels < 10:
            print("⚠️  Need more SAFE images (10-20 recommended)")
            print("   → Take screenshots of: cats, food, nature, cars")
        else:
            print(f"✅ Good number of safe images ({empty_labels})")
        
        return len(labeled) > 0
    
    def prepare_dataset(self, train_split=0.85):
        """Split into train/val and organize"""
        print("\n" + "="*70)
        print("📦 Preparing Dataset")
        print("="*70)
        
        # Get all labeled images
        images = []
        for img_path in SCREENSHOTS_DIR.glob("*.png"):
            label_path = SCREENSHOTS_DIR / (img_path.stem + ".txt")
            if label_path.exists():
                images.append(img_path)
        
        for img_path in SCREENSHOTS_DIR.glob("*.jpg"):
            label_path = SCREENSHOTS_DIR / (img_path.stem + ".txt")
            if label_path.exists():
                images.append(img_path)
        
        if len(images) == 0:
            print("❌ No labeled images found!")
            return
        
        # Shuffle
        np.random.shuffle(images)
        
        # Split
        split_idx = int(len(images) * train_split)
        train_images = images[:split_idx]
        val_images = images[split_idx:]
        
        print(f"\n📊 Dataset Split:")
        print(f"   Training: {len(train_images)} images")
        print(f"   Validation: {len(val_images)} images")
        
        # Copy to output directory
        print("\n📁 Copying files...")
        
        for split_name, split_images in [("train", train_images), ("val", val_images)]:
            for img_path in split_images:
                # Copy image
                dest_img = OUTPUT_DIR / "images" / split_name / img_path.name
                shutil.copy(img_path, dest_img)
                
                # Copy label
                label_path = SCREENSHOTS_DIR / (img_path.stem + ".txt")
                dest_label = OUTPUT_DIR / "labels" / split_name / (img_path.stem + ".txt")
                shutil.copy(label_path, dest_label)
        
        print("✅ Dataset prepared!")
        
        # Create YAML
        self.create_yaml()
    
    def create_yaml(self):
        """Create YOLO training config"""
        yaml_content = f"""# Google Search Screenshot Dataset
path: {OUTPUT_DIR.absolute().as_posix()}
train: images/train
val: images/val

# Classes
nc: 1
names: ['toxic_card']

# Dataset info:
# - Full Google search result pages
# - Multiple thumbnails per image (grid layout)
# - Includes UI elements (search bar, SafeSearch toggle)
# - Mix of toxic and safe search results
"""
        yaml_path = "google_search_data.yaml"
        with open(yaml_path, 'w') as f:
            f.write(yaml_content)
        
        print(f"\n✅ Created config: {yaml_path}")
        return yaml_path
    
    def visualize_annotations(self, num_samples=5):
        """Show some annotated samples"""
        print("\n" + "="*70)
        print("🎨 Creating Visualization")
        print("="*70)
        
        viz_dir = Path("visualization")
        viz_dir.mkdir(exist_ok=True)
        
        # Get some training images
        train_dir = OUTPUT_DIR / "images" / "train"
        if not train_dir.exists():
            print("❌ No training images yet!")
            return
        
        images = list(train_dir.glob("*.png"))[:num_samples] + \
                 list(train_dir.glob("*.jpg"))[:num_samples]
        images = images[:num_samples]
        
        for img_path in images:
            # Load image
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            
            # Load labels
            label_path = OUTPUT_DIR / "labels" / "train" / (img_path.stem + ".txt")
            if not label_path.exists():
                continue
            
            # Draw boxes
            h, w = img.shape[:2]
            with open(label_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue
                    
                    # YOLO format: class x_center y_center width height (normalized)
                    cls, x_c, y_c, box_w, box_h = map(float, parts[:5])
                    
                    # Convert to pixel coordinates
                    x1 = int((x_c - box_w/2) * w)
                    y1 = int((y_c - box_h/2) * h)
                    x2 = int((x_c + box_w/2) * w)
                    y2 = int((y_c + box_h/2) * h)
                    
                    # Draw box
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 3)
                    cv2.putText(img, "TOXIC", (x1, y1-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Save
            output_path = viz_dir / f"annotated_{img_path.name}"
            cv2.imwrite(str(output_path), img)
            print(f"   Created: {output_path.name}")
        
        print(f"\n✅ Visualizations saved to: {viz_dir}/")


def main():
    print("="*70)
    print("🎯 Google Search Screenshot Dataset Builder")
    print("   For Full Search Result Pages (Multiple Thumbnails)")
    print("="*70)
    
    processor = SearchScreenshotProcessor()
    
    # Show collection guide
    processor.print_collection_guide()
    
    # Check if screenshots exist
    if SCREENSHOTS_DIR.exists():
        has_data = processor.validate_screenshots()
        
        if has_data:
            print("\n" + "="*70)
            response = input("\n📦 Prepare dataset now? (y/n): ").lower().strip()
            if response == 'y':
                processor.prepare_dataset()
                processor.visualize_annotations()
                
                print("\n" + "="*70)
                print("✅ DATASET READY!")
                print("="*70)
                print("\n🚀 Next step: Train the model")
                print("\nRun:")
                print("   python hybrid-trainer-enhanced.py")
                print("\nOr train directly:")
                print("   from ultralytics import YOLO")
                print("   model = YOLO('yolov8s.pt')")
                print("   model.train(data='google_search_data.yaml', epochs=100)")
    
    print("\n" + "="*70)
    print("📋 QUICK CHECKLIST:")
    print("="*70)
    print("☐ Take 50-100 Google search screenshots on phone")
    print("☐ Include 20-30 SAFE screenshots (cats, food, etc.)")
    print("☐ Transfer to search_screenshots/ folder")
    print("☐ Install LabelImg: pip install labelImg")
    print("☐ Label images: labelImg search_screenshots/")
    print("☐ Draw boxes around ONLY toxic thumbnails")
    print("☐ Save empty labels for safe images")
    print("☐ Run this script again to prepare dataset")
    print("☐ Train with hybrid-trainer-enhanced.py")
    print("="*70)

if __name__ == "__main__":
    main()
