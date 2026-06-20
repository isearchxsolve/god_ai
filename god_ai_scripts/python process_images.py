import pathlib
from pathlib import Path
from PIL import Image
import random

CUSTOM_ROOT = Path('custom_sources')
OUTPUT_DIR = Path('final_dataset')
TARGET_SIZE = (224, 224)

def safe_open(p):
    try:
        i = Image.open(p).convert('RGB')
        return i.resize(TARGET_SIZE) if min(i.size) >= 32 else None
    except Exception:
        return None

items = []
for f in CUSTOM_ROOT.rglob('*.jpg'):
    if 'safe' not in f.parts:
        items.append((f, 'unsafe'))

for f in (CUSTOM_ROOT / 'safe').rglob('*.jpg'):
    items.append((f, 'safe'))

random.shuffle(items)
n = len(items)
t = int(n * 0.7)
v = int(n * 0.85)

splits = [
    ('train', items[:t]),
    ('val', items[t:v]),
    ('test', items[v:])
]

for name, split in splits:
    for p, l in split:
        img = safe_open(p)
        if img:
            output_path = OUTPUT_DIR / name / l
            output_path.mkdir(parents=True, exist_ok=True)
            img.save(output_path / f'{p.stem}.jpg', 'JPEG', quality=92)
            print(f'{name}/{l}: done')

print('FINISHED - YOU NOW HAVE FINAL_DATASET WITH ~120K IMAGES')