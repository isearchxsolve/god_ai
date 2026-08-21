# convert_to_onnx_fixed.py (Windows Safe Version)
import torch
import timm
import onnx
import warnings
import sys

# === FIX: Force UTF-8 output to prevent Windows console crashes ===
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
# ==================================================================

warnings.filterwarnings("ignore")

MODEL_NAME = "efficientnet_b0"
PTH_PATH = "best_toxic_detector.pth"
ONNX_PATH = "best_toxic_detector.onnx"
INPUT_SIZE = 224

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# Load and clean state_dict (removes timm duplicate weights)
try:
    model = timm.create_model(MODEL_NAME, pretrained=False, num_classes=2)
    state_dict = torch.load(PTH_PATH, map_location=device)
except FileNotFoundError:
    print(f"Error: {PTH_PATH} not found. Make sure training completed successfully.")
    sys.exit(1)

cleaned_state_dict = {}
seen = set()
for k, v in state_dict.items():
    if k in seen:
        print(f"Skipping duplicate weight: {k}")
        continue
    seen.add(k)
    cleaned_state_dict[k] = v

model.load_state_dict(cleaned_state_dict, strict=True)
model.eval()
model.to(device)

# Dummy input
dummy_input = torch.randn(1, 3, INPUT_SIZE, INPUT_SIZE, device=device)

# Export
torch.onnx.export(
    model,
    dummy_input,
    ONNX_PATH,
    export_params=True,
    opset_version=18,
    do_constant_folding=True,
    keep_initializers_as_inputs=False,
    input_names=["input"],
    output_names=["output"],
    dynamic_axes={
        "input":  {0: "batch_size"},
        "output": {0: "batch_size"}
    },
    verbose=False,
)

# Changed arrow to -> to prevent crash
print(f"ONNX exported -> {ONNX_PATH}")

# === Fixed metadata cleanup (works with ONNX >=1.16) ===
try:
    onnx_model = onnx.load(ONNX_PATH)

    # Correct way to clear metadata in modern ONNX
    if onnx_model.metadata_props:
        onnx_model.metadata_props.clear()

    # Also remove doc_string if present
    if hasattr(onnx_model, "doc_string"):
        onnx_model.doc_string = ""

    # Save again (ensures clean serialization)
    onnx.save(onnx_model, ONNX_PATH)

    print(f"ONNX opset version: {onnx_model.opset_import[0].version}")
    onnx.checker.check_model(onnx_model)
    print("Perfect single-file ONNX model saved and verified!")

    # Optional quick test with ONNX Runtime
    import onnxruntime as ort
    sess = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])
    print(f"ONNX Runtime test passed! Input name: {sess.get_inputs()[0].name}")

except Exception as e:
    print(f"ONNX Processing/Test warning: {e}")