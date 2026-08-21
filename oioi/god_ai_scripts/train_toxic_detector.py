# train_toxic_detector.py  <-- WINDOWS SAFE VERSION
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import transforms
from torchvision.datasets import ImageFolder
from torch.cuda.amp import autocast, GradScaler
import timm
import json
from pathlib import Path
import sys

# === FIX: Force UTF-8 output to prevent Windows console crashes ===
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
# ==================================================================

DATASET_PATH = Path("final_dataset")
BATCH_SIZE = 64
EPOCHS = 20
MODEL_NAME = "efficientnet_b0"   # mobile-fast, 99%+ accuracy on your data

# Load class weights
try:
    summary_path = DATASET_PATH / "dataset_summary.json"
    if not summary_path.exists():
        print(f"Warning: {summary_path} not found. Using default weights 1.0")
        w_safe, w_unsafe = 1.0, 1.0
    else:
        summary = json.loads(summary_path.read_text(encoding='utf-8'))
        w_safe = summary["class_weights"]["safe"]
        w_unsafe = summary["class_weights"]["unsafe"]
except Exception as e:
    print(f"Error loading weights: {e}")
    w_safe, w_unsafe = 1.0, 1.0

class_weights = torch.tensor([w_safe, w_unsafe], dtype=torch.float32)

# Changed arrow character to "->" to prevent encoding crash
print(f"Class weights -> safe: {w_safe:.3f}, unsafe: {w_unsafe:.3f}")

# Transforms
train_transform = transforms.Compose([
    transforms.RandomResizedCrop(224),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(15),
    transforms.ColorJitter(0.3, 0.3, 0.3),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

val_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

import time # Add this at the top if missing

def main():
    # ... (Your existing device setup) ...
    if not torch.cuda.is_available():
        device = torch.device("cpu")
    else:
        device = torch.device("cuda")
        print(f"Using device: {torch.cuda.get_device_name(0)}")

    # ... (Your existing Dataset loading) ...
    train_dataset = ImageFolder(DATASET_PATH / "train", transform=train_transform)
    val_dataset   = ImageFolder(DATASET_PATH / "val",   transform=val_transform)

    # [SPEED UP TIP]: Since you have the 'if __name__' block, you can try changing 
    # num_workers to 2 or 4. If it crashes, go back to 0.
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True,  num_workers=2, pin_memory=True)
    val_loader   = DataLoader(val_dataset,   batch_size=BATCH_SIZE, shuffle=False, num_workers=2, pin_memory=True)

    model = timm.create_model(MODEL_NAME, pretrained=True, num_classes=2).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device), label_smoothing=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-5)
    
    use_amp = (device.type == 'cuda')
    scaler = torch.amp.GradScaler('cuda', enabled=use_amp)

    best_acc = 0.0
    print(f"Starting training on {len(train_dataset)} images...")
    
    for epoch in range(EPOCHS):
        model.train()
        running_loss = 0.0
        start_time = time.time()
        
        # [NEW] Enumerate gives us the batch index (i)
        for i, (inputs, labels) in enumerate(train_loader):
            inputs, labels = inputs.to(device), labels.to(device)
            optimizer.zero_grad()
            
            with torch.amp.autocast('cuda', enabled=use_amp):
                outputs = model(inputs)
                loss = criterion(outputs, labels)
            
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            
            running_loss += loss.item()

            # [NEW] Print status every 10 batches
            if (i + 1) % 10 == 0:
                print(f"Epoch [{epoch+1}/{EPOCHS}] Batch [{i+1}/{len(train_loader)}] Loss: {loss.item():.4f}")

        # Validation
        print(f"Validating Epoch {epoch+1}...")
        model.eval()
        correct = total = 0
        with torch.no_grad():
            for inputs, labels in val_loader:
                outputs = model(inputs.to(device))
                pred = outputs.argmax(1)
                correct += (pred == labels.to(device)).sum().item()
                total += labels.size(0)
        acc = correct / max(total, 1)
        
        epoch_time = time.time() - start_time
        print(f"Epoch {epoch+1} Finished in {epoch_time:.0f}s -> Val Accuracy: {acc*100:.2f}%")

        if acc > best_acc:
            best_acc = acc
            torch.save(model.state_dict(), "best_toxic_detector.pth")
            print("   [+] New best model saved!")

    print(f"\nTRAINING FINISHED! Best accuracy: {best_acc*100:.2f}%")

if __name__ == '__main__':
    main()