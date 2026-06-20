"""
auto_dataset_cleaner.py - Automatically clean and reorganize dataset
(Windows Safe Version - No Console Emojis)

This script:
1. Scans your current dataset
2. Identifies likely false positives using heuristics
3. Automatically moves them from 'unsafe' -> 'safe'
4. Creates a cleaned dataset ready for retraining
5. Generates a detailed report
"""

import shutil
from pathlib import Path
from PIL import Image
import numpy as np
import onnxruntime as ort
from torchvision import transforms
import json
from collections import defaultdict
import sys

# Force UTF-8 for output if possible, otherwise rely on ASCII
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Configuration
SOURCE_DATASET = Path("final_dataset")
CLEANED_DATASET = Path("cleaned_dataset")
REPORT_PATH = Path("cleaning_report")
ONNX_MODEL = "best_toxic_detector.onnx"

# Auto-relabeling rules (conservative - only move obvious false positives)
RULES = {
    'cartoon_emoji': {
        'color_variety': 0.05,      # Very low color variety
        'max_confidence': 0.92,      # Below 92% confidence
        'description': 'Cartoon/emoji style with low confidence'
    },
    'text_heavy': {
        'edge_density': 0.18,        # High edge density (text)
        'max_confidence': 0.90,      # Below 90% confidence
        'description': 'Text-heavy image with low confidence'
    },
    'borderline': {
        'min_confidence': 0.60,      # Between 60-85%
        'max_confidence': 0.85,
        'description': 'Borderline prediction (likely false positive)'
    },
    'very_low': {
        'max_confidence': 0.70,      # Very low confidence
        'description': 'Very low confidence unsafe prediction'
    }
}


class AutoDatasetCleaner:
    def __init__(self, model_path):
        """Initialize with ONNX model"""
        print("[*] Initializing Auto Dataset Cleaner...")
        self.session = ort.InferenceSession(
            model_path, 
            providers=['CPUExecutionProvider']
        )
        
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        
        # Statistics
        self.stats = {
            'total_unsafe': 0,
            'moved_to_safe': 0,
            'kept_as_unsafe': 0,
            'by_rule': defaultdict(int),
            'moved_images': []
        }
    
    def predict(self, image_path):
        """Get model prediction"""
        img = Image.open(image_path).convert("RGB")
        input_tensor = self.transform(img).unsqueeze(0).numpy()
        
        logits = self.session.run(None, {"input": input_tensor})[0][0]
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / exp_logits.sum()
        
        return float(probs[1])  # Probability of unsafe
    
    def analyze_image(self, image_path):
        """Get image characteristics"""
        img = Image.open(image_path).convert("RGB")
        img_array = np.array(img)
        
        # Edge density (high for text)
        gray = np.mean(img_array, axis=2).astype(np.uint8)
        edges_y = np.abs(np.diff(gray, axis=0))
        edges_x = np.abs(np.diff(gray, axis=1))
        edge_density = (np.sum(edges_y > 50) + np.sum(edges_x > 50)) / gray.size
        
        # Color variety (low for cartoons/emojis)
        unique_colors = len(np.unique(img_array.reshape(-1, 3), axis=0))
        color_variety = unique_colors / (img_array.shape[0] * img_array.shape[1])
        
        # Brightness variance (uniform for synthetic images)
        brightness = np.mean(img_array, axis=2)
        brightness_variance = np.var(brightness) / 255.0
        
        return {
            'edge_density': edge_density,
            'color_variety': color_variety,
            'brightness_variance': brightness_variance
        }
    
    def should_relabel(self, confidence, characteristics):
        """Determine if image should be moved from unsafe -> safe"""
        
        # Rule 1: Very low confidence (below 70%)
        if confidence < RULES['very_low']['max_confidence']:
            return True, 'very_low'
        
        # Rule 2: Borderline predictions (60-85%)
        if (RULES['borderline']['min_confidence'] <= confidence <= 
            RULES['borderline']['max_confidence']):
            return True, 'borderline'
        
        # Rule 3: Cartoon/emoji style with low confidence
        if (characteristics['color_variety'] < RULES['cartoon_emoji']['color_variety'] and
            confidence < RULES['cartoon_emoji']['max_confidence']):
            return True, 'cartoon_emoji'
        
        # Rule 4: Text-heavy with low confidence
        if (characteristics['edge_density'] > RULES['text_heavy']['edge_density'] and
            confidence < RULES['text_heavy']['max_confidence']):
            return True, 'text_heavy'
        
        return False, None
    
    def process_dataset(self):
        """Main processing: scan, analyze, move images"""
        print("\n[INFO] Scanning dataset...\n")
        
        # Process each split (train, val, test)
        for split in ['train', 'val', 'test']:
            unsafe_dir = SOURCE_DATASET / split / 'unsafe'
            
            if not unsafe_dir.exists():
                continue
            
            print(f"Processing {split} split...")
            images = list(unsafe_dir.glob("*.jpg")) + list(unsafe_dir.glob("*.png"))
            self.stats['total_unsafe'] += len(images)
            
            for i, img_path in enumerate(images, 1):
                if i % 100 == 0:
                    print(f"  {i}/{len(images)} processed...")
                
                try:
                    # Analyze image
                    confidence = self.predict(img_path)
                    characteristics = self.analyze_image(img_path)
                    
                    # Decide if should relabel
                    should_move, rule = self.should_relabel(confidence, characteristics)
                    
                    # Create cleaned dataset structure
                    if should_move:
                        # Move to safe folder
                        dest_dir = CLEANED_DATASET / split / 'safe'
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest_path = dest_dir / img_path.name
                        
                        shutil.copy2(img_path, dest_path)
                        
                        self.stats['moved_to_safe'] += 1
                        self.stats['by_rule'][rule] += 1
                        self.stats['moved_images'].append({
                            'path': str(img_path.relative_to(SOURCE_DATASET)),
                            'confidence': confidence,
                            'rule': rule,
                            'characteristics': characteristics
                        })
                    else:
                        # Keep as unsafe
                        dest_dir = CLEANED_DATASET / split / 'unsafe'
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest_path = dest_dir / img_path.name
                        
                        shutil.copy2(img_path, dest_path)
                        self.stats['kept_as_unsafe'] += 1
                
                except Exception as e:
                    print(f"  Error processing {img_path.name}: {e}")
            
            # Copy all safe images unchanged
            safe_dir = SOURCE_DATASET / split / 'safe'
            if safe_dir.exists():
                dest_safe_dir = CLEANED_DATASET / split / 'safe'
                dest_safe_dir.mkdir(parents=True, exist_ok=True)
                
                for img_path in safe_dir.glob("*"):
                    if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                        shutil.copy2(img_path, dest_safe_dir / img_path.name)
        
        self.generate_report()
    
    def generate_report(self):
        """Generate detailed cleaning report"""
        print("\n[INFO] Generating report...\n")
        
        REPORT_PATH.mkdir(exist_ok=True)
        
        # === Generate JSON report ===
        json_report = {
            'summary': {
                'total_unsafe_images': self.stats['total_unsafe'],
                'moved_to_safe': self.stats['moved_to_safe'],
                'kept_as_unsafe': self.stats['kept_as_unsafe'],
                'percentage_relabeled': round(
                    100 * self.stats['moved_to_safe'] / max(1, self.stats['total_unsafe']), 2
                )
            },
            'by_rule': dict(self.stats['by_rule']),
            'moved_images': self.stats['moved_images'][:100]  # First 100 examples
        }
        
        # FIX: Explicitly use utf-8 encoding for file writing
        (REPORT_PATH / 'cleaning_report.json').write_text(
            json.dumps(json_report, indent=2), encoding='utf-8'
        )
        
        # === Generate HTML report ===
        html_parts = [
            "<!DOCTYPE html><html><head>",
            "<meta charset='utf-8'>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }",
            ".container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }",
            "h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }",
            ".summary { background: #ecf0f1; padding: 20px; border-radius: 5px; margin: 20px 0; }",
            ".stat-box { display: inline-block; margin: 10px 20px; }",
            ".stat-number { font-size: 36px; font-weight: bold; color: #3498db; }",
            ".stat-label { color: #7f8c8d; }",
            ".rule-breakdown { margin: 30px 0; }",
            ".rule-item { background: white; border-left: 4px solid #3498db; padding: 15px; margin: 10px 0; }",
            ".success { color: #27ae60; font-weight: bold; }",
            ".warning { color: #e67e22; }",
            "table { width: 100%; border-collapse: collapse; margin: 20px 0; }",
            "th { background: #34495e; color: white; padding: 12px; text-align: left; }",
            "td { padding: 10px; border-bottom: 1px solid #ecf0f1; }",
            "tr:hover { background: #f8f9fa; }",
            ".confidence { font-weight: bold; }",
            ".high { color: #e74c3c; }",
            ".medium { color: #f39c12; }",
            ".low { color: #27ae60; }",
            "</style>",
            "</head><body><div class='container'>",
            "<h1>Dataset Cleaning Report</h1>",
            
            # Summary section
            "<div class='summary'>",
            "<h2>Summary</h2>",
            f"<div class='stat-box'><div class='stat-number'>{self.stats['total_unsafe']}</div><div class='stat-label'>Total Unsafe Images</div></div>",
            f"<div class='stat-box'><div class='stat-number success'>{self.stats['moved_to_safe']}</div><div class='stat-label'>Moved to Safe</div></div>",
            f"<div class='stat-box'><div class='stat-number'>{self.stats['kept_as_unsafe']}</div><div class='stat-label'>Kept as Unsafe</div></div>",
            f"<div class='stat-box'><div class='stat-number warning'>{json_report['summary']['percentage_relabeled']}%</div><div class='stat-label'>Relabeled</div></div>",
            "</div>",
            
            # Rule breakdown
            "<div class='rule-breakdown'>",
            "<h2>Relabeling Rules Applied</h2>",
        ]
        
        for rule_name, count in self.stats['by_rule'].items():
            description = RULES[rule_name]['description']
            html_parts.append(
                f"<div class='rule-item'>"
                f"<strong>{rule_name.replace('_', ' ').title()}</strong>: {count} images<br>"
                f"<small>{description}</small>"
                f"</div>"
            )
        
        html_parts.append("</div>")
        
        # Sample moved images
        html_parts.extend([
            "<h2>Sample Moved Images (First 50)</h2>",
            "<table>",
            "<thead><tr><th>Original Path</th><th>Confidence</th><th>Rule</th></tr></thead>",
            "<tbody>"
        ])
        
        for img_info in self.stats['moved_images'][:50]:
            conf = img_info['confidence']
            conf_class = 'high' if conf > 0.85 else ('medium' if conf > 0.70 else 'low')
            
            html_parts.append(
                f"<tr>"
                f"<td>{img_info['path']}</td>"
                f"<td class='confidence {conf_class}'>{conf:.1%}</td>"
                f"<td>{img_info['rule'].replace('_', ' ').title()}</td>"
                f"</tr>"
            )
        
        html_parts.extend([
            "</tbody></table>",
            "</div></body></html>"
        ])
        
        # FIX: Explicitly use utf-8 encoding for file writing
        (REPORT_PATH / 'cleaning_report.html').write_text("\n".join(html_parts), encoding='utf-8')
        
        print("="*70)
        print("[OK] CLEANING COMPLETE!")
        print("="*70)
        print(f"\nResults:")
        print(f"  * Original unsafe images: {self.stats['total_unsafe']}")
        print(f"  * Moved to safe:          {self.stats['moved_to_safe']} ({json_report['summary']['percentage_relabeled']}%)")
        print(f"  * Kept as unsafe:         {self.stats['kept_as_unsafe']}")
        print(f"\n[>] Cleaned dataset:   {CLEANED_DATASET.absolute()}")
        print(f"[>] HTML report:       {(REPORT_PATH / 'cleaning_report.html').absolute()}")
        print(f"[>] JSON report:       {(REPORT_PATH / 'cleaning_report.json').absolute()}")
        
        print("\n" + "="*70)
        print("NEXT STEPS:")
        print("="*70)
        print(f"1. Review report: open {REPORT_PATH / 'cleaning_report.html'}")
        print(f"2. Train with cleaned data:")
        print(f"   - Rename: final_dataset -> final_dataset_backup")
        print(f"   - Rename: cleaned_dataset -> final_dataset")
        print(f"   - Run: python train_toxic_detector.py")
        print(f"3. Convert to ONNX: python convert_to_onnx_and_tflite.py")
        print(f"4. Test: python inference.py")
        print("="*70)


def main():
    """Main execution"""
    cleaner = AutoDatasetCleaner(ONNX_MODEL)
    cleaner.process_dataset()


if __name__ == "__main__":
    main()