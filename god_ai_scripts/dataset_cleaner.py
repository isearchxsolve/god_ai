"""
dataset_cleaner.py - Remove false positives from training data

This script helps identify and remove images that are incorrectly labeled
as "unsafe" (like poop emojis, mild profanity text, memes)
"""

import shutil
from pathlib import Path
from PIL import Image
import torch
from torchvision import transforms
import onnxruntime as ort
import numpy as np

# Configuration
DATASET_PATH = Path("final_dataset")
ONNX_MODEL = "best_toxic_detector.onnx"
OUTPUT_PATH = Path("cleaned_dataset")
REVIEW_PATH = Path("needs_review")

# Categories to review
REVIEW_CATEGORIES = {
    'text_heavy': [],      # Images with lots of text
    'cartoon_style': [],   # Cartoon/emoji style images
    'borderline': []       # 60-80% confidence unsafe predictions
}


class DatasetCleaner:
    def __init__(self, model_path):
        """Initialize ONNX model for predictions"""
        self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
    
    def predict(self, image_path):
        """Get model prediction and confidence"""
        img = Image.open(image_path).convert("RGB")
        input_tensor = self.transform(img).unsqueeze(0).numpy()
        
        logits = self.session.run(None, {"input": input_tensor})[0][0]
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / exp_logits.sum()
        
        return float(probs[1])  # Probability of unsafe
    
    def is_text_heavy(self, image_path):
        """Heuristic: detect if image has lots of text"""
        img = Image.open(image_path).convert("L")  # Grayscale
        img_array = np.array(img)
        
        # Text tends to have high edge density
        edges = np.abs(np.diff(img_array, axis=0))
        edge_ratio = np.sum(edges > 50) / edges.size
        
        return edge_ratio > 0.15  # Adjust threshold as needed
    
    def is_cartoon_style(self, image_path):
        """Heuristic: detect cartoon/emoji style"""
        img = Image.open(image_path).convert("RGB")
        img_array = np.array(img)
        
        # Cartoons have fewer unique colors
        unique_colors = len(np.unique(img_array.reshape(-1, 3), axis=0))
        total_pixels = img_array.shape[0] * img_array.shape[1]
        
        return unique_colors / total_pixels < 0.05  # Low color variety
    
    def scan_dataset(self):
        """Scan dataset and identify images needing review"""
        print("🔍 Scanning dataset for potential false positives...\n")
        
        unsafe_images = list((DATASET_PATH / "train" / "unsafe").glob("*.jpg"))
        unsafe_images += list((DATASET_PATH / "val" / "unsafe").glob("*.jpg"))
        
        total = len(unsafe_images)
        reviewed = 0
        
        for img_path in unsafe_images:
            reviewed += 1
            if reviewed % 100 == 0:
                print(f"Progress: {reviewed}/{total} images reviewed")
            
            try:
                # Get model confidence
                unsafe_prob = self.predict(img_path)
                
                # Check image characteristics
                is_text = self.is_text_heavy(img_path)
                is_cartoon = self.is_cartoon_style(img_path)
                
                # Flag for review based on criteria
                if 0.60 <= unsafe_prob <= 0.85:
                    # Borderline predictions - likely false positives
                    REVIEW_CATEGORIES['borderline'].append((img_path, unsafe_prob))
                
                if is_text and unsafe_prob < 0.95:
                    # Text-heavy images with lower confidence
                    REVIEW_CATEGORIES['text_heavy'].append((img_path, unsafe_prob))
                
                if is_cartoon and unsafe_prob < 0.95:
                    # Cartoon style with lower confidence
                    REVIEW_CATEGORIES['cartoon_style'].append((img_path, unsafe_prob))
            
            except Exception as e:
                print(f"Error processing {img_path.name}: {e}")
        
        self.generate_report()
    
    def generate_report(self):
        """Generate HTML report for manual review"""
        print("\n📊 Generating review report...")
        
        # Create review directories
        for category in REVIEW_CATEGORIES:
            (REVIEW_PATH / category).mkdir(parents=True, exist_ok=True)
        
        html_parts = [
            "<!DOCTYPE html><html><head>",
            "<style>",
            "body { font-family: Arial; margin: 20px; }",
            ".category { margin: 30px 0; }",
            ".image-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }",
            ".image-item { border: 1px solid #ccc; padding: 10px; }",
            ".image-item img { width: 100%; height: 200px; object-fit: cover; }",
            ".confidence { font-weight: bold; color: #e74c3c; }",
            "</style>",
            "</head><body>",
            "<h1>🔍 Dataset Review - Potential False Positives</h1>"
        ]
        
        for category, images in REVIEW_CATEGORIES.items():
            if not images:
                continue
            
            html_parts.append(f"<div class='category'>")
            html_parts.append(f"<h2>{category.replace('_', ' ').title()} ({len(images)} images)</h2>")
            html_parts.append("<div class='image-grid'>")
            
            for img_path, confidence in images[:50]:  # Show first 50
                # Copy to review folder
                dest = REVIEW_PATH / category / img_path.name
                shutil.copy2(img_path, dest)
                
                html_parts.append("<div class='image-item'>")
                html_parts.append(f"<img src='{category}/{img_path.name}'>")
                html_parts.append(f"<p>{img_path.name}</p>")
                html_parts.append(f"<p class='confidence'>Confidence: {confidence:.1%}</p>")
                html_parts.append("</div>")
            
            html_parts.append("</div></div>")
        
        html_parts.append("</body></html>")
        
        (REVIEW_PATH / "review.html").write_text("\n".join(html_parts))
        
        print(f"✅ Review report saved to: {REVIEW_PATH / 'review.html'}")
        print("\n📈 Summary:")
        for category, images in REVIEW_CATEGORIES.items():
            if images:
                print(f"  - {category}: {len(images)} images")


def main():
    """Main execution"""
    cleaner = DatasetCleaner(ONNX_MODEL)
    cleaner.scan_dataset()
    
    print("\n" + "="*70)
    print("NEXT STEPS:")
    print("="*70)
    print(f"1. Open {REVIEW_PATH / 'review.html'} in your browser")
    print("2. Review flagged images manually")
    print("3. Move false positives from 'unsafe' to 'safe' folder")
    print("4. Retrain model with cleaned dataset")
    print("5. Run inference.py again to verify improvements")


if __name__ == "__main__":
    main()
