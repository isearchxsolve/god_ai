"""Styles registry with 150+ real named styles for the AI Animation Canvas.

Each style includes a prompt suffix for consistent styling across providers.
Styles are grouped by category for the frontend picker. Every style has a
real, optimized prompt template based on actual anime/animation artistic
tradition — not generic "Style 0/1/2" placeholders.
"""
from typing import List, Dict, Any, Optional

# =============================================================================
# Real named styles with optimized prompt suffixes
# =============================================================================

STYLES: List[Dict[str, Any]] = []

def _add_style(
    sid: str,
    name: str,
    category: str,
    prompt_suffix: str,
    description: str = "",
    negative_prompt: str = "",
    lighting: str = "",
    color_palette: List[str] = None,
) -> None:
    """Helper to append a style with full metadata."""
    STYLES.append({
        "id": sid,
        "name": name,
        "category": category,
        "description": description,
        "promptSuffix": prompt_suffix,
        "negativePrompt": negative_prompt,
        "lighting": lighting,
        "colorPalette": color_palette or [],
        # Pollinations is keyless, so use it for previews
        "thumbnail": f"https://image.pollinations.ai/prompt/{prompt_suffix[:200].replace(' ', '%20')}&width=256&height=256&nologo=true&seed=42",
        "previewUrl": f"https://image.pollinations.ai/prompt/{prompt_suffix[:200].replace(' ', '%20')}&width=512&height=512&nologo=true&seed=42",
        "isBuiltIn": True,
    })


# -----------------------------------------------------------------------------
# ANIME STYLES (Japanese animation tradition)
# -----------------------------------------------------------------------------
_add_style("ghibli", "Studio Ghibli", "Anime",
    "Studio Ghibli style, soft watercolor backgrounds, hand-drawn animation, Hayao Miyazaki, warm pastoral lighting, gentle atmosphere, lush nature, detailed clouds",
    "Hand-painted Ghibli aesthetic with soft lighting and nature", "harsh lines, 3D render, photorealistic")
_add_style("makoto-shinkai", "Makoto Shinkai", "Anime",
    "Makoto Shinkai style, hyper-detailed skies, volumetric clouds, cinematic lens flare, golden hour lighting, emotional atmosphere, deep blue gradients",
    "Surreal skies and emotional cinematography", "")
_add_style("naruto", "Naruto Shippuden", "Anime",
    "Naruto Shippuden anime style, bold outlines, dynamic action poses, spiky hair, ninja headbands, intense expressions, studio Pierrot",
    "Classic Naruto ninja aesthetic", "")
_add_style("one-piece", "One Piece", "Anime",
    "One Piece anime style, Eiichiro Oda, exaggerated expressions, rubber-like characters, ocean adventure, vibrant tropical colors",
    "Oda's distinctive pirate art style", "")
_add_style("demon-slayer", "Demon Slayer (Kimetsu no Yaiba)", "Anime",
    "Demon Slayer ufotable style, watercolor texture, elemental breathing effects, dynamic swordplay, vivid color gradients, high-quality animation",
    "Ufotable's watercolor breathing effects", "")
_add_style("jujutsu-kaisen", "Jujutsu Kaisen", "Anime",
    "Jujutsu Kaisen anime style, MAPPA studio, dark supernatural curse energy, dynamic fight choreography, detailed character designs",
    "MAPPA dark supernatural aesthetic", "")
_add_style("attack-on-titan", "Attack on Titan", "Anime",
    "Attack on Titan anime style, Wit Studio, dark intense expressions, vertical maneuvering equipment, grim atmosphere, detailed backgrounds",
    "Dark grim titan-fighting aesthetic", "")
_add_style("my-hero-academia", "My Hero Academia", "Anime",
    "My Hero Academia anime style, Kohei Horikoshi, superhero comic influence, dynamic action, bright bold colors, studio Bones",
    "Superhero anime aesthetic", "")
_add_style("death-note", "Death Note", "Anime",
    "Death Note anime style, Madhouse, dark psychological thriller, dramatic shadows, gothic typography, intense close-ups",
    "Psychological thriller dark aesthetic", "")
_add_style("cowboy-bebop", "Cowboy Bebop", "Anime",
    "Cowboy Bebop style, Shinichiro Watanabe, jazz noir aesthetic, 70s color grading, space western, detailed character designs",
    "Jazz noir space western aesthetic", "")
_add_style("evangelion", "Neon Genesis Evangelion", "Anime",
    "Neon Genesis Evangelion style, Hideaki Anno, psychological mecha, desaturated palette, clinical atmosphere, Gainax",
    "Psychological mecha aesthetic", "")
_add_style("akira", "Akira", "Anime",
    "Akira anime style, Katsuhiro Otomo, neo-Tokyo cyberpunk, detailed mechanical designs, fluid animation, high frame rate",
    "Otomo's iconic cyberpunk aesthetic", "")
_add_style("ghost-in-shell", "Ghost in the Shell", "Anime",
    "Ghost in the Shell style, Mamoru Oshii, cyberpunk philosophy, detailed urban environments, blue-green palette, Production IG",
    "Cyberphilosophy aesthetic", "")
_add_style("violet-evergarden", "Violet Evergarden", "Anime",
    "Violet Evergarden style, Kyoto Animation, ultra-detailed Victorian aesthetics, emotional lighting, photographic depth of field",
    "KyoAni ultra-detailed aesthetic", "")
_add_style("your-name", "Your Name (Kimi no Na wa)", "Anime",
    "Your Name style, Makoto Shinkai, body swap romance, stunning twilight skies, Tokyo cityscape, emotional golden hour",
    "Shinkai romance twilight aesthetic", "")
_add_style("spirited-away", "Spirited Away", "Anime",
    "Spirited Away style, Studio Ghibli, bathhouse spirits, Japanese folklore, rich red and gold palette, ethereal atmosphere",
    "Ghibli spirit world aesthetic", "")
_add_style("princess-mononoke", "Princess Mononoke", "Anime",
    "Princess Mononoke style, Studio Ghibli, forest spirits, epic nature, detailed animal designs, earthy color palette",
    "Ghibli epic forest aesthetic", "")
_add_style("howl-moving-castle", "Howl's Moving Castle", "Anime",
    "Howl's Moving Castle style, Studio Ghibli, steampunk castle, Victorian fantasy, soft pastel colors, elaborate architecture",
    "Ghibli steampunk fantasy aesthetic", "")
_add_style("castle-in-sky", "Castle in the Sky", "Anime",
    "Castle in the Sky style, Studio Ghibli, floating island, retro-futuristic, adventure atmosphere, warm earth tones",
    "Ghibli sky adventure aesthetic", "")
_add_style("kiki-delivery", "Kiki's Delivery Service", "Anime",
    "Kiki's Delivery Service style, Studio Ghibli, cozy European town, coming-of-age, warm pastel palette, gentle storytelling",
    "Ghibli cozy coming-of-age aesthetic", "")

# -----------------------------------------------------------------------------
# CHINESE ANIMATION (Donghua)
# -----------------------------------------------------------------------------
_add_style("chibi-anime", "Chibi Anime", "Anime",
    "chibi anime style, super deformed, large heads, small bodies, cute expressions, pastel colors, kawaii aesthetic",
    "Cute chibi proportions", "")
_add_style("lotus-lantern", "Lotus Lantern (Baolian Deng)", "Chinese Animation",
    "Chinese donghua style, Lotus Lantern, traditional Chinese mythology, ink wash backgrounds, flowing robes, oriental fantasy",
    "Chinese mythological animation", "")
_add_style("white-snake", "White Snake (Bai She)", "Chinese Animation",
    "White Snake donghua style, Light Chaser Animation, Chinese folklore, flowing silk, traditional architecture, romantic atmosphere",
    "Chinese folklore romance aesthetic", "")
_add_style("ne-zha", "Ne Zha", "Chinese Animation",
    "Ne Zha donghua style, Light Chaser Animation, Chinese mythology, fiery effects, dynamic action, traditional motifs",
    "Chinese mythological action aesthetic", "")
_add_style("scissor-seven", "Scissor Seven", "Chinese Animation",
    "Scissor Seven donghua style, simplified character designs, comedic expressions, Chinese humor, flat color blocks",
    "Chinese comedy animation aesthetic", "")

# -----------------------------------------------------------------------------
# KOREAN ANIMATION (Manhwa/Aeni)
# -----------------------------------------------------------------------------
_add_style("korean-manhwa", "Korean Manhwa", "Korean Animation",
    "Korean manhwa style, webtoon aesthetic, vertical scroll format, clean line art, gradient backgrounds, modern character designs",
    "Webtoon manhwa aesthetic", "")
_add_style("solo-leveling", "Solo Leveling", "Korean Animation",
    "Solo Leveling manhwa style, detailed shadow work, hunter aesthetic, blue-purple glow effects, dramatic lighting",
    "Hunter RPG manhwa aesthetic", "")
_add_style("tower-of-god", "Tower of God", "Korean Animation",
    "Tower of God manhwa style, SIU, surreal architecture, diverse character designs, vertical progression themes",
    "Surreal tower-climbing aesthetic", "")

# -----------------------------------------------------------------------------
# REALISTIC / CINEMATIC
# -----------------------------------------------------------------------------
_add_style("cinematic-8k", "Cinematic 8K Photorealistic", "Realistic",
    "cinematic 8K photorealistic, hyperdetailed, dramatic lighting, film grain, anamorphic lens, depth of field, color graded",
    "High-end cinematic photorealism", "")
_add_style("hbo-style", "HBO prestige style", "Realistic",
    "HBO prestige TV style, muted color palette, naturalistic lighting, film grain, realistic cinematography, atmospheric",
    "Prestige TV naturalistic aesthetic", "")
_add_style("imax-70mm", "IMAX 70mm film", "Realistic",
    "IMAX 70mm film aesthetic, ultra-sharp, high dynamic range, epic scale, sweeping landscapes, Christopher Nolan style",
    "IMAX epic film aesthetic", "")
_add_style("tarantino", "Quentin Tarantino style", "Realistic",
    "Quentin Tarantino cinematic style, 70mm anamorphic, intense close-ups, bold color choices, dramatic tension",
    "Tarantino cinematic aesthetic", "")
_add_style("villeneuve", "Denis Villeneuve style", "Realistic",
    "Denis Villeneuve style, Blade Runner 2049 aesthetic, monumental scale, orange-and-teal palette, slow contemplative camera",
    "Villeneuve sci-fi aesthetic", "")
_add_style("wes-anderson", "Wes Anderson style", "Realistic",
    "Wes Anderson style, symmetrical compositions, pastel color palette, retro aesthetic, whimsical, precise framing",
    "Anderson symmetrical pastel aesthetic", "")
_add_style("studio-ghibli-live", "Ghibli Live-Action Look", "Realistic",
    "live action with Studio Ghibli color palette, soft natural lighting, lush green environments, golden hour warmth",
    "Live-action Ghibli color palette", "")

# -----------------------------------------------------------------------------
# 3D / CGI
# -----------------------------------------------------------------------------
_add_style("pixar", "Pixar Style 3D", "3D",
    "Pixar 3D animation style, subsurface scattering, polished surfaces, expressive characters, warm color palette, Renderman quality",
    "Pixar polished 3D aesthetic", "")
_add_style("disney-3d", "Disney 3D Animation", "3D",
    "Disney 3D animation style, Moana/Frozen aesthetic, detailed hair simulation, lush environments, musical color palette",
    "Disney musical 3D aesthetic", "")
_add_style("dreamworks-3d", "DreamWorks 3D", "3D",
    "DreamWorks 3D animation style, Puss in Boots quality, dynamic action, expressive faces, rich textures",
    "DreamWorks quality 3D aesthetic", "")
_add_style("shading-3dsmax", "3ds Max Render", "3D",
    "3ds Max V-Ray render, architectural visualization, photorealistic materials, global illumination, clean studio lighting",
    "3ds Max V-Ray architectural aesthetic", "")
_add_style("blender-cycles", "Blender Cycles Render", "3D",
    "Blender Cycles render, photorealistic path tracing, PBR materials, HDRI lighting, modern 3D aesthetic",
    "Blender Cycles PBR aesthetic", "")
_add_style("unreal-engine", "Unreal Engine 5", "3D",
    "Unreal Engine 5 render, Nanite geometry, Lumen global illumination, photorealistic real-time, cinematic depth of field",
    "UE5 photoreal aesthetic", "")
_add_style("claymation", "Claymation / Stop Motion", "3D",
    "claymation stop motion style, Wallace and Gromit aesthetic, clay texture, handmade charm, visible fingerprints, Aardman style",
    "Aardman clay texture aesthetic", "")
_add_style("low-poly-3d", "Low Poly 3D", "3D",
    "low poly 3D style, flat shaded polygons, minimal geometry, vibrant colors, isometric perspective, game art aesthetic",
    "Stylized low poly game aesthetic", "")
_add_style("voxel-art", "Voxel Art", "3D",
    "voxel art style, Minecraft aesthetic, cubic blocks, blocky characters, isometric view, vibrant saturated colors",
    "Voxel cubic aesthetic", "")
_add_style("isometric-3d", "Isometric 3D Illustration", "3D",
    "isometric 3D illustration, 45 degree angle, clean vector-like 3D, soft gradients, miniature diorama feel",
    "Isometric diorama 3D aesthetic", "")

# -----------------------------------------------------------------------------
# PIXEL ART
# -----------------------------------------------------------------------------
_add_style("pixel-16bit", "16-Bit Pixel Art (SNES)", "Pixel Art",
    "16-bit pixel art, SNES era, detailed sprites, limited color palette, dithering patterns, retro game aesthetic",
    "SNES-era pixel art aesthetic", "")
_add_style("pixel-8bit", "8-Bit Pixel Art (NES)", "Pixel Art",
    "8-bit pixel art, NES era, chunky pixels, 4-color palette, simple sprites, retro game aesthetic, Castlevania style",
    "NES-era 8-bit pixel aesthetic", "")
_add_style("pixel-32bit", "32-Bit Pixel Art (PS1)", "Pixel Art",
    "32-bit pixel art, PlayStation 1 era, pre-rendered backgrounds, low-res textures, PS1 aesthetic, Symphony of the Night",
    "PS1-era 32-bit pixel aesthetic", "")
_add_style("pixel-modern", "Modern HD Pixel Art", "Pixel Art",
    "modern HD pixel art, Octopath Traveler style, HD-2D hybrid, lighting effects on pixel art, depth of field, high resolution",
    "HD-2D modern pixel aesthetic", "")
_add_style("pixel-isometric", "Isometric Pixel Art", "Pixel Art",
    "isometric pixel art, clean lines, detailed environments, retro game tilemap, limited palette, simulation game aesthetic",
    "Isometric pixel game aesthetic", "")
_add_style("pixel-gothic", "Gothic Pixel Art", "Pixel Art",
    "gothic pixel art, dark fantasy, detailed shading, atmospheric lighting, Castlevania Symphony of the Night style",
    "Dark gothic pixel aesthetic", "")

# -----------------------------------------------------------------------------
# TRADITIONAL ART / PAINTING
# -----------------------------------------------------------------------------
_add_style("watercolor", "Watercolor Painting", "Watercolor",
    "watercolor painting, soft washes, bleeding colors, paper texture, traditional media, organic edges, translucent layers",
    "Traditional watercolor painting", "")
_add_style("oil-painting", "Oil Painting", "Oil Painting",
    "oil painting, thick impasto brush strokes, rich texture, classical technique, deep colors, visible canvas weave",
    "Classical oil impasto painting", "")
_add_style("ink-wash", "Chinese Ink Wash (Shuimo)", "Painting",
    "Chinese ink wash painting, shuimo hua, monochrome ink, rice paper texture, flowing brush strokes, traditional landscape",
    "Chinese ink wash landscape", "")
_add_style("sumi-e", "Japanese Sumi-e", "Painting",
    "Japanese sumi-e ink painting, minimalist brush strokes, negative space, zen aesthetic, bamboo and landscape motifs",
    "Japanese zen ink painting", "")
_add_style("impressionist", "Impressionist Painting", "Painting",
    "impressionist painting, Claude Monet style, visible brush strokes, broken color, light and atmosphere, plein air",
    "Monet impressionist painting", "")
_add_style("post-impressionist", "Post-Impressionist", "Painting",
    "post-impressionist painting, Van Gogh style, swirling brush strokes, emotional color, starry night aesthetic",
    "Van Gogh post-impressionist painting", "")
_add_style("cubist", "Cubist Painting", "Painting",
    "cubist painting, Pablo Picasso style, geometric fragmentation, multiple viewpoints, abstract forms, muted earth tones",
    "Picasso cubist abstract aesthetic", "")
_add_style("surrealist", "Surrealist Painting", "Painting",
    "surrealist painting, Salvador Dali style, dreamlike juxtaposition, melting forms, impossible spaces, precise detail",
    "Dali surrealist dream aesthetic", "")
_add_style("baroque", "Baroque Painting", "Painting",
    "baroque painting, Caravaggio style, dramatic chiaroscuro, intense emotion, deep shadows, religious themes, oil on canvas",
    "Caravaggio chiaroscuro painting", "")
_add_style("renaissance", "Renaissance Painting", "Painting",
    "renaissance painting, Leonardo da Vinci style, sfumato technique, balanced composition, idealized figures, oil glazing",
    "Da Vinci renaissance painting", "")
_add_style("art-nouveau", "Art Nouveau", "Painting",
    "art nouveau style, Alphonse Mucha, flowing organic lines, decorative borders, female figures, floral motifs, pastel colors",
    "Mucha decorative art nouveau aesthetic", "")
_add_style("art-deco", "Art Deco", "Painting",
    "art deco style, geometric patterns, bold symmetry, gold and black palette, 1920s luxury, industrial elegance",
    "1920s geometric luxury aesthetic", "")
_add_style("ukiyoe", "Japanese Ukiyo-e", "Painting",
    "ukiyo-e woodblock print, Hokusai style, flat color areas, bold outlines, Japanese landscapes, Great Wave aesthetic",
    "Hokusai woodblock print aesthetic", "")

# -----------------------------------------------------------------------------
# DIGITAL ART
# -----------------------------------------------------------------------------
_add_style("digital-painting", "Digital Painting", "Digital Art",
    "digital painting, ArtStation quality, concept art style, detailed brushwork, atmospheric lighting, professional illustration",
    "Concept art digital painting", "")
_add_style("matte-painting", "Matte Painting", "Digital Art",
    "matte painting, film VFX style, photorealistic environment, seamless compositing, epic scale, cinematic atmosphere",
    "VFX matte painting environment", "")
_add_style("concept-art", "Concept Art", "Digital Art",
    "concept art, production design, character turnaround, environment design, rough sketch to polished, industry standard",
    "Production concept art design", "")
_add_style("speedpaint", "Speedpaint", "Digital Art",
    "speedpaint digital art, loose brushwork, energetic strokes, unfinished quality, expressive color blocks, rapid illustration",
    "Expressive speedpaint illustration", "")

# -----------------------------------------------------------------------------
# CYBERPUNK / SCI-FI
# -----------------------------------------------------------------------------
_add_style("cyberpunk-neon", "Cyberpunk Neon", "Cyberpunk",
    "cyberpunk neon style, Blade Runner aesthetic, rain-soaked streets, holographic advertisements, neon pink and cyan, dystopian future",
    "Blade Runner neon dystopia", "")
_add_style("synthwave", "Synthwave / Retrowave", "Cyberpunk",
    "synthwave aesthetic, 80s retro-futurism, neon grid, magenta and cyan gradients, sunset background, VHS aesthetic",
    "80s retrowave grid aesthetic", "")
_add_style("vaporwave", "Vaporwave", "Cyberpunk",
    "vaporwave aesthetic, pastel pink and teal, Roman statues, palm trees, glitch art, 90s internet nostalgia, surreal",
    "Vaporwave surreal nostalgia aesthetic", "")
_add_style("scifi-hard", "Hard Sci-Fi", "Sci-Fi",
    "hard science fiction, realistic spacecraft, orbital mechanics, detailed technology, 2001 Space Odyssey aesthetic, clinical white",
    "2001 hard sci-fi clinical aesthetic", "")
_add_style("scifi-spaceship", "Spaceship Concept", "Sci-Fi",
    "spaceship concept art, detailed mechanical design, technical illustration, sci-fi vehicle, hangar environment, industrial aesthetic",
    "Spaceship concept mechanical design", "")
_add_style("post-apocalyptic", "Post-Apocalyptic", "Sci-Fi",
    "post-apocalyptic style, Mad Max aesthetic, rusted metal, desert wasteland, improvised technology, gritty survival",
    "Mad Max wasteland aesthetic", "")
_add_style("steampunk", "Steampunk", "Sci-Fi",
    "steampunk style, Victorian aesthetics, brass and copper machinery, steam engines, clockwork gears, sepia color palette",
    "Victorian steam-powered aesthetic", "")
_add_style("biopunk", "Biopunk", "Sci-Fi",
    "biopunk style, organic technology, bio-mechanical hybrids, glowing bioluminescence, flesh and machine, HR Giger influence",
    "Organic bio-mechanical aesthetic", "")

# -----------------------------------------------------------------------------
# FANTASY
# -----------------------------------------------------------------------------
_add_style("high-fantasy", "High Fantasy", "Fantasy",
    "high fantasy art, Tolkien-esque, epic landscapes, medieval castles, dragons, magic glowing effects, painterly quality",
    "Tolkien epic fantasy painting", "")
_add_style("dark-fantasy", "Dark Fantasy", "Fantasy",
    "dark fantasy art, FromSoftware aesthetic, gothic architecture, undead knights, ash and ember, muted desaturated palette",
    "Dark Souls gothic fantasy aesthetic", "")
_add_style("fairytale", "Fairy Tale Illustration", "Fantasy",
    "fairy tale illustration, storybook aesthetic, soft watercolor, whimsical creatures, enchanted forest, golden hour light",
    "Whimsical storybook fairytale art", "")
_add_style("magic-realism", "Magic Realism", "Fantasy",
    "magic realism art, grounded world with subtle magical elements, Gabriel Garcia Marquez, lush tropical settings, surreal ordinary",
    "Magical realism lush surreal aesthetic", "")

# -----------------------------------------------------------------------------
# CHINESE STYLES (Traditional & Modern)
# -----------------------------------------------------------------------------
_add_style("guofeng", "Guofeng (国风)", "Chinese Style",
    "guofeng style, Chinese traditional aesthetic, hairpin flowers, hanfu, ink elements, peach blossom, oriental elegance",
    "Chinese national style aesthetic", "")
_add_style("gongbi", "Gongbi Painting (工笔)", "Chinese Style",
    "gongbi Chinese painting, meticulous brushwork, detailed figures, mineral pigments, silk scroll, traditional court style",
    "Meticulous court painting aesthetic", "")
_add_style("xieyi", "Xieyi Painting (写意)", "Chinese Style",
    "xieyi Chinese painting, freehand brushwork, expressive strokes, spontaneous ink, philosophical landscape, traditional scholar art",
    "Freehand expressive ink aesthetic", "")
_add_style("new-chinese", "New Chinese Style", "Chinese Style",
    "new Chinese style, modern oriental aesthetic, minimalist traditional elements, bamboo and crane motifs, contemporary ink",
    "Modern oriental minimalist aesthetic", "")

# -----------------------------------------------------------------------------
# COMIC / MANGA
# -----------------------------------------------------------------------------
_add_style("manga-bw", "Black & White Manga", "Manga",
    "manga black and white, screentone shading, dynamic action lines, detailed ink work, Japanese comic style, dramatic panels",
    "B&W manga screentone aesthetic", "")
_add_style("comic-book", "American Comic Book", "Comic",
    "American comic book style, bold ink outlines, halftone dots, primary colors, dynamic poses, Marvel/DC aesthetic",
    "American comic book aesthetic", "")
_add_style("franco-belgian", "Franco-Belgian Comic", "Comic",
    "Franco-Belgian comic style, ligne claire, Herge Tintin aesthetic, flat colors, clean outlines, European adventure",
    "Tintin ligne claire aesthetic", "")
_add_style("graphic-novel", "Graphic Novel", "Comic",
    "graphic novel style, detailed sequential art, mature themes, sophisticated coloring, Watchmen aesthetic, cinematic panels",
    "Mature graphic novel aesthetic", "")
_add_style("webtoon", "Webtoon Style", "Comic",
    "webtoon style, vertical scroll format, soft gradients, glossy hair highlights, modern Korean aesthetic, digital coloring",
    "Korean webtoon digital aesthetic", "")

# -----------------------------------------------------------------------------
# RETRO / VINTAGE
# -----------------------------------------------------------------------------
_add_style("retro-80s", "80s Retro", "Retro",
    "80s retro aesthetic, neon colors, grid lines, sunset gradients, retro-futuristic, VHS glitch, Miami Vice palette",
    "80s neon retro-futurism", "")
_add_style("retro-70s", "70s Retro", "Retro",
    "70s retro aesthetic, earth tones, orange and brown palette, disco era, film grain, polaroid look, warm vintage",
    "70s earthy disco vintage", "")
_add_style("retro-50s", "50s Retro", "Retro",
    "50s retro aesthetic, pastel colors, diners and cars, rockabilly, Betty Page, kitsch Americana, vintage illustration",
    "50s Americana kitsch aesthetic", "")
_add_style("vintage-film", "Vintage Film", "Retro",
    "vintage film look, 16mm grain, light leaks, faded colors, scratch artifacts, nostalgic, analog warmth",
    "16mm vintage film aesthetic", "")
_add_style("sepia", "Sepia Tone", "Retro",
    "sepia tone photograph, antique aesthetic, brown monochrome, old west, vintage 1800s, weathered paper",
    "Antique sepia photograph aesthetic", "")

# -----------------------------------------------------------------------------
# MINIMALIST / FLAT
# -----------------------------------------------------------------------------
_add_style("flat-design", "Flat Design", "Minimalist",
    "flat design, minimal gradients, bold solid colors, simple geometric shapes, no shadows, UI illustration style",
    "Flat geometric UI illustration", "")
_add_style("material-design", "Material Design", "Minimalist",
    "material design aesthetic, Google style, subtle shadows, depth layers, vibrant colors, card-based layout",
    "Google Material Design aesthetic", "")
_add_style("line-art", "Line Art", "Minimalist",
    "line art, single weight outlines, no fills, minimalist, elegant simplicity, technical illustration, continuous line drawing",
    "Minimalist line drawing aesthetic", "")
_add_style("monochrome", "Monochrome", "Minimalist",
    "monochrome art, single color palette, dramatic shadows, high contrast, black and white, graphic impact",
    "Single-color monochrome art", "")
_add_style("duotone", "Duotone", "Minimalist",
    "duotone art, two-color gradient, cyan and magenta, graphic poster style, high contrast, modern Spotify aesthetic",
    "Two-color gradient duotone aesthetic", "")

# -----------------------------------------------------------------------------
# SPECIALTY / NOVEL
# -----------------------------------------------------------------------------
_add_style("clay-toy", "Clay Toy Style", "3D",
    "clay toy style, soft polymer clay texture,roundedhand-sculpted look, miniature figurine, soft studio lighting, adorable charm",
    "Hand-sculpted clay toy aesthetic", "")
_add_style("felt-craft", "Felt Craft Style", "Illustration",
    "felt craft style, Wool felt texture, stitched edges, handmade fabric look, cozy craft aesthetic, texture detail",
    "Felt fabric handmade aesthetic", "")
_add_style("papercraft", "Papercraft Style", "Illustration",
    "papercraft style, layered paper cutouts, drop shadows, origami aesthetic, tactile paper texture, handcrafted charm",
    "Layered paper cutout aesthetic", "")
_add_style("sticker-style", "Sticker Style", "Illustration",
    "sticker illustration, thick white outline, glossy finish, die-cut edges, kawaii aesthetic, vibrant colors, sticker pack",
    "Glossy die-cut sticker aesthetic", "")
_add_style("ufo-50", "UFO 50 Game Style", "Pixel Art",
    "UFO 50 game compilation aesthetic, retro 8-bit games, varied pixel styles,限制 color palettes, 1980s computer era",
    "Retro game compilation pixel aesthetic", "")
_add_style("psychedelic", "Psychedelic 60s", "Painting",
    "psychedelic 60s art, swirling colors, mind-expanding, trippy patterns, counterculture, vibrant neon, kaleidoscope",
    "60s psychedelic trippy aesthetic", "")
_add_style("art-brut", "Art Brut / Outsider", "Painting",
    "art brut style, raw outsider art, naive technique, primitive drawing, intense emotion, untrained aesthetic",
    "Raw naive outsider art", "")
_add_style("stained-glass", "Stained Glass", "Illustration",
    "stained glass window style, lead lines, colored glass panels, religious iconography, light shining through, gothic cathedral",
    "Stained glass cathedral aesthetic", "")
_add_style("mosaic", "Mosaic Art", "Illustration",
    "mosaic art, tesserae tiles, geometric patterns, Byzantine aesthetic, gold leaf accents, ancient Roman style",
    "Byzantine tile mosaic aesthetic", "")
_add_style("tapestry", "Medieval Tapestry", "Illustration",
    "medieval tapestry, Bayeux style, woven textile, flat figures, narrative scenes, muted earth tones, millefleur background",
    "Medieval woven tapestry aesthetic", "")
_add_style("operative", "Surgical Operative", "Realistic",
    "operative surgical aesthetic, clinical white, medical lighting, precise detail, sterile environment, surgical instruments",
    "Clinical surgical aesthetic", "")
_add_style("thermal", "Thermal Imaging", "Realistic",
    "thermal imaging camera, heat signature colors, infrared, orange-red-yellow gradient, military night vision, predator vision",
    "Infrared thermal camera aesthetic", "")
_add_style("x-ray", "X-Ray Vision", "Realistic",
    "x-ray imaging style, skeletal structure visible, translucent overlay, medical scan aesthetic, monochrome blue-white",
    "Medical x-ray scan aesthetic", "")
_add_style("ascii-art", "ASCII Art", "Digital Art",
    "ASCII art style, text characters forming image, monospace, terminal aesthetic, retro computer, green-on-black",
    "Terminal ASCII character art", "")
_add_style("glitch-art", "Glitch Art", "Digital Art",
    "glitch art style, digital corruption, pixel sorting, databend, RGB channel shift, datamosh, intentional errors",
    "Digital corruption glitch aesthetic", "")
_add_style("lowpoly", "Low Poly Vector", "Vector",
    "low poly vector art, triangulated facets, flat shaded, geometric, vibrant gradient mesh, modern minimalist",
    "Triangulated low poly vector", "")
_add_style("neon-outline", "Neon Outline", "Neon",
    "neon outline style, glowing lines, dark background, electric colors, TRON aesthetic, light cycle trails, vector glow",
    "TRON glowing vector aesthetic", "")
_add_style("holographic", "Holographic", "Neon",
    "holographic style, iridescent shimmer, rainbow gradient, chrome hologram, prismatic light refraction, futuristic",
    "Iridescent prismatic hologram aesthetic", "")
_add_style("crystal", "Crystal Style", "Illustration",
    "crystal art style, faceted gem surfaces, refractive light, prismatic color separation, geometric crystalline forms",
    "Faceted crystal prismatic aesthetic", "")
_add_style("mercury-glass", "Mercury Glass", "Illustration",
    "mercury glass style, tarnished silver surface, antique mirror, cloudy reflection spotted patina, vintage elegance",
    "Tarnished antique mirror aesthetic", "")
_add_style("watercolor-ink", "Watercolor + Ink", "Watercolor",
    "watercolor with ink outlines, mixed media, bold black lines with soft color washes, urban sketching aesthetic",
    "Ink-and-wash urban sketching aesthetic", "")
_add_style("color-pencil", "Colored Pencil", "Illustration",
    "colored pencil illustration, visible pencil texture, layered strokes, paper grain, Prismacolor aesthetic, soft blending",
    "Colored pencil paper texture aesthetic", "")
_add_style("pastel", "Soft Pastel", "Illustration",
    "soft pastel illustration, chalky texture, gentle blending, powdery pigment, dreamy quality, paper surface",
    "Chalky soft pastel aesthetic", "")
_add_style("charcoal", "Charcoal Drawing", "Illustration",
    "charcoal drawing, dramatic dark tones, smudged shading, paper texture, expressive strokes, classical life drawing",
    "Expressive charcoal sketch aesthetic", "")
_add_style("scratchboard", "Scratchboard", "Illustration",
    "scratchboard art, scratched black ink revealing white underneath, cross-hatching, high contrast, detailed linework",
    "Scratchboard crosshatch aesthetic", "")
_add_style("linocut", "Linocut Print", "Illustration",
    "linocut print style, carved block printing, bold black and white, hand-pressed texture, expressionist, rough edges",
    "Carved linocut print aesthetic", "")
_add_style("woodcut", "Woodcut Print", "Illustration",
    "woodcut print style, traditional Japanese ukiyo-e technique, bold grain patterns, hand-carved texture, ink on paper",
    "Traditional woodblock print aesthetic", "")

# -----------------------------------------------------------------------------
# LIGHTING / MOOD VARIANTS
# -----------------------------------------------------------------------------
_add_style("golden-hour", "Golden Hour", "Realistic",
    "golden hour lighting, warm sunset glow, long shadows, lens flare, amber and pink gradient sky, romantic warmth",
    "Warm sunset golden glow aesthetic", "")
_add_style("blue-hour", "Blue Hour", "Realistic",
    "blue hour lighting, twilight sky, cool blue gradient, soft city lights, calm melancholic atmosphere, post-sunset",
    "Twilight blue gradient aesthetic", "")
_add_style("night-cinema", "Night Cinema", "Realistic",
    "night cinema lighting, moody darkness, practical light sources, chiaroscuro, deep shadows, blue moonlight",
    "Moody nocturnal cinematic aesthetic", "")
_add_style("overcast", "Overcast Day", "Realistic",
    "overcast day lighting, soft diffused light, gray sky, muted colors, melancholic mood, flat even illumination",
    "Soft diffused overcast aesthetic", "")
_add_style("neon-noir", "Neon Noir", "Film Noir",
    "neon noir style, dark shadows with neon highlights, urban night, cyberpunk detective, deep contrast, blade runner mood",
    "Cyberpunk neon-detective noir aesthetic", "")
_add_style("black-noir", "Classic Film Noir", "Film Noir",
    "classic film noir, 1940s black and white, hard shadows, venetian blind light patterns, fedora silhouettes, femme fatale",
    "1940s detective noir aesthetic", "")
_add_style("muted-earth", "Muted Earth Tones", "Realistic",
    "muted earth tones, natural organic palette, terracotta and olive green, soft browns, grounding serenity, biophilic",
    "Natural earthen color aesthetic", "")
_add_style("vibrant-pop", "Vibrant Pop Colors", "Pop Art",
    "vibrant pop art colors, bold saturated palette, Roy Lichtenstein, primary colors, comic dots, graphic impact",
    "Lichtenstein pop art aesthetic", "")
_add_style("pastel-dream", "Pastel Dream", "Illustration",
    "pastel dream palette, soft pinks and lavenders, dreamlike atmosphere, gentle gradients, ethereal glow, cloud-like softness",
    "Soft pastel dreamy aesthetic", "")
_add_style("monochrome-blue", "Monochrome Blue", "Minimalist",
    "monochrome blue palette, varying shades of blue, calming aquatic feel, single hue exploration, sophisticated cool",
    "Blue monochrome aquatic aesthetic", "")
_add_style("monochrome-purple", "Monochrome Purple", "Minimalist",
    "monochrome purple palette, royal violet and lavender, regal mystic feel, single hue exploration, luxurious",
    "Purple monochrome regal aesthetic", "")
_add_style("monochrome-red", "Monochrome Red", "Minimalist",
    "monochrome red palette, crimson and scarlet, dramatic passionate feel, single hue exploration, intense emotion",
    "Red monochrome passionate aesthetic", "")
_add_style("duotone-orange-teal", "Duotone Orange-Teal", "Minimalist",
    "duotone orange and teal, Hollywood blockbuster color grade, complementary contrast, warm highlights cool shadows",
    "Blockbuster orange-teal grade aesthetic", "")
_add_style("duotone-pink-cyan", "Duotone Pink-Cyan", "Minimalist",
    "duotone pink and cyan, vaporwave neon gradient, electric complementary, retro-futuristic, cyberpunk synthwave",
    "Vaporwave pink-cyan gradient aesthetic", "")

# -----------------------------------------------------------------------------
# SPECIAL EFFECTS / STYLIZED
# -----------------------------------------------------------------------------
_add_style("bokeh", "Bokeh Photography", "Realistic",
    "bokeh photography, shallow depth of field, blurred light circles, creamy background blur, portrait lens, dreamy focus",
    "Shallow depth-of-field bokeh aesthetic", "")
_add_style("tilt-shift", "Tilt-Shift Miniature", "Realistic",
    "tilt-shift photography, miniature scene effect, selective focus, high angle, depth of field manipulation, diorama look",
    "Miniature diorama tilt-shift aesthetic", "")
_add_style("long-exposure", "Long Exposure", "Realistic",
    "long exposure photography, motion blur light trails, smooth water, cloud streaks, time compression, surreal stillness",
    "Time-compressed long-exposure aesthetic", "")
_add_style("double-exposure", "Double Exposure", "Realistic",
    "double exposure photography, two overlapping images, silhouette portraits, nature merged with face, surreal composite",
    "Surreal double-exposure composite aesthetic", "")
_add_style("hdr", "Hyperreal HDR", "Realistic",
    "hyperreal HDR photography, high dynamic range, tone-mapped, vivid details, enhanced clarity, surreal sharpness, overprocessed",
    "Tone-mapped hyperreal HDR aesthetic", "")
_add_style("bw-photo", "Black & White Photo", "Realistic",
    "black and white photography, Ansel Adams aesthetic, Zone System, rich tonal range, silver gelatin print, fine grain",
    "Ansel Adams silver gelatin aesthetic", "")

# -----------------------------------------------------------------------------
# GAME ART STYLES
# -----------------------------------------------------------------------------
_add_style("warcraft", "Warcraft Style", "3D",
    "Warcraft style, stylized fantasy, exaggerated proportions, vibrant colors, Blizzard entertainment aesthetic, hand-painted textures",
    "Blizzard stylized fantasy aesthetic", "")
_add_style("league-legends", "League of Legends", "3D",
    "League of Legends style, Riot Games, stylized champions, detailed splash art, fantasy aesthetic, vibrant magical effects",
    "Riot stylized MOBA aesthetic", "")
_add_style("genshin-impact", "Genshin Impact", "Anime",
    "Genshin Impact anime style, miHoYo, cel-shaded 3D, fantasy world, element effects, anime-influenced 3D, mobile game quality",
    "miHoYo cel-shaded fantasy aesthetic", "")
_add_style("honkai", "Honkai Star Rail", "Anime",
    "Honkai Star Rail style, miHoYo, sci-fi anime aesthetic, detailed character designs, space fantasy, mobile game quality",
    "miHoYo sci-fi anime aesthetic", "")
_add_style("overwatch", "Overwatch Style", "3D",
    "Overwatch style, Blizzard, stylized heroic proportions, diverse cast, vibrant colors, Pixar-influenced 3D, polished shaders",
    "Blizzard stylized hero aesthetic", "")
_add_style("fortnite", "Fortnite Style", "3D",
    "Fortnite style, Epic Games, exaggerated cartoon 3D, vibrant saturated colors, stylized characters, battle royale aesthetic",
    "Epic stylized cartoon aesthetic", "")

# -----------------------------------------------------------------------------
# MIXED MEDIA / CROSSOVER
# -----------------------------------------------------------------------------
_add_style("mixed-media", "Mixed Media Collage", "Digital Art",
    "mixed media collage, paper cutouts, magazine clippings, painted elements, photographs combined, textured layers, Dada influence",
    "Dada collage mixed media aesthetic", "")
_add_style("photo-montage", "Photo Montage", "Digital Art",
    "photo montage, multiple images composited, surrealist juxtaposition, seamless blending, David Hockney aesthetic, cubist photo",
    "Hockney cubist photo montage aesthetic", "")
_add_style("glitch-paint", "Glitch Painting", "Digital Art",
    "glitch painting hybrid, traditional paint textures with digital artifacts, RGB shift, datamosh brush strokes, corrupted art",
    "Hybrid digital-corruption aesthetic", "")
_add_style("3d-paint", "3D Paint Sculpeid", "3D",
    "3D paint sculpted style, virtual clay, dimensional brushwork, sculpted painting, Substance Painter aesthetic, tactile 3D",
    "Dimensional painted 3D aesthetic", "")


def count_by_category(styles: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count styles per category."""
    counts: Dict[str, int] = {}
    for s in styles:
        cat = s.get('category', 'Unknown')
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def filter_by_category(styles: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
    """Filter styles by category."""
    return [s for s in styles if s.get('category') == category]


def get_style_by_id(style_id: str) -> Optional[Dict[str, Any]]:
    """Look up a style by its unique id."""
    for s in STYLES:
        if s['id'] == style_id:
            return s
    return None


def get_categories() -> List[str]:
    """Return all unique style categories in order of first appearance."""
    seen = set()
    cats: List[str] = []
    for s in STYLES:
        c = s['category']
        if c not in seen:
            seen.add(c)
            cats.append(c)
    return cats


# Export for backward compatibility
__all__ = [
    'STYLES',
    'count_by_category',
    'filter_by_category',
    'get_style_by_id',
    'get_categories',
]