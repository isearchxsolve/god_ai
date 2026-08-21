# compare_pth_onnx_accuracy.py - Diagnose ONNX vs PyTorch accuracy differences
import torch
import torch.nn as nn
import timm
import onnxruntime as ort
import numpy as np
from pathlib import Path
from torch.utils.data import DataLoader
from torchvision import transforms
from torchvision.datasets import ImageFolder
from tqdm import tqdm

MODEL_NAME = "efficientnet_b0"
PTH_PATH = "best_toxic_detector.pth"
ONNX_PATH = "toxic_detector.onnx"
DATASET_PATH = Path("final_dataset")
BATCH_SIZE = 32

val_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

def test_pytorch_model():
    """Test original PyTorch model"""
    print("\n" + "="*60)
    print("Testing PyTorch Model (.pth)")
    print("="*60)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Load PyTorch model
    model = timm.create_model(MODEL_NAME, pretrained=False, num_classes=2)
    model.load_state_dict(torch.load(PTH_PATH, map_location=device))
    model.to(device)
    model.eval()
    
    # Load validation dataset
    val_dataset = ImageFolder(DATASET_PATH / "val", transform=val_transform)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    
    correct = total = 0
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for inputs, labels in tqdm(val_loader, desc="PyTorch inference"):
            inputs = inputs.to(device)
            outputs = model(inputs)
            preds = outputs.argmax(1).cpu().numpy()
            
            all_preds.extend(preds)
            all_labels.extend(labels.numpy())
            
            correct += (preds == labels.numpy()).sum()
            total += labels.size(0)
    
    accuracy = correct / total
    print(f"\nPyTorch Accuracy: {accuracy*100:.2f}%")
    print(f"Correct: {correct}/{total}")
    
    return all_preds, all_labels, accuracy

def test_onnx_model():
    """Test ONNX model"""
    print("\n" + "="*60)
    print("Testing ONNX Model (.onnx)")
    print("="*60)
    
    # Load ONNX model (CPU only for compatibility)
    session = ort.InferenceSession(
        ONNX_PATH,
        providers=['CPUExecutionProvider']
    )
    
    # Load validation dataset
    val_dataset = ImageFolder(DATASET_PATH / "val", transform=val_transform)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    
    correct = total = 0
    all_preds = []
    all_labels = []
    
    for inputs, labels in tqdm(val_loader, desc="ONNX inference"):
        # Convert to numpy for ONNX
        inputs_np = inputs.numpy()
        
        # Run ONNX inference
        outputs = session.run(None, {"input": inputs_np})[0]
        preds = np.argmax(outputs, axis=1)
        
        all_preds.extend(preds)
        all_labels.extend(labels.numpy())
        
        correct += (preds == labels.numpy()).sum()
        total += labels.size(0)
    
    accuracy = correct / total
    print(f"\nONNX Accuracy: {accuracy*100:.2f}%")
    print(f"Correct: {correct}/{total}")
    
    return all_preds, all_labels, accuracy

def compare_single_sample():
    """Compare PyTorch vs ONNX on single sample to check numerical differences"""
    print("\n" + "="*60)
    print("Comparing Single Sample Output")
    print("="*60)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Load models
    model_pth = timm.create_model(MODEL_NAME, pretrained=False, num_classes=2)
    model_pth.load_state_dict(torch.load(PTH_PATH, map_location=device))
    model_pth.to(device)
    model_pth.eval()
    
    session_onnx = ort.InferenceSession(ONNX_PATH)
    
    # Get one sample
    val_dataset = ImageFolder(DATASET_PATH / "val", transform=val_transform)
    sample_input, sample_label = val_dataset[0]
    sample_input_batch = sample_input.unsqueeze(0)
    
    # PyTorch inference
    with torch.no_grad():
        output_pth = model_pth(sample_input_batch.to(device)).cpu().numpy()
    
    # ONNX inference
    output_onnx = session_onnx.run(None, {"input": sample_input_batch.numpy()})[0]
    
    # Compare
    print(f"\nPyTorch output: {output_pth[0]}")
    print(f"ONNX output:    {output_onnx[0]}")
    print(f"\nDifference (max): {np.abs(output_pth - output_onnx).max():.6f}")
    print(f"Difference (mean): {np.abs(output_pth - output_onnx).mean():.6f}")
    
    pth_pred = np.argmax(output_pth)
    onnx_pred = np.argmax(output_onnx)
    
    print(f"\nPyTorch prediction: {pth_pred}")
    print(f"ONNX prediction:    {onnx_pred}")
    print(f"True label:         {sample_label}")
    print(f"Match: {'✓' if pth_pred == onnx_pred else '✗ MISMATCH!'}")
    
    return np.abs(output_pth - output_onnx).max()

def analyze_differences(pth_preds, onnx_preds, labels):
    """Analyze where predictions differ"""
    print("\n" + "="*60)
    print("Analyzing Prediction Differences")
    print("="*60)
    
    pth_preds = np.array(pth_preds)
    onnx_preds = np.array(onnx_preds)
    labels = np.array(labels)
    
    # Find mismatches
    mismatch = pth_preds != onnx_preds
    num_mismatches = mismatch.sum()
    
    print(f"\nTotal samples: {len(labels)}")
    print(f"Prediction mismatches: {num_mismatches} ({num_mismatches/len(labels)*100:.2f}%)")
    
    if num_mismatches > 0:
        # Analyze where they differ
        pth_correct_onnx_wrong = (pth_preds == labels) & (onnx_preds != labels)
        onnx_correct_pth_wrong = (onnx_preds == labels) & (pth_preds != labels)
        both_wrong = (pth_preds != labels) & (onnx_preds != labels) & mismatch
        
        print(f"\nBreakdown of mismatches:")
        print(f"  PyTorch correct, ONNX wrong: {pth_correct_onnx_wrong.sum()}")
        print(f"  ONNX correct, PyTorch wrong: {onnx_correct_pth_wrong.sum()}")
        print(f"  Both wrong (different): {both_wrong.sum()}")

def main():
    print("="*60)
    print("PyTorch vs ONNX Accuracy Comparison Tool")
    print("="*60)
    
    # Check files exist
    if not Path(PTH_PATH).exists():
        print(f"ERROR: {PTH_PATH} not found!")
        return
    
    if not Path(ONNX_PATH).exists():
        print(f"ERROR: {ONNX_PATH} not found!")
        return
    
    # 1. Compare single sample for numerical accuracy
    max_diff = compare_single_sample()
    
    if max_diff > 0.01:
        print("\n⚠️  WARNING: Large numerical difference detected!")
        print("This could indicate an export issue.")
    
    # 2. Test PyTorch model
    pth_preds, labels, pth_acc = test_pytorch_model()
    
    # 3. Test ONNX model
    onnx_preds, _, onnx_acc = test_onnx_model()
    
    # 4. Analyze differences
    analyze_differences(pth_preds, onnx_preds, labels)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"PyTorch Accuracy: {pth_acc*100:.2f}%")
    print(f"ONNX Accuracy:    {onnx_acc*100:.2f}%")
    print(f"Difference:       {abs(pth_acc - onnx_acc)*100:.2f}%")
    
    if abs(pth_acc - onnx_acc) < 0.01:
        print("\n✓ Models match! Difference is negligible.")
    else:
        print("\n⚠️  Significant accuracy difference detected!")
        print("\nPossible causes:")
        print("1. ONNX export issue - try re-exporting with opset_version=17")
        print("2. Numerical precision differences")
        print("3. Operator implementation differences")
        print("\nRun the improved export script to fix this.")

if __name__ == '__main__':
    main()