# diagnose_model_issue.py - Understand what your model actually learned
import torch
import timm
import numpy as np
from pathlib import Path
from PIL import Image
from torchvision import transforms
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder
import json

MODEL_NAME = "efficientnet_b0"
PTH_PATH = "best_toxic_detector.pth"
DATASET_PATH = Path("final_dataset")

transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

def analyze_training_data():
    """Check what's in your training data"""
    
    print("="*80)
    print("TRAINING DATA ANALYSIS")
    print("="*80)
    
    # Count images directly from folders
    train_path = DATASET_PATH / "train"
    val_path = DATASET_PATH / "val"
    
    if train_path.exists():
        train_safe = len(list((train_path / "safe").glob("*"))) if (train_path / "safe").exists() else 0
        train_unsafe = len(list((train_path / "unsafe").glob("*"))) if (train_path / "unsafe").exists() else 0
        
        val_safe = len(list((val_path / "safe").glob("*"))) if (val_path / "safe").exists() else 0
        val_unsafe = len(list((val_path / "unsafe").glob("*"))) if (val_path / "unsafe").exists() else 0
        
        print(f"\n📊 Dataset Composition:")
        print(f"   Training images:")
        print(f"      - Safe: {train_safe}")
        print(f"      - Unsafe: {train_unsafe}")
        if train_unsafe > 0:
            print(f"      - Ratio: {train_safe / train_unsafe:.2f}:1 (safe:unsafe)")
        
        print(f"\n   Validation images:")
        print(f"      - Safe: {val_safe}")
        print(f"      - Unsafe: {val_unsafe}")
        if val_unsafe > 0:
            print(f"      - Ratio: {val_safe / val_unsafe:.2f}:1 (safe:unsafe)")
        
        # Check for severe imbalance
        if train_unsafe > 0:
            train_ratio = train_safe / train_unsafe
            if train_ratio > 3 or train_ratio < 0.33:
                print(f"\n   ⚠️  WARNING: Class imbalance detected!")
                print(f"      This can cause the model to be biased.")
    else:
        print(f"\n❌ Training data not found at {train_path}")
    
    # Analyze what the model predicts on training data
    print(f"\n" + "="*80)
    print("MODEL PREDICTIONS ON TRAINING DATA")
    print("="*80)
    
    device = torch.device("cpu")
    model = timm.create_model(MODEL_NAME, pretrained=False, num_classes=2)
    model.load_state_dict(torch.load(PTH_PATH, map_location=device))
    model.eval()
    
    train_dataset = ImageFolder(DATASET_PATH / "train", transform=transform)
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=False, num_workers=0)
    
    # Get predictions for safe class
    safe_probs = []
    unsafe_probs = []
    
    print("\nAnalyzing training data predictions...")
    
    with torch.no_grad():
        for inputs, labels in train_loader:
            outputs = model(inputs)
            probs = torch.softmax(outputs, dim=1)
            
            for i, label in enumerate(labels):
                prob_unsafe = probs[i][1].item()
                
                if label == 0:  # Safe image
                    safe_probs.append(prob_unsafe)
                else:  # Unsafe image
                    unsafe_probs.append(prob_unsafe)
    
    safe_probs = np.array(safe_probs)
    unsafe_probs = np.array(unsafe_probs)
    
    print(f"\n📊 Probability Distribution:")
    print(f"\n   SAFE images (should have LOW unsafe probability):")
    print(f"      Mean unsafe prob: {safe_probs.mean():.4f}")
    print(f"      Median:           {np.median(safe_probs):.4f}")
    print(f"      Min:              {safe_probs.min():.4f}")
    print(f"      Max:              {safe_probs.max():.4f}")
    
    # Check how many safe images are being predicted as unsafe
    false_positives = (safe_probs > 0.5).sum()
    print(f"\n      ⚠️  {false_positives} / {len(safe_probs)} safe images have >50% unsafe probability!")
    print(f"         That's {false_positives/len(safe_probs)*100:.2f}% false positive rate on training data!")
    
    print(f"\n   UNSAFE images (should have HIGH unsafe probability):")
    print(f"      Mean unsafe prob: {unsafe_probs.mean():.4f}")
    print(f"      Median:           {np.median(unsafe_probs):.4f}")
    print(f"      Min:              {unsafe_probs.min():.4f}")
    print(f"      Max:              {unsafe_probs.max():.4f}")
    
    # Show distribution
    print(f"\n📊 Distribution of unsafe probabilities:")
    print(f"\n   For SAFE images:")
    for threshold in [0.1, 0.3, 0.5, 0.7, 0.9]:
        count = (safe_probs > threshold).sum()
        pct = count / len(safe_probs) * 100
        print(f"      >{threshold:.1f}: {count} images ({pct:.1f}%)")
    
    print(f"\n   For UNSAFE images:")
    for threshold in [0.1, 0.3, 0.5, 0.7, 0.9]:
        count = (unsafe_probs > threshold).sum()
        pct = count / len(unsafe_probs) * 100
        print(f"      >{threshold:.1f}: {count} images ({pct:.1f}%)")

def check_validation_errors():
    """Find which validation images are being misclassified"""
    
    print(f"\n" + "="*80)
    print("VALIDATION SET ERRORS")
    print("="*80)
    
    device = torch.device("cpu")
    model = timm.create_model(MODEL_NAME, pretrained=False, num_classes=2)
    model.load_state_dict(torch.load(PTH_PATH, map_location=device))
    model.eval()
    
    val_dataset = ImageFolder(DATASET_PATH / "val", transform=transform)
    
    # Get some misclassified examples
    false_positives = []  # Safe images marked as unsafe
    false_negatives = []  # Unsafe images marked as safe
    
    print("\nFinding misclassified images...")
    
    with torch.no_grad():
        for idx in range(len(val_dataset)):
            img, label = val_dataset[idx]
            output = model(img.unsqueeze(0))
            prob = torch.softmax(output[0], dim=0)
            prob_unsafe = prob[1].item()
            
            pred = 1 if prob_unsafe > 0.5 else 0
            
            if label == 0 and pred == 1:  # False positive
                img_path = val_dataset.imgs[idx][0]
                false_positives.append((img_path, prob_unsafe))
            elif label == 1 and pred == 0:  # False negative
                img_path = val_dataset.imgs[idx][0]
                false_negatives.append((img_path, prob_unsafe))
    
    print(f"\n⚠️  FALSE POSITIVES (Safe images marked as UNSAFE):")
    print(f"   Total: {len(false_positives)}")
    if len(false_positives) > 0:
        print(f"\n   Top 10 most confident false positives:")
        false_positives.sort(key=lambda x: x[1], reverse=True)
        for img_path, prob in false_positives[:10]:
            print(f"      {Path(img_path).name}: {prob:.2%} unsafe")
    
    print(f"\n⚠️  FALSE NEGATIVES (Unsafe images marked as SAFE):")
    print(f"   Total: {len(false_negatives)}")
    if len(false_negatives) > 0:
        print(f"\n   Top 10 most confident false negatives:")
        false_negatives.sort(key=lambda x: x[1])
        for img_path, prob in false_negatives[:10]:
            print(f"      {Path(img_path).name}: {prob:.2%} unsafe")
    
    print(f"\n💡 DIAGNOSIS:")
    
    if len(false_positives) > len(val_dataset) * 0.01:
        print(f"   ⚠️  High false positive rate ({len(false_positives)/len(val_dataset)*100:.2f}%)")
        print(f"      The model is too aggressive at flagging safe content.")
        print(f"      Possible causes:")
        print(f"         - Training data mislabeled (safe images in 'unsafe' folder)")
        print(f"         - Not enough diverse safe examples")
        print(f"         - Model overfitting to unsafe patterns")
    
    if len(false_negatives) > len(val_dataset) * 0.01:
        print(f"   ⚠️  High false negative rate ({len(false_negatives)/len(val_dataset)*100:.2f}%)")
        print(f"      The model is missing actual unsafe content.")

def main():
    print("="*80)
    print("MODEL DIAGNOSTIC TOOL")
    print("="*80)
    print("\nThis tool will help understand why your model flags normal content as unsafe.\n")
    
    # Check if dataset exists
    if not DATASET_PATH.exists():
        print(f"❌ Dataset not found at: {DATASET_PATH}")
        print("   This script needs access to your training data.")
        return
    
    # Run diagnostics
    analyze_training_data()
    check_validation_errors()
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    print("""
Based on the diagnostics above:

1. If you have many false positives on SAFE images:
   → Your "unsafe" training folder likely contains normal images
   → Review and clean your training data
   → The model learned the wrong patterns

2. If safe images have high unsafe probabilities in training:
   → Data labeling error - images in wrong folders
   → Retrain with corrected labels

3. If your business/corporate images are flagged:
   → Your training data lacks diverse safe examples
   → Add more corporate/business images to "safe" folder
   → Retrain the model

Next steps:
   1. Check: final_dataset/train/unsafe/ for any normal images
   2. Check: final_dataset/train/safe/ for any mislabeled images
   3. If issues found, fix labels and retrain
    """)

if __name__ == "__main__":
    main()