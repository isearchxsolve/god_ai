# quick_collect_images.py - Fast automated safe image collection
import subprocess
import requests
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import random
import time

OUTPUT_DIR = Path("safe_images_collection")

def setup():
    """Create directory structure"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    for subdir in ["kaggle", "unsplash", "synthetic", "filtered"]:
        (OUTPUT_DIR / subdir).mkdir(exist_ok=True)
    print(f"✓ Created directories in: {OUTPUT_DIR}")

def download_from_kaggle():
    
    # Unzip files
    print("\n📂 Extracting archives...")
    import zipfile
    for zip_file in (OUTPUT_DIR / "kaggle").glob("*.zip"):
        print(f"   Extracting {zip_file.name}...")
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(OUTPUT_DIR / "kaggle" / zip_file.stem)
    
    return True

def download_from_unsplash(access_key):
    """Download images from Unsplash (requires free API key)"""
    print("\n" + "="*80)
    print("📸 DOWNLOADING FROM UNSPLASH")
    print("="*80)
    
    if not access_key or access_key == "YOUR_ACCESS_KEY":
        print("⚠️  Skipping - No Unsplash API key provided")
        print("   Get free key at: https://unsplash.com/developers")
        return
    
    categories = [
        "business", "office", "corporate", "document", 
        "product", "infographic", "workspace", "technology"
    ]
    
    output_dir = OUTPUT_DIR / "unsplash"
    downloaded = 0
    
    for category in categories:
        print(f"\n📥 Downloading '{category}' images...")
        category_dir = output_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            for page in range(1, 6):  # 5 pages = ~150 images per category
                url = "https://api.unsplash.com/search/photos"
                params = {
                    "query": category,
                    "per_page": 30,
                    "page": page,
                    "client_id": access_key
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code != 200:
                    print(f"   API error: {response.status_code}")
                    break
                
                data = response.json()
                
                for photo in data.get("results", []):
                    try:
                        img_url = photo["urls"]["regular"]
                        img_response = requests.get(img_url, timeout=10)
                        
                        if img_response.status_code == 200:
                            filepath = category_dir / f"{photo['id']}.jpg"
                            filepath.write_bytes(img_response.content)
                            downloaded += 1
                    except:
                        continue
                
                time.sleep(1)  # Rate limiting
                
            print(f"   ✓ Downloaded {len(list(category_dir.glob('*')))} images")
            
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
    
    print(f"\n✓ Total Unsplash images: {downloaded}")

def generate_synthetic_images(count=3000):
    """Generate synthetic business images"""
    print("\n" + "="*80)
    print("🎨 GENERATING SYNTHETIC IMAGES")
    print("="*80)
    
    output_dir = OUTPUT_DIR / "synthetic"
    
    def generate_business_doc(idx):
        img = Image.new('RGB', (800, 1000), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        # Header
        header_color = random.choice([(0, 102, 204), (46, 125, 50), (211, 47, 47)])
        draw.rectangle([50, 50, 750, 150], fill=header_color)
        
        # Text lines
        for i in range(12):
            y = 200 + i * 50
            width = random.randint(400, 700)
            draw.rectangle([50, y, 50 + width, y + 15], fill=(220, 220, 220))
        
        # Logo area
        draw.ellipse([650, 70, 730, 130], fill=(255, 200, 0))
        
        img.save(output_dir / f"doc_{idx}.jpg", quality=85)
    
    def generate_infographic(idx):
        colors = [(52, 152, 219), (46, 204, 113), (241, 196, 15), (231, 76, 60), (155, 89, 182)]
        img = Image.new('RGB', (900, 900), color=(250, 250, 250))
        draw = ImageDraw.Draw(img)
        
        # Grid of colored blocks
        for i in range(3):
            for j in range(3):
                x = j * 300
                y = i * 300
                color = random.choice(colors)
                draw.rectangle([x+10, y+10, x+290, y+290], fill=color)
                # Add white text area
                draw.rectangle([x+30, y+200, x+270, y+270], fill=(255, 255, 255, 200))
        
        img.save(output_dir / f"info_{idx}.jpg", quality=85)
    
    def generate_product(idx):
        bg = random.choice([(255, 255, 255), (248, 248, 248), (240, 240, 250)])
        img = Image.new('RGB', (600, 600), color=bg)
        draw = ImageDraw.Draw(img)
        
        # Product shape
        product_color = (random.randint(50, 150), random.randint(50, 150), random.randint(100, 200))
        draw.rectangle([150, 150, 450, 450], fill=product_color, outline=(0, 0, 0), width=2)
        
        # Shadow
        draw.rectangle([160, 460, 450, 470], fill=(200, 200, 200))
        
        img.save(output_dir / f"prod_{idx}.jpg", quality=85)
    
    print(f"Generating {count} synthetic images...")
    
    for i in range(count // 3):
        generate_business_doc(i)
        generate_infographic(i)
        generate_product(i)
        
        if (i + 1) % 100 == 0:
            print(f"   Generated {(i + 1) * 3}/{count}")
    
    total = len(list(output_dir.glob("*.jpg")))
    print(f"\n✓ Generated {total} synthetic images")

def filter_and_organize():
    """Filter out bad images and organize"""
    print("\n" + "="*80)
    print("🔍 FILTERING AND ORGANIZING")
    print("="*80)
    
    output_dir = OUTPUT_DIR / "filtered"
    output_dir.mkdir(exist_ok=True)
    
    good = 0
    bad = 0
    
    # Process all collected images
    for img_path in OUTPUT_DIR.rglob("*"):
        if img_path.parent.name == "filtered":
            continue
            
        if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
            try:
                img = Image.open(img_path)
                
                # Filter criteria
                if img.width < 224 or img.height < 224:
                    bad += 1
                    continue
                
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if too large
                if img.width > 1024 or img.height > 1024:
                    img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                
                # Save
                output_path = output_dir / f"safe_{good:06d}.jpg"
                img.save(output_path, quality=90)
                good += 1
                
                if good % 500 == 0:
                    print(f"   Processed: {good} ✓  |  {bad} ✗")
                
            except Exception as e:
                bad += 1
    
    print(f"\n✅ Filtering complete!")
    print(f"   ✓ Good images: {good:,}")
    print(f"   ✗ Rejected: {bad:,}")
    
    return good

def main():
    print("="*80)
    print("AUTOMATED SAFE IMAGE COLLECTION TOOL")
    print("="*80)
    print("\nThis script will collect 15,000+ safe images from multiple sources:\n")
    print("1. ✓ Synthetic generation (3,000 images) - Always works")
    print("2. 📦 Kaggle datasets (10,000+ images) - Requires kaggle CLI")
    print("3. 📸 Unsplash API (1,000+ images) - Requires free API key\n")
    
    setup()
    
    
    total = filter_and_organize()
    
    # Summary
    print("\n" + "="*80)
    print("📊 COLLECTION SUMMARY")
    print("="*80)
    print(f"\n✅ Total safe images collected: {total:,}")
    print(f"📁 Location: {OUTPUT_DIR / 'filtered'}")
    
    if total >= 15000:
        print(f"\n🎉 SUCCESS! You have {total:,} images (target: 15,000)")
    elif total >= 10000:
        print(f"\n✓ Good! You have {total:,} images")
        print("   Consider adding more for better diversity")
    else:
        print(f"\n⚠️  Only {total:,} images collected")
        print("   Recommend enabling Kaggle downloads for more images")
    
    print("\n📝 Next steps:")
    print(f"1. Copy images: cp {OUTPUT_DIR}/filtered/* final_dataset/train/safe/")
    print("2. Run: python fix_class_imbalance.py")
    print("3. Retrain: python train_toxic_detector.py")

if __name__ == "__main__":
    main()
