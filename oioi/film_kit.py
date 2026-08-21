# ==============================================================================
# CELL 3: FINAL_FILM_KIT.PY (NVIDIA NIM GATEKEEPER & DSP UPSCALE)
# ==============================================================================
import os
import sys
import base64
import glob
import subprocess
from openai import OpenAI

def encode_image(path):
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def validate_frame_nvlm(frame_path):
    """Hits the NVIDIA NVLM-D-72B endpoint for structural CI/CD validation."""
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.environ.get("NVIDIA_API_KEY")
    )
    
    encoded_image = encode_image(frame_path)
    print(f"👁️ Gatekeeper analyzing {os.path.basename(frame_path)}...")
    
    try:
        completion = client.chat.completions.create(
            model="nvidia/nvlm-d-72b",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text", 
                        "text": "Strictly evaluate this frame against anti-morph safeguards. Are there any structural defects, melting, or mutations in the faces or hands? Reply strictly with 'PASS' if the structure is perfect, or 'FAIL' if there are defects."
                    },
                    {
                        "type": "image_url", 
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}
                    }
                ]
            }],
            max_tokens=10,
            temperature=0.0 # Strict determinism
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ NVIDIA API Error: {e}")
        return "FAIL"

def main():
    print("=== STAGE 3: HYBRID VALIDATION & 4K DSP STACK ===")
    
    # 1. Locate the newly rendered master frames
    # Adjust this path if your render_motion outputs to a different folder structure
    clip_dir = "/kaggle/working/output_c01/clips" 
    
    # Grab a representative frame to test (e.g., a thumbnail or first frame)
    test_frames = glob.glob(f"{clip_dir}/**/*.jpg", recursive=True) + glob.glob(f"{clip_dir}/**/*.png", recursive=True)
    
    if not test_frames:
        print("⚠️ No rendered frames found for validation. Did the render loop complete?")
        sys.exit(1)

    target_frame = test_frames[0]
    
    # 2. Run the Multimodal Validation
    validation_result = validate_frame_nvlm(target_frame)
    print(f"Gatekeeper Result: {validation_result}")
    
    if "FAIL" in validation_result:
        print("❌ HYBRID GATE REJECTED: Structural mutation detected by NVLM.")
        print("⏸️ Halting pipeline to conserve T4 compute. Check generation parameters.")
        sys.exit(1)
        
    print("✅ HYBRID GATE PASSED: Asset is structurally sound.")
    print("🚀 Triggering Phase B: Offline 4K DSP Stack (Real-ESRGAN + GFPGAN + RIFE)...")
    
    # 3. Trigger your final 4K Upscale/Delivery script
    # This executes the equivalent of Gate 7 in your gated pipeline
    upscale_script = os.path.join('/kaggle/working', 'godshand', 'kit', 'src', 'upscale_4k.py')
    if os.path.exists(upscale_script):
        subprocess.run([sys.executable, upscale_script], check=True)
        print("🎬 Final master packaging complete.")
    else:
        print(f"⚠️ Could not find upscale script at {upscale_script}. Skipping DSP stage.")

if __name__ == "__main__":
    main()