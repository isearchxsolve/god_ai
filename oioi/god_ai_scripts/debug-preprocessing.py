import numpy as np
import cv2
from PIL import Image, ImageOps

IMAGE_PATH = "shits.jpg"
IMG_SIZE = 640

def letterbox_v1_opencv(img, size=640):
    """Version from model-comparison.py (OpenCV input)"""
    h, w = img.shape[:2]
    scale = min(size / h, size / w)
    nh, nw = int(h * scale), int(w * scale)
    
    img_resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    pad_x = (size - nw) // 2
    pad_y = (size - nh) // 2
    canvas[pad_y:pad_y+nh, pad_x:pad_x+nw] = img_resized
    
    return canvas, scale, pad_x, pad_y

def letterbox_v2_pil(image, size):
    """Version from inference_tflite.py (PIL input)"""
    iw, ih = image.size
    w, h = size
    scale = min(w / iw, h / ih)
    nw = int(iw * scale)
    nh = int(ih * scale)

    image = image.resize((nw, nh), Image.BICUBIC)
    
    new_image = Image.new('RGB', size, (114, 114, 114))
    pad_x = (w - nw) // 2
    pad_y = (h - nh) // 2
    new_image.paste(image, (pad_x, pad_y))
    
    return new_image, scale, pad_x, pad_y

def main():
    print("=" * 70)
    print("🔬 Preprocessing Comparison Test")
    print("=" * 70)
    
    # Load image both ways
    pil_img = Image.open(IMAGE_PATH)
    pil_img = ImageOps.exif_transpose(pil_img)
    print(f"📷 Original PIL image: {pil_img.size} (width, height)")
    
    cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    print(f"📷 Original CV image: {cv_img.shape[:2]} (height, width)")
    
    # Method 1: OpenCV (model-comparison.py)
    print("\n" + "="*70)
    print("Method 1: OpenCV letterbox (model-comparison.py)")
    print("="*70)
    canvas1, scale1, pad_x1, pad_y1 = letterbox_v1_opencv(cv_img, IMG_SIZE)
    print(f"Scale: {scale1:.6f}")
    print(f"Padding: ({pad_x1}, {pad_y1})")
    print(f"Output shape: {canvas1.shape}")
    
    # Normalize
    norm1 = canvas1.astype(np.float32) / 255.0
    print(f"Normalized range: [{norm1.min():.3f}, {norm1.max():.3f}]")
    print(f"Mean pixel value: {norm1.mean():.6f}")
    print(f"Std pixel value: {norm1.std():.6f}")
    
    # Method 2: PIL (inference_tflite.py)
    print("\n" + "="*70)
    print("Method 2: PIL letterbox (inference_tflite.py)")
    print("="*70)
    pil_padded, scale2, pad_x2, pad_y2 = letterbox_v2_pil(pil_img, (IMG_SIZE, IMG_SIZE))
    print(f"Scale: {scale2:.6f}")
    print(f"Padding: ({pad_x2}, {pad_y2})")
    print(f"Output size: {pil_padded.size}")
    
    # Convert to numpy
    canvas2 = np.array(pil_padded)
    norm2 = canvas2.astype(np.float32) / 255.0
    print(f"Normalized range: [{norm2.min():.3f}, {norm2.max():.3f}]")
    print(f"Mean pixel value: {norm2.mean():.6f}")
    print(f"Std pixel value: {norm2.std():.6f}")
    
    # Compare
    print("\n" + "="*70)
    print("🔍 COMPARISON")
    print("="*70)
    print(f"Scale difference: {abs(scale1 - scale2):.10f}")
    print(f"Padding difference: ({abs(pad_x1 - pad_x2)}, {abs(pad_y1 - pad_y2)})")
    
    # Pixel-wise comparison
    diff = np.abs(norm1 - norm2)
    print(f"\nPixel differences:")
    print(f"  Max difference: {diff.max():.6f}")
    print(f"  Mean difference: {diff.mean():.6f}")
    print(f"  Pixels with diff > 0.01: {(diff > 0.01).sum()}")
    print(f"  Pixels with diff > 0.001: {(diff > 0.001).sum()}")
    
    if diff.max() > 0.05:
        print(f"\n⚠️  LARGE DIFFERENCES DETECTED!")
        print(f"   This explains the confidence mismatch!")
        
        # Find where the differences are
        diff_mask = diff > 0.01
        print(f"\n   Differences concentrated in:")
        if diff_mask[:, :176, :].any():
            print(f"     - Left padding region")
        if diff_mask[:, 464:, :].any():
            print(f"     - Right padding region")
        if diff_mask[:176, :, :].any():
            print(f"     - Top padding region")
        if diff_mask[464:, :, :].any():
            print(f"     - Bottom padding region")
        if diff_mask[176:464, 176:464, :].any():
            print(f"     - Image content region (!)")
    else:
        print(f"\n✅ Preprocessing is IDENTICAL (max diff: {diff.max():.6f})")
    
    # Save for visual inspection
    cv2.imwrite("debug_opencv_letterbox.jpg", canvas1)
    cv2.imwrite("debug_pil_letterbox.jpg", cv2.cvtColor(canvas2, cv2.COLOR_RGB2BGR))
    cv2.imwrite("debug_difference.jpg", (diff * 255).astype(np.uint8))
    
    print(f"\n💾 Saved debug images:")
    print(f"   - debug_opencv_letterbox.jpg")
    print(f"   - debug_pil_letterbox.jpg")
    print(f"   - debug_difference.jpg (visualizes pixel differences)")
    
    print("\n" + "="*70)
    print("🎯 DIAGNOSIS:")
    print("="*70)
    
    if diff.max() < 0.001:
        print("✅ Preprocessing is identical - issue must be elsewhere")
    elif diff.max() < 0.05:
        print("⚠️  Minor differences (likely interpolation method)")
        print("   BICUBIC (PIL) vs LINEAR (OpenCV)")
        print("   This could cause small confidence variations")
    else:
        print("❌ Major preprocessing differences found!")
        print("   This is causing the accuracy issues")
    
    print("="*70)

if __name__ == "__main__":
    main()
