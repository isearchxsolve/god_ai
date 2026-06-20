# ========================================
# SafeScreen Model Setup Script v4.7
# Logic: VENV Use + CLI Fix + Verification (No Library Install)
# ========================================

param(
    [string]$OutputDir = ".\models"
)

$ErrorActionPreference = "Stop"

function Show-Success { param([string]$Message) Write-Host "[OK] $Message" -ForegroundColor Green }
function Show-Info    { param([string]$Message) Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Show-Error   { param([string]$Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }

# 1. Environment Paths
$WorkDir = Join-Path $OutputDir "workspace"
$VenvDir = Join-Path $WorkDir "venv_310"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvBin = Join-Path $VenvDir "Scripts"

if (!(Test-Path $VenvPython)) {
    Show-Error "Virtual environment not found at $VenvDir. Please ensure libraries are pre-installed."
    exit 1
}

# 2. Conversion & Verification Python Script
$mainScript = @"
import os, sys, subprocess, onnx, numpy as np
import tensorflow as tf
from onnx_tf.backend import prepare

def verify_model(path, model_type):
    print(f"--- Verifying {model_type} TFLite Output ---")
    try:
        interpreter = tf.lite.Interpreter(model_path=path)
        interpreter.allocate_tensors()
        
        input_details = interpreter.get_input_details()[0]
        output_details = interpreter.get_output_details()[0]
        
        # Logic verification for DetectionEngine.kt / FastTextDetector.kt
        if model_type == "Detection":
            # DetectionEngine expects 320x320
            actual = input_details['shape'].tolist()
            if 320 in actual:
                print(f"  [PASS] Detection Input: {actual}")
            else:
                print(f"  [FAIL] Detection expects 320, got {actual}"); sys.exit(1)
                
        elif model_type == "Recognition":
            # FastTextDetector expects 32x128
            actual = input_details['shape'].tolist()
            if 32 in actual and 128 in actual:
                print(f"  [PASS] Recognition Input: {actual}")
            else:
                print(f"  [FAIL] Recognition expects 32x128, got {actual}"); sys.exit(1)

        # Runtime Check
        input_data = np.array(np.random.random_sample(input_details['shape']), dtype=np.float32)
        interpreter.set_tensor(input_details['index'], input_data)
        interpreter.invoke()
        print(f"  [PASS] {model_type} runtime inference verified.")
    except Exception as e:
        print(f"  [ERROR] Verification failed: {e}"); sys.exit(1)

def run_conversion(paddle_dir, out_file, venv_bin, model_name):
    onnx_file = out_file + ".onnx"
    sm_path = out_file + "_sm"
    p2o_cmd = os.path.join(venv_bin, "paddle2onnx.exe")
    
    # Stage 1: Paddle -> ONNX
    print(f"\nStage 1: Converting {model_name} (Paddle -> ONNX)...")
    cmd = [p2o_cmd, "--model_dir", paddle_dir, "--model_filename", "inference.pdmodel",
           "--params_filename", "inference.pdiparams", "--save_file", onnx_file, "--opset_version", "13"]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Paddle2ONNX Error:\n{result.stderr}"); sys.exit(1)
    
    # Stage 2: ONNX -> TF
    print("Stage 2: Exporting to TF SavedModel...")
    tf_rep = prepare(onnx.load(onnx_file))
    tf_rep.export_graph(sm_path)
    
    # Stage 3: TF -> TFLite
    print("Stage 3: Quantizing to TFLite (FP16)...")
    converter = tf.lite.TFLiteConverter.from_saved_model(sm_path)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    tflite_model = converter.convert()
    
    with open(out_file, 'wb') as f:
        f.write(tflite_model)
    
    verify_model(out_file, model_name)

if __name__ == '__main__':
    run_conversion(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
"@

$convertPath = Join-Path $WorkDir "process_verify_fast.py"
$mainScript | Out-File -FilePath $convertPath -Encoding utf8

# 3. Process Models
$ModelsDir = Join-Path $OutputDir "tflite"
if (!(Test-Path $ModelsDir)) { New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null }

$models = @(
    @{ Name="Detection"; Url="https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_det_infer.tar"; Dir="en_PP-OCRv3_det_infer"; Out="dbnet_lite_320.tflite" },
    @{ Name="Recognition"; Url="https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_rec_infer.tar"; Dir="en_PP-OCRv3_rec_infer"; Out="tiny_crnn_en.tflite" }
)

foreach ($m in $models) {
    Show-Info "Starting workflow for $($m.Name)..."
    $targetDir = Join-Path $WorkDir $m.Dir
    $outFile = Join-Path $ModelsDir $m.Out
    
    # Download/Extract if missing
    if (-not (Test-Path $targetDir)) {
        Show-Info "Downloading source Paddle model..."
        Invoke-WebRequest -Uri $m.Url -OutFile (Join-Path $WorkDir "tmp.tar") -UseBasicParsing
        tar -xf (Join-Path $WorkDir "tmp.tar") -C $WorkDir
        Remove-Item (Join-Path $WorkDir "tmp.tar")
    }
    
    # Run Conversion + Verification
    & $VenvPython $convertPath $targetDir $outFile "$VenvBin" "$($m.Name)"
    
    if ($LASTEXITCODE -eq 0) {
        Show-Success "Successfully verified and saved to $outFile"
    } else {
        Show-Error "Failed to process $($m.Name). Check python environment for missing dependencies."
    }
}