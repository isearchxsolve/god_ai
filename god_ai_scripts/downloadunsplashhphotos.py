import pandas as pd
import requests
import os
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

photos = pd.read_csv("photos.csv000", sep="\t")
photos['photo_image_url'] = photos['photo_image_url'].str.strip()

output_dir = "unsplash_full_images"
os.makedirs(output_dir, exist_ok=True)

def download_image(row):
    url = str(row['photo_image_url']).strip()
    photo_id = str(row['photo_id']).strip()
    
    # Skip if exists
    for ext in ['jpg', 'png']:
        if os.path.exists(os.path.join(output_dir, f"{photo_id}.{ext}")):
            return (photo_id, True, None)
    
    if not url.startswith('https://'):
        return (photo_id, False, "invalid_url")
    
    try:
        response = requests.get(url, allow_redirects=True, timeout=30)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            ext = 'png' if 'png' in content_type else 'jpg'
            
            filename = os.path.join(output_dir, f"{photo_id}.{ext}")
            with open(filename, "wb") as f:
                f.write(response.content)
            return (photo_id, True, None)
        else:
            return (photo_id, False, f"status_{response.status_code}")
    except Exception as e:
        return (photo_id, False, str(e))

# Download with 20 parallel threads
failed_downloads = []

with ThreadPoolExecutor(max_workers=20) as executor:
    futures = {executor.submit(download_image, row): idx 
               for idx, row in photos.iterrows()}
    
    for future in tqdm(as_completed(futures), total=len(photos)):
        photo_id, success, error = future.result()
        if not success and error != "invalid_url":
            failed_downloads.append((photo_id, error))

print(f"\nCompleted: {len(photos) - len(failed_downloads)} successful, {len(failed_downloads)} failed")

if failed_downloads:
    failed_df = pd.DataFrame(failed_downloads, columns=['photo_id', 'error'])
    failed_df.to_csv('failed_downloads.csv', index=False)