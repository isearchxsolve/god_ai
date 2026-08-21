"""
AUTO DATASET GENERATOR (v9) – BALANCED TRAINING MODE
1. SCRAPES 'Unsafe' (Bio-hazard) AND 'Safe' (Hard Negatives) images.
2. AUTO-LABELS Unsafe content with bounding boxes.
3. GENERATES EMPTY LABELS for Safe content (teaches model to ignore them).
4. OUTPUTS a ready-to-train YOLO dataset.
"""

import time
import random
import threading
import shutil
import cv2
import numpy as np
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# ===================== CONFIG =====================
BASE_DIR = Path("google_search_dataset_v2")
RAW_DIR = BASE_DIR / "raw"
TRAIN_IMG_DIR = BASE_DIR / "images" / "train"
TRAIN_LBL_DIR = BASE_DIR / "labels" / "train"

# Balanced Target: 50% Toxic, 50% Safe
TARGET_SCREENSHOTS_PER_TERM = 8
PARALLEL_TABS = 4
SCALE = 3.0 

MOBILE_EMULATION = {
    "deviceMetrics": {"width": 393, "height": 851, "pixelRatio": 3.0},
    "userAgent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/124.0.0.0 Mobile Safari/537.36"
}

# Global variable to store driver path
DRIVER_PATH = None

# ===================== TERM LISTS =====================

SAFE_TERMS = [
    # Animals (50)
    "cute cat", "kitten playing", "puppy", "baby animals", "red panda", "otter", "bunny rabbit",
    "hamster", "guinea pig", "ferret", "hedgehog", "squirrel", "chipmunk", "fox", "deer",
    "elephant", "giraffe", "zebra", "lion cub", "tiger cub", "panda bear", "koala", "kangaroo",
    "dolphin", "whale", "sea turtle", "penguin", "seal pup", "owl", "parrot", "hummingbird",
    "butterfly", "ladybug", "dragonfly", "golden retriever", "corgi", "husky puppy", "beagle",
    "dachshund", "pomeranian", "shiba inu", "maine coon cat", "persian cat", "ragdoll cat",
    "siamese cat", "bengal cat", "scottish fold", "alpaca", "llama", "sheep",
    
    # Nature & Landscapes (50)
    "sunset beach", "mountain landscape", "forest path", "waterfall", "rainbow", "northern lights",
    "cherry blossom", "autumn leaves", "snow mountain", "desert dunes", "ocean waves", "coral reef",
    "tropical island", "lake reflection", "canyon", "volcano", "meadow flowers", "bamboo forest",
    "pine trees", "redwood forest", "glacier", "hot springs", "rocky coast", "sand beach",
    "tropical rainforest", "savanna", "tundra landscape", "river valley", "countryside", "vineyard",
    "lavender field", "sunflower field", "tulip garden", "botanical garden", "japanese garden",
    "zen garden", "park", "hiking trail", "camping site", "starry night", "full moon", "sunrise",
    "clouds", "blue sky", "storm clouds", "lightning", "snow", "rain", "fog", "mist",
    
    # Food (50)
    "pizza", "chocolate cake", "sushi", "pasta", "burger", "tacos", "ramen", "ice cream",
    "pancakes", "waffles", "croissant", "donuts", "cupcakes", "macarons", "bread", "bagel",
    "sandwich", "salad", "fruit bowl", "smoothie bowl", "acai bowl", "poke bowl", "bibimbap",
    "pad thai", "curry", "dumplings", "spring rolls", "banh mi", "pho", "bao buns", "fried rice",
    "steak", "bbq ribs", "grilled chicken", "salmon", "lobster", "shrimp", "oysters", "caviar",
    "cheese platter", "charcuterie", "bruschetta", "caprese", "tiramisu", "creme brulee",
    "cheesecake", "apple pie", "brownies", "cookies", "coffee art", "latte art",
    
    # People & Lifestyle (50)
    "happy family", "smiling people", "wedding", "birthday party", "graduation", "baby photo",
    "kids playing", "friends laughing", "couple", "yoga", "meditation", "exercise", "running",
    "cycling", "swimming", "hiking", "dancing", "reading", "studying", "working", "office",
    "teamwork", "handshake", "celebration", "success", "achievement", "volunteer", "helping",
    "elderly care", "healthcare worker", "teacher", "students", "classroom", "library", "museum",
    "concert", "festival", "parade", "sports", "soccer", "basketball", "tennis", "golf",
    "skateboarding", "surfing", "snowboarding", "skiing", "camping", "fishing", "gardening",
    "face","baby face","smiling face",
    
    # Architecture & Places (50)
    "modern house", "luxury home", "cozy cabin", "tiny house", "treehouse", "castle", "palace",
    "cathedral", "temple", "mosque", "pagoda", "skyscraper", "city skyline", "downtown",
    "street photography", "alley", "bridge", "tower", "monument", "statue", "fountain",
    "plaza", "park bench", "playground", "cafe", "coffee shop", "restaurant", "bookstore",
    "bakery", "market", "shopping mall", "boutique", "hotel lobby", "resort", "spa", "gym",
    "stadium", "theater", "cinema", "airport", "train station", "subway", "lighthouse",
    "windmill", "barn", "farmhouse", "greenhouse", "cottage", "villa", "apartment", "loft",
    
    # Technology & Objects (50)
    "luxury car", "ferrari", "lamborghini", "porsche", "tesla", "vintage car", "motorcycle",
    "bicycle", "skateboard", "drone", "robot", "smartphone", "laptop", "camera", "headphones",
    "smartwatch", "tablet", "gaming setup", "workspace", "desk setup", "minimalist design",
    "interior design", "home decor", "furniture", "sofa", "bed", "kitchen", "bathroom",
    "living room", "bedroom", "plants", "succulent", "bonsai", "flower arrangement", "vase",
    "candles", "lamp", "chandelier", "mirror", "art", "painting", "sculpture", "pottery",
    "jewelry", "watch", "ring", "necklace", "bracelet", "fashion", "outfit", "shoes", "sneakers",
]

# ===================== 300 UNSAFE TERMS =====================
UNSAFE_TERMS = [
  "porn", "pornography", "xxx", "hardcore porn", "softcore porn", "nsfw", "hentai", "ecchi",
  "yaoi", "yuri", "futanari", "rule34", "r34", "pornhub", "xvideos", "xnxx", "redtube",
  "youporn", "brazzers", "bangbros", "reality kings", "naughty america", "onlyfans leak",
  "leaked nudes", "sextape", "celebrity nude", "revenge porn", "deepfake porn", "celeb jihad",
  "the fappening", "anal sex", "anal penetration", "anal creampie", "anal gape", "double anal",
  "ass to mouth", "atm", "rimming", "rimjob", "salad tossing", "blowjob", "giving head",
  "sucking dick", "deepthroat", "throatpie", "gagging on cock", "face fucking", "skull fucking",
  "handjob", "jerking off", "jacking off", "wanking", "fapping", "cumshot", "facial cumshot",
  "money shot", "creampie", "internal cumshot", "breeding fetish", "bareback sex", "raw sex",
  "gangbang", "orgy", "group sex", "threesome", "foursome", "bukkake", "gokkun", "nakadashi",
  "ahegao", "milf", "gilf", "teen porn", "jailbait", "barely legal", "lesbian porn", "dyke",
  "tribbing", "scissoring", "strapon", "pegging", "gay porn", "twink", "shemale", "tranny",
  "ladyboy", "dickgirl", "futa", "bdsm", "bondage", "shibari", "kinbaku", "sadism", "masochism",
  "sadomasochism", "dominatrix", "domme", "findom", "paypig", "submissive", "sex slave", "gimp",
  "ball gag", "nipple clamps", "flogging", "whipping", "spanking", "paddling", "caning",
  "electro stimulation", "wax play", "edgeplay", "breath play", "erotic asphyxiation",
  "autoerotic asphyxiation", "choking fetish", "rape fantasy", "consensual non consent",
  "ravishment", "somnophilia", "sleep sex", "voyeur", "peeping tom", "upskirt", "downblouse",
  "hidden cam", "spy cam", "toilet cam", "changing room cam", "striptease", "lapdance",
  "webcam girl", "cam model", "hooker", "brothel", "escort service", "happy ending massage",
  "cock", "pussy", "cunt", "twat", "boner", "hard on", "erect penis", "wet vagina", "camel toe",
  "moose knuckle", "blue balls", "gore", "gruesome", "graphic violence", "extreme violence",
  "beheading", "decapitation", "severed head", "throat slit", "necklacing", "curb stomp",
  "execution video", "isis video", "cartel video", "funkytown gore", "mutilation", "dismemberment",
  "evisceration", "disembowelment", "gutting", "flaying", "skinned alive", "burned alive",
  "immolation", "self immolation", "torture porn", "snuff film", "snuff video", "faces of death",
  "bestgore", "liveleak", "kaotic", "theync", "rotten.com", "suicide", "commit suicide",
  "kill myself", "hanging body", "hanged man", "noose", "shotgun suicide", "slit wrists",
  "cutting self", "self harm", "seppuku", "hara kiri", "mass shooting", "school shooter",
  "active shooter", "columbine", "sandy hook", "terrorist attack", "bombing", "ied explosion",
  "suicide vest", "9/11 footage", "jumpers", "war crimes", "genocide", "ethnic cleansing",
  "mass grave", "pile of bodies", "rotting corpse", "decomposing body", "maggot infested",
  "autopsy photo", "crime scene photo", "murder scene", "bloody", "bleeding", "blood splatter",
  "pool of blood", "covered in blood", "hemorrhage", "brain matter", "skull fragments",
  "severed limb", "stump fetish", "acrotomophilia", "apotemnophilia", "necrophilia", "necro",
  "corpse fucking", "mauling", "shark attack", "bear attack", "dog attack", "pitbull attack",
  "industrial accident", "lathe accident", "degloving", "hydraulic press accident", "scat",
  "scatology", "shit play", "coprophilia", "eating shit", "pile of shit", "feces", "human feces",
  "excrement", "human waste", "defecation", "bowel movement", "loose stool", "bloody stool",
  "poop", "turd", "diarrhea", "explosive diarrhea", "2 girls 1 cup", "tubgirl", "brown shower",
  "glass bottom boat", "cleveland steamer", "dirty sanchez", "alabama hot pocket", "urine",
  "pissing", "golden shower", "watersports", "urolagnia", "drinking piss", "piss fetish",
  "omorashi", "desperate peeing", "wetting pants", "diaper fetish", "abdl", "adult baby",
  "crinkling", "messy diaper", "loaded diaper", "soiled diaper", "vomit", "puke", "barf",
  "projectile vomit", "vomiting", "retching", "heaving", "vomit fetish", "puking fetish",
  "emetophilia", "roman shower", "2 girls 1 finger", "blue waffle", "lemon party", "meatspin",
  "goatse", "prolapse", "rosebudding", "pink sock", "gaping hole", "fisting", "vaginal fisting",
  "anal fisting", "handballing", "sounding", "urethral sounding", "docking", "cock docking",
  "ball busting", "cbt", "cock and ball torture", "genital torture", "needle play", "vore",
  "vorarephilia", "unbirthing", "giantess", "shrinking fetish", "pony play", "pup play",
  "human pup", "furry porn", "yiff", "clop", "zoophilia", "bestiality", "animal sex",
  "horse sex", "dog sex", "knotting", "pus", "infected wound", "oozing wound", "festering",
  "gangrene", "necrosis", "maggots", "parasites", "tapeworm", "lice infestation", "bed bugs",
  "roach infestation", "rat infestation", "sewage", "septic tank", "dirty toilet",
  "overflowing toilet", "clogged toilet", "roadkill", "animal carcass", "dead animal"
]

# ===================== SCRAPER =====================

def setup_driver(driver_path):
    """Create a driver instance using pre-installed driver path"""
    options = Options()
    options.add_experimental_option("mobileEmulation", MOBILE_EMULATION)
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    driver = webdriver.Chrome(service=Service(driver_path), options=options)
    return driver

def sanitize(name):
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name)[:40]

def scrape_worker(thread_id, terms, is_unsafe, driver_path):
    """Worker thread for scraping - now receives pre-installed driver path"""
    driver = setup_driver(driver_path)
    prefix = "unsafe" if is_unsafe else "safe"
    try:
        for term in terms:
            print(f"[Thread {thread_id}] Scraping ({prefix}): {term}")
            url = f"https://www.google.com/search?q={term.replace(' ', '+')}&tbm=isch&safe=off"
            driver.get(url)
            time.sleep(3)
            
            for i in range(TARGET_SCREENSHOTS_PER_TERM):
                driver.execute_script(f"window.scrollTo(0, {i * 1000});")
                time.sleep(1 + random.random())
                
                if i % 4 == 0:
                    try: driver.find_element(By.CSS_SELECTOR, ".mye4qd").click()
                    except: pass

                # Filename includes prefix so processor knows what to do
                filename = f"{prefix}_{sanitize(term)}_{i}_{int(time.time())}.png"
                driver.save_screenshot(str(RAW_DIR / filename))
                
    except Exception as e:
        print(f"[Thread {thread_id}] Error: {e}")
    finally:
        driver.quit()

# ===================== PROCESSOR (V16 LOGIC) =====================

def get_content_mask(img):
    # (Same V16 High-Sensitivity Masking Logic)
    inv = 255 - img
    diff_map = np.max(inv, axis=2)
    blurred_diff = cv2.GaussianBlur(diff_map, (5,5), 0)
    _, raw_mask = cv2.threshold(blurred_diff, 5, 255, cv2.THRESH_BINARY)
    
    kernel_erode = cv2.getStructuringElement(cv2.MORPH_RECT, (int(1.5*SCALE), int(1.5*SCALE)))
    no_text_mask = cv2.erode(raw_mask, kernel_erode, iterations=1)
    
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (int(5*SCALE), int(5*SCALE)))
    solid_mask = cv2.dilate(no_text_mask, kernel_dilate, iterations=1)
    
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (int(10*SCALE), int(10*SCALE)))
    return cv2.morphologyEx(solid_mask, cv2.MORPH_CLOSE, kernel_close)

def box_to_yolo(box, w, h):
    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2 / w
    cy = (y1 + y2) / 2 / h
    bw = (x2 - x1) / w
    bh = (y2 - y1) / h
    return f"0 {max(0,min(1,cx)):.6f} {max(0,min(1,cy)):.6f} {max(0,min(1,bw)):.6f} {max(0,min(1,bh)):.6f}"

def process_file(img_path):
    try:
        is_unsafe_file = img_path.name.startswith("unsafe")
        
        # Load Image
        original_img = cv2.imread(str(img_path))
        if original_img is None: return 0
        orig_h, orig_w = original_img.shape[:2]

        # --- PATH A: SAFE FILE ---
        # Strategy: Save image, create EMPTY label file.
        if not is_unsafe_file:
            shutil.copy(img_path, TRAIN_IMG_DIR / img_path.name)
            # Create empty .txt file
            (TRAIN_LBL_DIR / (img_path.stem + ".txt")).touch()
            return 1

        # --- PATH B: UNSAFE FILE ---
        # Strategy: Auto-detect boxes. If found, save image + labels.
        
        img = cv2.resize(original_img, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_CUBIC)
        h, w = img.shape[:2]
        
        mask = get_content_mask(img)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        final_boxes = []
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            
            # Simple UI Filter
            if (y < 150*SCALE) or (bw/bh > 3.0) or (bh < 50*SCALE):
                continue
                
            # Scale back
            orig_box = (
                int(x / SCALE), int(y / SCALE), 
                int((x+bw) / SCALE), int((y+bh) / SCALE)
            )
            final_boxes.append(orig_box)
            
        if final_boxes:
            shutil.copy(img_path, TRAIN_IMG_DIR / img_path.name)
            labels = [box_to_yolo(b, orig_w, orig_h) for b in final_boxes]
            with open(TRAIN_LBL_DIR / (img_path.stem + ".txt"), "w") as f:
                f.write("\n".join(labels))
            return 1
            
        return 0 # No valid boxes found in unsafe image
        
    except Exception as e:
        print(f"Error {img_path.name}: {e}")
        return 0

# ===================== MAIN =====================

def main():
    global DRIVER_PATH
    
    print("="*80)
    print(" AUTO DATASET GENERATOR v9 - BALANCED & SELF-SUFFICIENT")
    print("="*80)
    
    # Setup directories
    if RAW_DIR.exists(): shutil.rmtree(RAW_DIR)
    RAW_DIR.mkdir(parents=True)
    TRAIN_IMG_DIR.mkdir(parents=True, exist_ok=True)
    TRAIN_LBL_DIR.mkdir(parents=True, exist_ok=True)
    
    # CRITICAL FIX: Install ChromeDriver ONCE before starting threads
    print("\n[SETUP] Installing ChromeDriver (one-time)...")
    try:
        DRIVER_PATH = ChromeDriverManager().install()
        print(f"[SETUP] ChromeDriver installed at: {DRIVER_PATH}")
    except Exception as e:
        print(f"[ERROR] Failed to install ChromeDriver: {e}")
        return
    
    # 1. SCRAPING
    print("\n[PHASE 1] Starting scraping threads...")
    threads = []
    
    # Launch Unsafe Scrapers (2 threads)
    unsafe_chunks = [UNSAFE_TERMS[i::2] for i in range(2)]
    for i in range(2):
        t = threading.Thread(target=scrape_worker, args=(i, unsafe_chunks[i], True, DRIVER_PATH))
        t.start()
        threads.append(t)
        time.sleep(2)  # Stagger thread starts slightly
        
    # Launch Safe Scrapers (2 threads)
    safe_chunks = [SAFE_TERMS[i::2] for i in range(2)]
    for i in range(2):
        t = threading.Thread(target=scrape_worker, args=(i+2, safe_chunks[i], False, DRIVER_PATH))
        t.start()
        threads.append(t)
        time.sleep(2)  # Stagger thread starts slightly
        
    for t in threads: t.join()
    
    # 2. PROCESSING
    print("\n[PHASE 2] Processing & Auto-Labeling...")
    files = list(RAW_DIR.glob("*.png"))
    processed_count = 0
    
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(process_file, f): f for f in files}
        for future in as_completed(futures):
            processed_count += future.result()
            
    print("\n" + "="*80)
    print(" DATASET GENERATION COMPLETE")
    print(f" Total Training Samples: {processed_count}")
    print(" (Includes both labeled Toxic images and empty-label Safe images)")
    print("="*80)

if __name__ == "__main__":
    main()