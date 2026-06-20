# inference_onnx_production.py - Production ONNX inference with optimal threshold
# (Windows Safe Version - No Emojis)
import onnxruntime as ort
import numpy as np
from PIL import Image
from torchvision import transforms
from pathlib import Path
import sys

# === FIX: Force UTF-8 output to prevent Windows console crashes ===
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
# ==================================================================

class ToxicContentDetector:
    """Production-ready toxic content detector using ONNX"""
    
    def __init__(self, model_path="best_toxic_detector.onnx", threshold=0.50):
        """
        Initialize the detector
        
        Args:
            model_path: Path to ONNX model file
            threshold: Classification threshold (default 0.50 for 99.93% accuracy)
        """
        self.session = ort.InferenceSession(
            model_path, 
            providers=['CPUExecutionProvider']
        )
        self.threshold = threshold
        
        # Standard preprocessing (MUST match training)
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        
        print(f"[OK] Loaded ONNX model: {model_path}")
        print(f"[OK] Threshold: {threshold} (optimal for validation accuracy)")
    
    def predict(self, image_path, return_probabilities=False):
        """
        Predict if an image contains toxic/unsafe content
        """
        # Load and preprocess image
        img = Image.open(image_path).convert("RGB")
        input_tensor = self.transform(img).unsqueeze(0).numpy()
        
        # Run inference
        logits = self.session.run(None, {"input": input_tensor})[0][0]
        
        # Apply softmax to get probabilities
        exp_logits = np.exp(logits - np.max(logits))  # Numerical stability
        probs = exp_logits / exp_logits.sum()
        
        prob_safe = float(probs[0])
        prob_unsafe = float(probs[1])
        
        # Classify based on threshold
        is_toxic = prob_unsafe > self.threshold
        
        if return_probabilities:
            return is_toxic, prob_safe, prob_unsafe
        else:
            return is_toxic
    
    def predict_batch(self, image_paths):
        """
        Predict multiple images (processed one at a time due to ONNX limitation)
        """
        results = []
        
        for img_path in image_paths:
            try:
                is_toxic, prob_safe, prob_unsafe = self.predict(img_path, return_probabilities=True)
                results.append((img_path, is_toxic, prob_unsafe))
            except Exception as e:
                print(f"Error processing {img_path}: {e}")
                results.append((img_path, None, None))
        
        return results
    
    def get_recommendation(self, prob_unsafe):
        """Get human-readable recommendation based on probability"""
        if prob_unsafe > 0.90:
            return "[!] VERY HIGH RISK - Almost certainly unsafe"
        elif prob_unsafe > 0.75:
            return "[!] HIGH RISK - Very likely unsafe"
        elif prob_unsafe > 0.60:
            return "[?] MODERATE RISK - Possibly unsafe, review recommended"
        elif prob_unsafe > 0.40:
            return "[-] LOW RISK - Uncertain, borderline case"
        else:
            return "[OK] VERY LOW RISK - Likely safe"


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    
    # Initialize detector with optimal threshold
    detector = ToxicContentDetector(
        model_path="best_toxic_detector.onnx",
        threshold=0.80  # 99.93% accuracy on validation set
    )
    
    print("\n" + "="*70)
    print("EXAMPLE 1: Simple prediction")
    print("="*70)
    
    # Check if a sample image exists, otherwise create a dummy one or skip
    sample_img = Path("face.jpg")
    if not sample_img.exists():
        # Try to find any jpg in current dir
        any_jpg = list(Path(".").glob("*.jpg"))
        if any_jpg:
            sample_img = any_jpg[0]
        else:
            print("No .jpg images found to test. Skipping Example 1 & 2.")
            sample_img = None

    if sample_img:
        is_toxic = detector.predict(sample_img)
        print(f"{sample_img.name} -> {'UNSAFE [!]' if is_toxic else 'SAFE [OK]'}")
        
        print("\n" + "="*70)
        print("EXAMPLE 2: Detailed prediction with probabilities")
        print("="*70)
        
        is_toxic, prob_safe, prob_unsafe = detector.predict(sample_img, return_probabilities=True)
        
        print(f"Image: {sample_img.name}")
        print(f"  Probability SAFE:   {prob_safe:.4f} ({prob_safe*100:.2f}%)")
        print(f"  Probability UNSAFE: {prob_unsafe:.4f} ({prob_unsafe*100:.2f}%)")
        print(f"  Threshold: {detector.threshold}")
        print(f"  Result: {'UNSAFE [!]' if is_toxic else 'SAFE [OK]'}")
        print(f"  Recommendation: {detector.get_recommendation(prob_unsafe)}")
    
    
    print("\n" + "="*70)
    print("EXAMPLE 3: Batch processing")
    print("="*70)
    
    # Find all images in current directory
    image_paths = list(Path(".").glob("*.jpg")) + list(Path(".").glob("*.jpeg")) + list(Path(".").glob("*.png"))
    
    if len(image_paths) > 0:
        results = detector.predict_batch([str(p) for p in image_paths[:100]])  # Process first 5
        
        print(f"\nProcessed {len(results)} images:")
        for img_path, is_toxic, prob_unsafe in results:
            if is_toxic is not None:
                status = "UNSAFE [!]" if is_toxic else "SAFE [OK]"
                print(f"  {Path(img_path).name}: {status} (unsafe={prob_unsafe:.2%})")
    
    
    print("\n" + "="*70)
    print("THRESHOLD RECOMMENDATIONS")
    print("="*70)
    print("""
Based on validation set analysis (8,745 images):

THRESHOLD    ACCURACY    USE CASE
---------    --------    --------
0.30-0.50    99.93%      [OK] RECOMMENDED - Maximum accuracy
0.60-0.70    99.69%      Balanced - Good for most cases
0.75-0.80    99.37%      More lenient - Fewer false alarms
0.80+        <95%        [X] NOT RECOMMENDED - Misses too much unsafe content

Your original threshold of 0.80 misses 5.19% of unsafe content (454 images).
Use 0.50 for optimal performance!
    """)