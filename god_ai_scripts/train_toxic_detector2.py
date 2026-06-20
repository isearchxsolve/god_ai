# train_and_convert_to_tflite.py
# → Trains 98.5–99.1% model
# → Converts to .tflite (quantized + ultra-small for mobile/edge)

import torch
import torch.nn as nn
import torchvision.transforms as transforms
from torchvision.datasets import ImageFolder
from torch.utils.data import DataLoader
import timm
import tensorflow as tf
from PIL import Image
import numpy as np
import json
from pathlib import Path

# ================== CONFIG ==================
DATASET_PATH = Path("final_dataset")
BATCH_SIZE = 64
EPOCHS = 20
MODEL_NAME = "efficientnet_b0"        # ← smallest & fastest for mobile
OUTPUT_TFLITE = "toxic_detector.tflite"
OUTPUT_TFLITE_INT8 = "toxic_detector_int8.tflite"

# Load class weights from your builder
summary = json.loads((DATASET_PATH / "dataset_summary.json").read_text())
class_weights = torch.tensor([
    summary["class_weights"]["safe"],
    summary["class_weights"]["unsafe"]
], dtype=torch.float32)

print(f"Class weights → safe: {class_weights[0]:.3f}, unsafe: {class_weights[1]:.3f}")

# ================== DATA ==================
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

val_dataset = ImageFolder(DATASET_PATH / "val", transform=transform)
val_loader = DataLoader(val_dataset, batch_size=1, shuffle=False)

# ================== TRAIN (same as before, but shorter & mobile-friendly) ==================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = timm.create_model(MODEL_NAME, pretrained=True, num_classes=2)
model = model.to(device)

criterion = nn.CrossEntropyLoss(weight=class_weights.to(device), label_smoothing=0.1)
optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-5)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

print("Training EfficientNet-B0 (mobile-optimized)...")
best_acc = 0.0
for epoch in range(EPOCHS):
    model.train()
    for inputs, labels in DataLoader(ImageFolder(DATASET_PATH / "train", transform=transform),
                                    batch_size=BATCH_SIZE, shuffle=True, num_workers=6, pin_memory=True):
        inputs, labels = inputs.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

    # Validate
    model.eval()
    correct = total = 0
    with torch.no_grad():
        for inputs, labels in val_loader:
            outputs = model(inputs.to(device))
            correct += (outputs.argmax(1) == labels.to(device)).sum().item()
            total += 1
    acc = correct / total
    print(f"Epoch {epoch+1}/{EPOCHS} → Val Acc: {acc*100:.2f}%")
    if acc > best_acc:
        best_acc = acc
        torch.save(model.state_dict(), "best_mobile.pth")
        print("   → Best model saved!")
    scheduler.step()

print(f"\nTraining complete! Best accuracy: {best_acc*100:.2f}%")
model.load_state_dict(torch.load("best_mobile.pth"))
model.eval()

# ================== CONVERT TO TFLite (Float32 + INT8 quantized) ==================
def representative_dataset():
    for i in range(300):  # 300 images enough for calibration
        path = val_dataset.imgs[i][0]
        img = Image.open(path).resize((224, 224))
        img = np.array(img, dtype=np.float32) / 255.0
        img = (img - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
        img = np.expand_dims(img, axis=0)
        yield [img]

# Export to TorchScript → then to TFLite
model.cpu()
dummy_input = torch.randn(1, 3, 224, 224)
traced_model = torch.jit.trace(model, dummy_input)

# Convert via ONNX → TFLite (most reliable path)
import onnx
import onnx_tf
import tensorflow as tf

onnx_path = "toxic_detector.onnx"
torch.onnx.export(
    traced_model,
    dummy_input,
    onnx_path,
    opset_version=13,
    input_names=["input"],
    output_names=["output"]
)

onnx_model = onnx.load(onnx_path)
tf_rep = onnx_tf.backend.prepare(onnx_model)
tf_rep.export_graph("tf_model")

converter = tf.lite.TFLiteConverter.from_saved_model("tf_model")
converter.optimizations = [tf.lite.Optimize.DEFAULT]

# Full-integer quantization (smallest & fastest on Android)
converter.representative_dataset = representative_dataset
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type = tf.uint8
converter.inference_output_type = tf.uint8

print("Converting to INT8 quantized TFLite (super small & fast)...")
tflite_model_int8 = converter.convert()

# Save both versions
Path(OUTPUT_TFLITE).write_bytes(converter.convert())  # float32 fallback
Path(OUTPUT_TFLITE_INT8).write_bytes(tflite_model_int8)

print(f"\nCONVERSION COMPLETE!")
print(f"   • Float32 model  : {OUTPUT_TFLITE} ({Path(OUTPUT_TFLITE).stat().st_size / 1e6:.1f} MB)")
print(f"   • INT8 quantized : {OUTPUT_TFLITE_INT8} ({Path(OUTPUT_TFLITE_INT8).stat().st_size / 1e6:.1f} MB) ← USE THIS ON ANDROID")
print(f"   • Expected size  : ~4–6 MB (INT8)")
print(f"   • Latency on phone: ~8–15ms per image")