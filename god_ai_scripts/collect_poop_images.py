import requests
import zipfile
from pathlib import Path
from PIL import Image
from tqdm import tqdm
import random
import urllib3
import json

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

output_dir = Path("medical_images_dataset")
output_dir.mkdir(exist_ok=True)
all_images = []

print("Downloading Medical/Stool Images from Public Sources...")
print("=" * 80)

# 1. HyperKvasir via OSF (Open Science Framework) - Direct download
print("\n1. Attempting HyperKvasir from OSF...")
try:
    # OSF direct download for labeled images subset
    osf_url = "https://osf.io/download/mh9sj/"
    print("   Note: HyperKvasir is very large (110K+ images)")
    print("   Downloading a subset of labeled images...")
    print("   ⚠ This is a large file, may take time...")
    
    # Alternative: Skip large downloads and focus on smaller datasets
    print("   → Skipping full download (too large)")
    print("   → Recommended: Use Kaggle datasets manually")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 2. GitHub - Dog Feces Dataset
print("\n2. Downloading Dog Feces Dataset from GitHub...")
try:
    dfml_url = "https://github.com/ZhouGuoXiong/MC-SCMNet/archive/refs/heads/main.zip"
    dfml_zip = output_dir / "dfml.zip"
    
    with requests.get(dfml_url, stream=True, verify=False, timeout=30) as r:
        r.raise_for_status()
        total_size = int(r.headers.get('content-length', 0))
        with open(dfml_zip, 'wb') as f:
            for chunk in tqdm(r.iter_content(chunk_size=8192), 
                            total=total_size//8192, desc="DFML Dog Feces"):
                f.write(chunk)
    
    with zipfile.ZipFile(dfml_zip) as z:
        z.extractall(output_dir / "dfml")
    dfml_zip.unlink()
    
    # Find and process images
    dfml_images = list((output_dir / "dfml").rglob("*.jpg"))
    dfml_images += list((output_dir / "dfml").rglob("*.png"))
    
    selected_dfml = random.sample(dfml_images, min(500, len(dfml_images)))
    for i, img in enumerate(selected_dfml):
        try:
            new_name = output_dir / f"dfml_sample_{i}.jpg"
            new_name.write_bytes(img.read_bytes())
            all_images.append(new_name)
        except:
            pass
    
    print(f"   ✓ DFML: {len([i for i in all_images if 'dfml' in i.name])} images")
except Exception as e:
    print(f"   ✗ DFML Error: {e}")

# 3. Human Stools Classification Dataset
print("\n3. Downloading Human Stools Classification...")
try:
    human_url = "https://github.com/andrewmvd/human-stools-classification/archive/refs/heads/main.zip"
    human_zip = output_dir / "human_stools.zip"
    
    with requests.get(human_url, stream=True, verify=False, timeout=30) as r:
        r.raise_for_status()
        total_size = int(r.headers.get('content-length', 0))
        with open(human_zip, 'wb') as f:
            for chunk in tqdm(r.iter_content(chunk_size=8192),
                            total=total_size//8192, desc="Human Stools"):
                f.write(chunk)
    
    with zipfile.ZipFile(human_zip) as z:
        z.extractall(output_dir / "human_stools")
    human_zip.unlink()
    
    # Find images
    human_images = list((output_dir / "human_stools").rglob("*.jpg"))
    human_images += list((output_dir / "human_stools").rglob("*.png"))
    
    selected_human = random.sample(human_images, min(500, len(human_images)))
    for i, img in enumerate(selected_human):
        try:
            with Image.open(img) as pil_img:
                if pil_img.size[0] > 50:
                    new_name = output_dir / f"human_sample_{i}.jpg"
                    new_name.write_bytes(img.read_bytes())
                    all_images.append(new_name)
        except:
            pass
    
    print(f"   ✓ Human Stools: {len([i for i in all_images if 'human' in i.name])} images")
except Exception as e:
    print(f"   ✗ Human Stools Error: {e}")

# 4. ShitSpotter from Hugging Face
print("\n4. Attempting ShitSpotter Dataset...")
try:
    # Note: Full dataset may require HF authentication
    print("   → ShitSpotter requires Hugging Face authentication")
    print("   → Skipping automatic download")
    print("   → Manual: https://huggingface.co/datasets/erotemic/shitspotter")
except Exception as e:
    print(f"   ✗ ShitSpotter Error: {e}")

# Summary
print("\n" + "=" * 80)
print(f"Download Complete: {len(all_images)} images collected")
print(f"Saved to: {output_dir.resolve()}")

if len(all_images) > 0:
    print("\n✓ SUCCESS - Images downloaded!")
    print("\nNext Steps:")
    print("1. For more medical images, download from Kaggle:")
    print("   • Kvasir: https://www.kaggle.com/datasets/meetnagadia/kvasir-dataset")
    print("   • HyperKvasir: https://www.kaggle.com/datasets/kelkalot/the-hyper-kvasir-dataset")
    print("   • Kvasir-SEG: https://www.kaggle.com/datasets/debeshjha1/kvasirseg")
    print("\n2. Install Kaggle CLI: pip install kaggle")
    print("3. Configure API key: https://www.kaggle.com/docs/api")
    print("4. Download: kaggle datasets download -d meetnagadia/kvasir-dataset")
else:
    print("\n⚠ No images downloaded. Try these alternatives:")
    print("1. Install Kaggle CLI and download datasets manually")
    print("2. Check your internet connection")
    print("3. Use alternative medical image sources")

print("\n" + "=" * 80)
print("KAGGLE DOWNLOAD INSTRUCTIONS:")
print("=" * 80)
print("1. Install: pip install kaggle")
print("2. Get API key from: https://www.kaggle.com/settings")
print("3. Place kaggle.json in: ~/.kaggle/ (Linux/Mac) or C:\\Users\\<user>\\.kaggle\\ (Windows)")
print("4. Run these commands:")
print("   kaggle datasets download -d meetnagadia/kvasir-dataset")
print("   kaggle datasets download -d debeshjha1/kvasirseg")
print("   kaggle datasets download -d kelkalot/the-hyper-kvasir-dataset")