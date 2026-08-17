"""Styles registry: 150+ curated animation styles with structured prompt templates.

Each style carries a real prompt suffix applied during generation and a
working preview URL (Pollinations renders the style prompt keylessly).
Categories mirror the oiioii.ai library: Anime, 3D/CG, Illustrated,
Pixel/Retro, Painting, Photographic, Cyberpunk, Minimalist and more.
"""
from typing import List, Dict, Any

STYLES: List[Dict[str, Any]] = []


def _add(sid: str, name: str, category: str, suffix: str, negative: str = "") -> None:
    preview_prompt = suffix.replace(", high quality", "").replace(", detailed", "").strip(" ,")
    preview_prompt = (preview_prompt or name) + ", style showcase, key visual"
    preview = "https://image.pollinations.ai/prompt/" + \
        "".join("%{:02X}".format(b) for b in preview_prompt.encode("utf-8")[:180]) + \
        "?width=320&height=180&nolog=true&seed=7"
    STYLES.append({
        "id": sid,
        "name": name,
        "category": category,
        "thumbnail": preview,
        "previewUrl": preview,
        "promptSuffix": suffix,
        "negativePrompt": negative,
        "isBuiltIn": True,
    })


# --- Anime (30) -------------------------------------------------------------
_anime = [
    ("ghibli", "Ghibli Style", "hand-painted cel animation, soft watercolor backgrounds, whimsical storybook atmosphere, Studio Ghibli inspired"),
    ("anime-shonen", "Shonen Anime", "dynamic shonen anime style, bold linework, high-energy action, vibrant colors"),
    ("anime-shojo", "Shojo Anime", "soft shojo anime style, sparkling eyes, pastel palette, romantic glow"),
    ("anime-90s", "90s Retro Anime", "1990s retro anime aesthetic, film grain, cel shading, nostalgic VHS tones"),
    ("anime-modern", "Modern Anime", "crisp modern anime style, clean digital lines, cinematic lighting"),
    ("sakuga", "Sakuga Action", "fluid sakuga animation style, expressive motion smears, dramatic impact frames"),
    ("chibi", "Chibi Cute", "adorable chibi style, oversized heads, tiny bodies, kawaii expressions"),
    ("mecha", "Mecha Anime", "detailed mecha anime style, giant robots, metallic panels, dramatic scale"),
    ("isekai", "Isekai Fantasy", "lush isekai fantasy anime, otherworldly landscapes, glowing magic"),
    ("slice-of-life", "Slice of Life", "warm slice-of-life anime, gentle afternoon light, cozy everyday moments"),
    ("dark-anime", "Dark Anime", "moody dark anime style, heavy shadows, psychological tension"),
    ("magical-girl", "Magical Girl", "sparkling magical girl style, transformation glow, frilly costumes"),
    ("sports-anime", "Sports Anime", "kinetic sports anime, motion lines, intense determination"),
    ("cyber-anime", "Cyber Anime", "neon cyberpunk anime, holographic UI, rain-slick streets"),
    ("samurai", "Samurai Era", "feudal Japan anime, ink-wash skies, katana glints, Edo period detail"),
    ("watercolor-anime", "Watercolor Anime", "delicate watercolor anime, bleeding pigments, dreamy softness"),
    ("pastel-anime", "Pastel Dream", "pastel-toned anime, cotton-candy skies, soothing palette"),
    ("noir-anime", "Anime Noir", "black-and-white anime noir, stark contrast, cigarette smoke curls"),
    ("school-anime", "School Days", "bright school-life anime, sunlit classrooms, cherry blossoms outside"),
    ("space-anime", "Space Opera Anime", "epic space opera anime, starfleets, nebula backdrops"),
    ("folklore-anime", "Yokai Folklore", "Japanese folklore anime, spirits and yokai, lantern-lit shrines"),
    ("idol", "Idol Stage", "glamorous idol anime, stage spotlights, glittering costumes"),
    ("post-apoc-anime", "Post-Apocalyptic Anime", "ruined-world anime, overgrown cities, lone wanderers"),
    ("steampunk-anime", "Steampunk Anime", "brass-and-gear steampunk anime, airships, Victorian coats"),
    ("vampire-anime", "Gothic Vampire", "gothic vampire anime, moonlit castles, crimson accents"),
    ("food-anime", "Culinary Anime", "mouth-watering food anime, glistening dishes, steam swirls"),
    ("music-anime", "Band Anime", "energetic band anime, instruments gleaming, live-house glow"),
    ("mecha-shojo", "Mecha Shojo", "pastel mecha-fusion anime, armored heroines, ribbon decals"),
    ("ukiyo-anime", "Ukiyo-e Anime", "anime fused with ukiyo-e woodblock prints, flat color blocks, wave motifs"),
    ("ink-anime", "Sumi Ink Anime", "anime drawn in sumi ink, brush strokes, negative space"),
]
for sid, name, suffix in _anime:
    _add(f"anime-{sid}", name, "Anime", f", {suffix}, high quality, detailed")

# --- 3D / CG (25) -----------------------------------------------------------
_cg = [
    ("pixar", "Pixar Look", "polished 3D animation style, expressive characters, global illumination, Pixar-like"),
    ("claymation", "Claymation", "stop-motion claymation look, fingerprint textures, handcrafted charm"),
    ("lowpoly", "Low Poly", "stylized low-poly 3D, faceted geometry, gradient skies"),
    ("toonshader", "Toon Shader", "cel-shaded 3D, thick outlines, flat color bands"),
    ("cgi-real", "Photoreal CGI", "photorealistic CGI render, subsurface scattering, ray tracing"),
    ("voxel", "Voxel World", "voxel-art 3D, cube-based geometry, isometric charm"),
    ("blender", "Indie 3D", "indie 3D render, soft studio lighting, subsurface glow"),
    ("rubber", "Rubber Hose", "1930s rubber-hose cartoon 3D, bouncy limbs, pie eyes"),
    ("porcelain", "Porcelain Doll", "glossy porcelain 3D figures, delicate paint details"),
    ("origami", "Origami Fold", "paper origami 3D world, folded creases, papercraft lighting"),
    ("lego", "Brick World", "interlocking brick toy 3D world, plastic sheen, minifigure scale"),
    ("plush", "Plush Toy", "soft plush-toy 3D, fuzzy fabric, stitched seams"),
    ("chrome", "Chrome Sculpture", "liquid chrome 3D sculpture, mirror reflections, studio backdrop"),
    ("hologram", "Hologram", "translucent hologram 3D, scanlines, cyan glow"),
    ("marble", "Marble Statue", "classical marble statue 3D, carved drapery, museum light"),
    ("gummy", "Gummy Candy", "glossy gummy-candy 3D, translucent sugar, bright colors"),
    ("wood", "Carved Wood", "hand-carved wooden 3D figures, grain texture, warm varnish"),
    ("ice", "Ice Sculpture", "crystalline ice 3D, refractive sparkle, cold blue light"),
    ("balloon", "Balloon Art", "twisted balloon-animal 3D, squeaky sheen, party colors"),
    ("paper-mache", "Papier-Mache", "papier-mache 3D craft, layered paper, matte paint"),
    ("ceramic", "Ceramic Glaze", "glazed ceramic 3D, kiln-fired shine, cobalt patterns"),
    ("neon3d", "Neon Wireframe", "glowing neon wireframe 3D, retrowave grid, black void"),
    ("isometric", "Isometric Diorama", "isometric 3D diorama, miniature rooms, tilt-shift depth"),
    ("chibi3d", "Chibi 3D", "chibi-proportioned 3D characters, big heads, glossy eyes"),
    ("mecha3d", "Mecha 3D", "hard-surface mecha 3D, panel lines, battle wear"),
]
for sid, name, suffix in _cg:
    _add(f"cg-{sid}", name, "3D/CG", f", {suffix}, high quality, detailed")

# --- Illustrated (25) -------------------------------------------------------
_ill = [
    ("storybook", "Storybook", "children's storybook illustration, gentle gouache, friendly shapes"),
    ("comic", "Comic Book", "bold comic book art, halftone dots, dynamic ink outlines"),
    ("manga-bw", "Manga Ink", "black-and-white manga page, screentone shading, expressive lines"),
    ("graphic-novel", "Graphic Novel", "painterly graphic novel art, moody palettes, textured brushwork"),
    ("webtoon", "Webtoon", "clean webtoon style, vertical-scroll composition, soft cel colors"),
    ("newspaper", "Newspaper Comic", "vintage newspaper comic strip, simple linework, sunday-page color"),
    ("franco", "Franco-Belgian", "ligne claire Franco-Belgian comic, flat color, crisp outlines"),
    ("poster", "Vintage Poster", "mid-century illustrated poster, limited palette, grain texture"),
    ("editorial", "Editorial Illustration", "conceptual editorial illustration, metaphorical imagery, flat shapes"),
    ("fashion", "Fashion Sketch", "elegant fashion illustration, loose ink, watercolor washes"),
    ("botanical", "Botanical Plate", "vintage botanical illustration, fine linework, aged paper"),
    ("cartoon-modern", "Modern Cartoon", "modern flat cartoon, rounded shapes, punchy colors"),
    ("doodle", "Doodle", "playful hand-drawn doodle style, loose pen, notebook paper"),
    ("sticker", "Sticker Pack", "die-cut sticker art, thick white borders, glossy fills"),
    ("tattoo", "Tattoo Flash", "traditional tattoo flash, bold lines, sailor-jerry palette"),
    ("woodcut", "Woodcut Print", "rough woodcut print, carved contrast, ink texture"),
    ("linocut", "Linocut", "hand-pulled linocut print, gouge marks, two-tone ink"),
    ("riso", "Risograph", "risograph print style, misregistered inks, grainy duotone"),
    ("screenprint", "Screen Print", "screen-printed poster, layered spot colors, subtle grain"),
    ("papercut", "Paper Cutout", "layered paper cutout art, shadow depth, craft edges"),
    ("collage", "Mixed Collage", "mixed-media collage, torn paper, vintage clippings"),
    ("infographic", "Infographic", "clean infographic illustration, icons, isometric charts"),
    ("childrens", "Crayon Kids", "childlike crayon drawing, waxy strokes, joyful scribbles"),
    ("chalk", "Chalkboard", "chalkboard illustration, dusty strokes, dark slate background"),
    ("scratchboard", "Scratchboard", "scratchboard art, white lines scratched from black ink"),
]
for sid, name, suffix in _ill:
    _add(f"ill-{sid}", name, "Illustrated", f", {suffix}, high quality, detailed")

# --- Pixel / Retro (20) -----------------------------------------------------
_px = [
    ("pixel8", "8-Bit Pixel", "8-bit pixel art, limited palette, NES-era charm"),
    ("pixel16", "16-Bit Pixel", "16-bit pixel art, SNES-era detail, dithering"),
    ("pixel32", "Hi-Bit Pixel", "high-bit pixel art, modern lighting effects, crisp sprites"),
    ("gameboy", "Game Boy", "monochrome Game Boy palette, 4 shades of green"),
    ("cga", "CGA Retro", "CGA 4-color retro computer art, magenta and cyan"),
    ("arcade", "Arcade Cabinet", "retro arcade pixel art, scanlines, marquee glow"),
    ("isometric-pixel", "Isometric Pixel", "isometric pixel art, tiny buildings, ant-sized people"),
    ("pixel-portrait", "Pixel Portrait", "detailed pixel-art portrait, careful dithering"),
    ("vhs", "VHS Tape", "VHS analog aesthetic, tracking lines, chroma bleed"),
    ("crt", "CRT Scanlines", "CRT monitor aesthetic, scanlines, phosphor glow"),
    ("synthwave", "Synthwave", "synthwave retro-future, chrome text, magenta sunset grid"),
    ("vaporwave", "Vaporwave", "vaporwave aesthetic, marble busts, pastel gradients, kanji"),
    ("atari", "Atari 2600", "Atari 2600 blocky graphics, thick pixels, abstract shapes"),
    ("amiga", "Amiga Demoscene", "Amiga demoscene art, gradient skies, tracker-music mood"),
    ("pixel-platformer", "Platformer Pixel", "cheerful platformer pixel art, grassy tiles, fluffy clouds"),
    ("pixel-rpg", "JRPG Pixel", "16-bit JRPG pixel art, town maps, sprite battles"),
    ("pixel-noir", "Pixel Noir", "moody pixel-art noir, rain, neon reflections"),
    ("pixel-space", "Pixel Space", "retro pixel space scene, starfields, chunky ships"),
    ("dotmatrix", "Dot Matrix", "dot-matrix LED display art, glowing dots, dark board"),
    ("lcd", "Handheld LCD", "handheld LCD game aesthetic, segmented pixels, olive screen"),
]
for sid, name, suffix in _px:
    _add(f"px-{sid}", name, "Pixel/Retro", f", {suffix}, high quality, detailed")

# --- Painting (20) ----------------------------------------------------------
_paint = [
    ("oil", "Oil Painting", "classical oil painting, visible brushstrokes, canvas texture"),
    ("impressionist", "Impressionist", "impressionist painting, dappled light, loose color"),
    ("watercolor", "Watercolor", "loose watercolor painting, wet-on-wet blooms, white paper"),
    ("gouache", "Gouache", "matte gouache painting, bold opaque shapes"),
    ("acrylic", "Acrylic", "textured acrylic painting, palette-knife ridges"),
    ("inkwash", "Ink Wash", "East Asian ink wash painting, graded sumi, misty mountains"),
    ("fresco", "Fresco", "Renaissance fresco, plaster texture, muted earth tones"),
    ("tempera", "Egg Tempera", "egg tempera panel painting, fine hatching, gold leaf"),
    ("pointillism", "Pointillism", "pointillist painting, dots of pure color, optical mixing"),
    ("expressionism", "Expressionism", "expressionist painting, distorted forms, raw emotion"),
    ("surrealism", "Surrealism", "surrealist painting, dream logic, impossible juxtapositions"),
    ("cubism", "Cubism", "cubist painting, fractured planes, multiple viewpoints"),
    ("popart", "Pop Art", "pop art, ben-day dots, saturated commercial color"),
    ("minimalpaint", "Color Field", "color-field painting, vast flat expanses, quiet scale"),
    ("baroque", "Baroque", "baroque painting, chiaroscuro drama, rich drapery"),
    ("rococo", "Rococo", "rococo painting, pastel elegance, playful cherubs"),
    ("ukiyoe", "Ukiyo-e", "ukiyo-e woodblock print, flat color, bold contours, great wave"),
    ("miniature", "Persian Miniature", "Persian miniature painting, intricate pattern, lapis blue"),
    ("icon", "Byzantine Icon", "Byzantine icon painting, gold ground, solemn gaze"),
    ("pleinair", "Plein Air", "plein-air landscape sketch, quick brushwork, open sky"),
]
for sid, name, suffix in _paint:
    _add(f"paint-{sid}", name, "Painting", f", {suffix}, high quality, detailed")

# --- Photographic (15) ------------------------------------------------------
_photo = [
    ("cinematic", "Cinematic Film", "cinematic film still, anamorphic bokeh, graded teal-orange"),
    ("documentary", "Documentary", "natural documentary photography, available light, candid"),
    ("film35", "35mm Film", "35mm film photography, grain, true-to-life color"),
    ("polaroid", "Polaroid", "polaroid instant photo, faded color, white frame"),
    ("blackwhite", "Black & White", "black-and-white photography, rich tonal range"),
    ("goldenhour", "Golden Hour", "golden-hour photography, warm backlight, long shadows"),
    ("neonphoto", "Neon Night", "neon-lit night photography, wet asphalt reflections"),
    ("studio", "Studio Portrait", "studio portrait photography, softbox lighting, seamless backdrop"),
    ("macro", "Macro", "macro photography, shallow depth of field, fine detail"),
    ("aerial", "Aerial", "aerial drone photography, top-down patterns"),
    ("longexp", "Long Exposure", "long-exposure photography, light trails, silky water"),
    ("hdr", "HDR Landscape", "HDR landscape photography, crisp detail, vivid sky"),
    ("infrared", "Infrared", "infrared photography, white foliage, dark skies"),
    ("tiltshift", "Tilt-Shift", "tilt-shift miniature photography, selective focus"),
    ("street", "Street Photo", "street photography, decisive moment, urban geometry"),
]
for sid, name, suffix in _photo:
    _add(f"photo-{sid}", name, "Photographic", f", {suffix}, high quality, detailed")

# --- Cyberpunk (10) ---------------------------------------------------------
_cyber = [
    ("neoncity", "Neon City", "cyberpunk neon city, holographic ads, rain, dense signage"),
    ("glitch", "Glitch Art", "glitch art, databent pixels, RGB channel splits"),
    ("terminal", "Terminal Green", "retro terminal aesthetic, green phosphor text, dark CRT"),
    ("mech-hud", "Mech HUD", "mecha cockpit HUD view, tactical overlays, warning glyphs"),
    ("chrome-punk", "Chrome Punk", "chromed cyberpunk portraits, mirror skin, fiber-optic hair"),
    ("dystopia", "Dystopia", "dystopian megacity, brutalist towers, smog haze"),
    ("netrun", "Netrunner", "virtual-reality datascape, wireframe terrain, code rain"),
    ("biopunk", "Biopunk", "biopunk aesthetic, bioluminescent grafts, organic tech"),
    ("solarpunk", "Solarpunk", "solarpunk future, green towers, stained-glass solar panels"),
    ("dreampunk", "Dreampunk", "dreampunk aesthetic, pastel vapor skies, floating plazas"),
]
for sid, name, suffix in _cyber:
    _add(f"cyber-{sid}", name, "Cyberpunk", f", {suffix}, high quality, detailed")

# --- Minimalist (15) --------------------------------------------------------
_min = [
    ("flat", "Flat Design", "flat vector design, geometric shapes, no gradients"),
    ("lineart", "Line Art", "minimal single-line art, continuous stroke, white background"),
    ("bauhaus", "Bauhaus", "bauhaus geometric design, primary colors, bold grids"),
    ("swiss", "Swiss Grid", "Swiss international style, strict grid, Helvetica clarity"),
    ("mono", "Monochrome", "minimal monochrome composition, single hue, negative space"),
    ("duotone", "Duotone", "duotone minimal art, two-color gradient mapping"),
    ("outline", "Outline Only", "clean outline drawing, uniform stroke weight"),
    ("geometric", "Geometric Abstract", "geometric abstraction, balanced primitives"),
    ("gradient", "Soft Gradient", "soft gradient minimalism, blurred orbs, airy"),
    ("icon-set", "Icon Set", "minimal icon design, rounded corners, consistent stroke"),
    ("wireframe", "Wireframe", "minimal wireframe sketch, blueprint lines"),
    ("silhouette", "Silhouette", "bold silhouette art, single color, strong shapes"),
    ("zen", "Zen Minimal", "zen minimal composition, stone, sand, stillness"),
    ("scandi", "Scandi Minimal", "Scandinavian minimal interior, pale wood, hygge light"),
    ("brutalist", "Brutalist Minimal", "brutalist minimal concrete, raw geometry, harsh light"),
]
for sid, name, suffix in _min:
    _add(f"min-{sid}", name, "Minimalist", f", {suffix}, high quality, detailed")


def count_by_category(styles: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count styles per category."""
    counts: Dict[str, int] = {}
    for s in styles:
        cat = s.get("category", "Unknown")
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def filter_by_category(styles: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
    """Filter styles by category."""
    return [s for s in styles if s.get("category") == category]


def get_style(style_id: str) -> Dict[str, Any]:
    """Return a single style by id (or empty dict)."""
    for s in STYLES:
        if s["id"] == style_id:
            return s
    return {}


__all__ = ["STYLES", "count_by_category", "filter_by_category", "get_style"]
