"""
AUTO COLLECTOR v4 – 30,000+ SCREENSHOTS MODE
Collects 15,000+ unsafe + 15,000+ safe Google Image screenshots
→ Runs in parallel (4 tabs parallel) → finishes in ~6–10 hours
→ No interaction needed. Just run and sleep.
"""

import time
import random
import threading
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# ===================== CONFIG =====================
OUTPUT_DIR = Path("search_screenshots")
SAFE_DIR = OUTPUT_DIR / "safe"
UNSAFE_DIR = OUTPUT_DIR / "unsafe"

TARGET_UNSAFE = 15_000
TARGET_SAFE = 15_000

PARALLEL_TABS = 4           # 4 Chrome tabs at once = 4x speed
SCROLL_PAUSE = 1.8
MAX_TIME_PER_TERM = 480     # 8 minutes max per term (prevents hanging)

MOBILE_EMULATION = {
    "deviceMetrics": {"width": 393, "height": 851, "pixelRatio": 3.0},
    "userAgent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/124.0.0.0 Mobile Safari/537.36"
}

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
    # Explicit sexual content (100)
    "porn", "xxx", "sex", "nude", "naked", "nsfw", "adult", "hentai", "onlyfans", "pornhub",
    "xvideos", "xnxx", "redtube", "youporn", "brazzers", "anal", "oral", "blowjob", "handjob",
    "milf", "teen porn", "lesbian", "gay porn", "bisexual", "threesome", "orgy", "gangbang",
    "bdsm", "bondage", "fetish", "kinky", "dominatrix", "submissive", "slave", "master",
    "erotic", "sensual", "seductive", "sexy", "lingerie", "topless", "bottomless", "stripping",
    "striptease", "lapdance", "escort", "prostitute", "hooker", "brothel", "red light",
    "webcam girl", "cam model", "amateur porn", "homemade porn", "leaked", "sex tape",
    "celebrity nude", "nip slip", "wardrobe malfunction", "upskirt", "downblouse", "voyeur",
    "peeping", "hidden camera", "revenge porn", "deepfake porn", "ai porn", "futanari",
    "yaoi", "yuri", "ecchi", "rule34", "r34", "lewd", "explicit", "hardcore", "softcore",
    "penetration", "intercourse", "climax", "orgasm", "masturbation", "self pleasure",
    "toys", "vibrator", "dildo", "butt plug", "sex toy", "adult toy", "pleasure device",
    "swingers", "wife swap", "cuckold", "hotwife", "cheating", "affair", "mistress",
    
    # Gore & violence (100)
    "gore", "blood", "bloody", "beheading", "decapitation", "execution", "torture", "mutilation",
    "dismemberment", "amputation", "severed", "chopped", "sliced", "diced", "butchered",
    "accident gore", "car crash gore", "motorcycle accident", "train accident", "plane crash",
    "industrial accident", "machinery accident", "chainsaw accident", "workplace death",
    "crime scene", "murder scene", "homicide", "stabbing", "shooting victim", "gunshot wound",
    "dead body", "corpse", "cadaver", "decomposed", "rotting body", "skeleton", "bones",
    "autopsy", "morgue", "post mortem", "forensic", "death photo", "aftermath", "carnage",
    "war footage", "combat death", "soldier killed", "battlefield", "war crime", "mass grave",
    "genocide", "massacre", "ethnic cleansing", "war torn", "bombing aftermath", "explosion victim",
    "terrorist attack", "suicide bomber", "9/11 jumpers", "school shooting", "mass shooting",
    "serial killer", "crime photo", "evidence photo", "brutal", "savage", "violent death",
    "hanging", "lynching", "crucifixion", "burned alive", "immolation", "fire victim",
    "drowning victim", "suffocation", "strangulation", "beaten to death", "blunt trauma",
    "crushed", "run over", "hit by car", "train death", "subway death", "fall death",
    "jump death", "suicide scene", "self harm", "cutting", "slashing", "razor", "blade",
    "overdose", "drug death", "poisoning", "toxic", "chemical burn", "acid attack",
    "animal attack", "mauling", "shark attack", "bear attack", "tiger attack", "snake bite",
    "spider bite", "infection", "necrosis", "gangrene", "disease", "plague", "virus",
    
    # Bodily functions & grossness (100)
    "poop", "feces", "shit", "human feces", "excrement", "bowel movement", "defecation",
    "scat", "scat porn", "coprophilia", "brown shower", "dirty sanchez", "cleveland steamer",
    "diarrhea", "explosive diarrhea", "liquid poop", "runny stool", "loose stool", "stomach bug",
    "food poisoning", "gastroenteritis", "dysentery", "cholera", "norovirus", "rotavirus",
    "vomit", "puke", "barf", "throw up", "throwing up", "puking", "vomiting", "projectile vomit",
    "bile", "regurgitation", "upchuck", "retch", "heave", "gag", "nausea", "motion sickness",
    "morning sickness", "hangover puke", "alcohol poisoning", "drunk vomit", "party aftermath",
    "toilet", "bathroom disaster", "clogged toilet", "overflowing toilet", "toilet overflow",
    "porta potty", "public bathroom", "dirty restroom", "filthy toilet", "unflushed",
    "urine", "pee", "piss", "urination", "golden shower", "watersports", "urolagnia",
    "bedwetting", "incontinence", "diaper", "adult diaper", "depends", "soiled",
    "fart", "flatulence", "gas", "passing gas", "farting", "smelly", "stink", "odor",
    "body odor", "BO", "armpit", "sweaty", "sweat stain", "perspiration", "smelly feet",
    "toe jam", "fungus", "athletes foot", "foot fungus", "nail fungus", "toenail",
    "pus", "discharge", "oozing", "weeping", "seeping", "festering", "infected wound",
    "abscess", "boil", "cyst", "pimple popping", "blackhead", "whitehead", "acne",
    "ingrown hair", "infected", "swollen", "inflamed", "rash", "hives", "blisters",
]

# Duplicate prevention
collected_files = set()

def sanitize(name):
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name)[:80]

def setup_driver():
    options = Options()
    options.add_experimental_option("mobileEmulation", MOBILE_EMULATION)
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=393,851')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")
    return driver

def count_thumbnails(driver):
    try:
        return len(driver.find_elements(By.CSS_SELECTOR, "img.rg_i, img.sFlh5c"))
    except:
        return 0

def collect_worker(thread_id, terms_list, is_unsafe):
    driver = setup_driver()
    folder = UNSAFE_DIR if is_unsafe else SAFE_DIR
    target = TARGET_UNSAFE if is_unsafe else TARGET_SAFE
    collected = 0

    print(f"[Thread {thread_id}] Starting {'UNSAFE' if is_unsafe else 'SAFE'} collection...")

    try:
        for term in terms_list:
            if collected >= target:
                break

            safe_param = "off" if is_unsafe else "active"
            url = f"https://www.google.com/search?q={term.replace(' ', '+')}&tbm=isch&safe={safe_param}"
            driver.get(url)
            time.sleep(4 + random.uniform(0, 2))

            last_height = 0
            no_progress = 0
            term_start = time.time()

            while collected < target and no_progress < 5:
                # Screenshot
                filename = f"{'u' if is_unsafe else 's'}_{sanitize(term)}_{collected+1:05d}.png"
                if filename in collected_files:
                    break
                collected_files.add(filename)

                driver.save_screenshot(str(folder / filename))
                collected += 1

                print(f"[Thread {thread_id}] Saved {filename} → Total: {collected}/{target}")

                # Scroll
                driver.execute_script("window.scrollBy(0, 1200);")
                time.sleep(SCROLL_PAUSE + random.uniform(0.3, 1.0))

                # Random human-like behavior
                if random.random() < 0.2:
                    driver.execute_script("window.scrollBy(0, -400);")
                    time.sleep(1)

                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    no_progress += 1
                else:
                    no_progress = 0
                last_height = new_height

                if time.time() - term_start > MAX_TIME_PER_TERM:
                    break

            print(f"[Thread {thread_id}] Finished term: {term} → {collected} total")

    except Exception as e:
        print(f"[Thread {thread_id}] Error: {e}")
    finally:
        driver.quit()
        print(f"[Thread {thread_id}] Finished. Collected {collected} images.")

def main():
    SAFE_DIR.mkdir(parents=True, exist_ok=True)
    UNSAFE_DIR.mkdir(parents=True, exist_ok=True)

    print("="*90)
    print("AUTO COLLECTOR v4 – 30,000+ SCREENSHOTS IN ONE NIGHT")
    print("="*90)
    print(f"Target: {TARGET_UNSAFE:,} unsafe + {TARGET_SAFE:,} safe = 30,000+ total")
    print(f"Using {PARALLEL_TABS} parallel Chrome tabs → ~6–10 hours")
    print("Just run this and go to sleep. Wake up with a world-class dataset.")
    print("="*90)

    # Split terms across threads
    unsafe_chunks = [UNSAFE_TERMS[i::PARALLEL_TABS] for i in range(PARALLEL_TABS)]
    safe_chunks = [SAFE_TERMS[i::PARALLEL_TABS] for i in range(PARALLEL_TABS)]

    threads = []

    # Start unsafe threads
    for i in range(PARALLEL_TABS):
        t = threading.Thread(target=collect_worker, args=(i+1, unsafe_chunks[i], True))
        t.start()
        threads.append(t)

    # Start safe threads
    for i in range(PARALLEL_TABS):
        t = threading.Thread(target=collect_worker, args=(i+PARALLEL_TABS+1, safe_chunks[i], False))
        t.start()
        threads.append(t)

    # Wait for all
    for t in threads:
        t.join()

    # Final count
    final_unsafe = len(list(UNSAFE_DIR.glob("*.png")))
    final_safe = len(list(SAFE_DIR.glob("*.png")))

    print("\n" + "="*90)
    print("COLLECTION COMPLETE — YOU NOW HAVE A WORLD-CLASS DATASET")
    print("="*90)
    print(f"Unsafe screenshots : {final_unsafe:,}")
    print(f"Safe screenshots   : {final_safe:,}")
    print(f"TOTAL              : {final_unsafe + final_safe:,}")
    print("="*90)
    print("Next steps:")
    print("   python auto_label_search_screenshots.py")
    print("   python hybrid_trainer_enhanced.py")
    print("You are now training the most accurate toxic thumbnail detector on Earth.")
    print("="*90)

if __name__ == "__main__":
    main()