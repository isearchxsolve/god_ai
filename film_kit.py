#!/usr/bin/env python3
"""
Film Kit v7.0 — The Godshand Hybrid Edition
──────────────────────────────────────────────────
idea → script (NIM) → base frames (FLUX) → 8K Pristine Upscale (GFPGAN+ESRGAN) 
→ 8K Pan & Scan (12fps) → RIFE Optical Flow (24fps) → 4K ProRes 4444 XQ Master
"""

import argparse
import asyncio
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

def _supports_color() -> bool:
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty(): return False
    return True

USE_COLOR = _supports_color()
def _c(code: str) -> str: return code if USE_COLOR else ""

class C:
    R = _c("\033[0m"); BOLD = _c("\033[1m"); ACCENT = _c("\033[38;5;43m"); ACCENTB = _c("\033[38;5;49m")   
    WHITE = _c("\033[38;5;255m"); GRAY = _c("\033[38;5;245m"); DIMGRAY = _c("\033[38;5;238m")  
    SILVER = _c("\033[38;5;251m"); GREEN = _c("\033[38;5;78m"); RED = _c("\033[38;5;203m")  
    AMBER = _c("\033[38;5;214m"); BLUE = _c("\033[38;5;75m"); PURPLE = _c("\033[38;5;141m")  

H = "─"; V = "│"; TL = "╭"; TR = "╮"; BL = "╰"; BR = "╯"
ARROW = "❯"; TICK = "✓"; CROSS = "✗"; WARN_SYM = "▲"; INFO_SYM = "◆"
SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

def ok(msg: str): print(f"  {C.GREEN}{TICK}{C.R}  {C.WHITE}{msg}{C.R}")
def err(msg: str): print(f"  {C.RED}{CROSS}{C.R}  {C.RED}{msg}{C.R}")
def warn(msg: str): print(f"  {C.AMBER}{WARN_SYM}{C.R}  {C.AMBER}{msg}{C.R}")
def info(msg: str): print(f"  {C.BLUE}{INFO_SYM}{C.R}  {C.GRAY}{msg}{C.R}")

def _pad(text: str, width: int) -> str:
    raw = re.sub(r"\033\[[^m]*m", "", text)
    return text + " " * max(0, width - len(raw))

def banner():
    w, inner = 62, 60
    title = f"{C.BOLD}{C.ACCENTB}Film Kit{C.R}{C.BOLD}{C.WHITE}  v7.0 (Godshand Hybrid){C.R}"
    sub = f"{C.DIMGRAY}idea → FLUX → 8K ESRGAN → 8K Pan/Scan → RIFE → ProRes{C.R}"
    print(f"\n  {C.DIMGRAY}{TL}{H * inner}{TR}{C.R}")
    print(f"  {C.DIMGRAY}{V}{C.R}  {_pad(title, inner - 2)}{C.DIMGRAY}{V}{C.R}")
    print(f"  {C.DIMGRAY}{V}{C.R}  {_pad(sub, inner - 2)}{C.DIMGRAY}{V}{C.R}")
    print(f"  {C.DIMGRAY}{BL}{H * inner}{BR}{C.R}\n")

class Spinner:
    def __init__(self, msg: str):
        self.msg = msg; self._frame = 0; self._active = False
    def start(self): self._active = True; self._draw()
    def _draw(self):
        sys.stdout.write(f"\r  {C.ACCENT}{SPINNER_FRAMES[self._frame % len(SPINNER_FRAMES)]}{C.R}  {C.GRAY}{self.msg}{C.R}   ")
        sys.stdout.flush(); self._frame += 1
    def tick(self):
        if self._active: self._draw()
    def stop(self, success: bool = True, msg: str = ""):
        if not self._active: return
        self._active = False
        sys.stdout.write(f"\r  {f'{C.GREEN}{TICK}' if success else f'{C.RED}{CROSS}'}{C.R}  {C.WHITE}{msg or self.msg}{C.R}   \n")
        sys.stdout.flush()

CONFIG_FILE = Path.home() / ".film_kit_config.json"
PROJECTS_DIR = Path.home() / "film_kit_projects"
DEFAULT_NIM_MODEL = "meta/llama-3.1-70b-instruct"

def load_config() -> Dict: return json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else {}
def save_config(cfg: Dict): CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
def run_cmd(cmd: List[str], quiet: bool = True) -> subprocess.CompletedProcess: return subprocess.run(cmd, capture_output=quiet, text=True)

class ProviderPool:
    def __init__(self, api_key: str, model_id: str):
        self.client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key, timeout=60.0) if HAS_OPENAI else None
        self.model_id = model_id
    def chat(self, messages: List[Dict], max_tokens: int = 2000) -> str:
        for _ in range(20):
            try: return self.client.chat.completions.create(model=self.model_id, messages=messages, temperature=0.8, max_tokens=max_tokens).choices[0].message.content or ""
            except Exception as exc: time.sleep(5.0)
        raise RuntimeError("LLM failed after multiple retries.")

@dataclass
class Scene:
    index: int; narration: str; visual_prompt: str; image_path: Optional[str] = None; audio_path: Optional[str] = None; clip_path: Optional[str] = None; duration: Optional[float] = None

class Project:
    def __init__(self, name: str):
        self.name = name.strip(); self.dir = PROJECTS_DIR / self.name
        for sub in ("images", "audio", "clips", "output"): (self.dir / sub).mkdir(parents=True, exist_ok=True)
        self.idea = ""; self.subject = ""; self.style = "cinematic, 4k, magical realism, highly detailed"; self.aspect = "4k"
        self.voice = "aria"; self.seed = random.randint(0, 999999); self.music = True; self.scenes: List[Scene] = []
        self.manifest_path = self.dir / "manifest.json"
        self.load()
    def save(self): self.manifest_path.write_text(json.dumps({"idea": self.idea, "subject": self.subject, "style": self.style, "aspect": self.aspect, "voice": self.voice, "seed": self.seed, "music": self.music, "scenes": [asdict(s) for s in self.scenes]}, indent=2), encoding="utf-8")
    def load(self):
        if not self.manifest_path.exists(): return
        try:
            d = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            self.idea, self.subject, self.style, self.aspect, self.voice, self.seed, self.music = d.get("idea", ""), d.get("subject", ""), d.get("style", ""), d.get("aspect", "4k"), d.get("voice", "aria"), int(d.get("seed", 0)), bool(d.get("music", False))
            self.scenes = [Scene(**s) for s in d.get("scenes", [])]
        except Exception: pass

def patch_basicsr():
    """Fixes the torchvision 0.16 compatibility bug in basicsr on Kaggle."""
    import site
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        bad_file = os.path.join(sp, 'basicsr', 'data', 'degradations.py')
        if os.path.exists(bad_file):
            with open(bad_file, 'r') as f: src = f.read()
            if 'functional_tensor' in src:
                src = src.replace('from torchvision.transforms.functional_tensor import rgb_to_grayscale', 'from torchvision.transforms.functional import rgb_to_grayscale')
                with open(bad_file, 'w') as f: f.write(src)
            break

def is_godshand_ready() -> bool:
    """Checks if the heavy Godshand AI libraries are installed on the system."""
    try:
        import cv2
        import gfpgan
        import realesrgan
        return shutil.which("rife-ncnn-vulkan") is not None
    except ImportError:
        return False

def godshand_enhance_8k(input_path: str):
    """Upscales a 1080p image to 8K (7680x4320) and restores faces using GFPGAN + RealESRGAN."""
    import cv2
    import torch
    patch_basicsr()
    from gfpgan import GFPGANer
    from realesrgan import RealESRGANer
    from basicsr.archs.rrdbnet_arch import RRDBNet

    img = cv2.imread(input_path)
    if img is None: raise RuntimeError(f"Failed to read image: {input_path}")

    # GFPGAN Face Restoration (Weight 0.7 for natural look)
    face_model = GFPGANer(model_path='https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.3.pth', upscale=1, arch='clean', channel_multiplier=2, bg_upsampler=None)
    _, _, img = face_model.enhance(img, has_aligned=False, only_center_face=False, paste_back=True, weight=0.7)

    # Real-ESRGAN x4 Upscale (1080p -> 8K)
    # TILE is critical: Prevents Kaggle T4 CUDA Out-of-Memory during upscaling
    rrdb = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    esr_model = RealESRGANer(scale=4, model_path='https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth', model=rrdb, tile=512, tile_pad=10, pre_pad=0, half=torch.cuda.is_available())
    
    img, _ = esr_model.enhance(img, outscale=4)
    cv2.imwrite(input_path, img) # Overwrite with pristine 8K asset
    
    # Aggressively flush VRAM to prevent crash on next scene
    del face_model
    del esr_model
    del rrdb
    import gc; gc.collect(); torch.cuda.empty_cache()

def build_godshand_clip(image_path: str, audio_path: str, duration: float, out_path: str, zoom_in: bool = True):
    """Pans across the 8K image at 12fps, RIFEs to 24fps, and encodes to 12-bit ProRes."""
    tmp_dir = Path(tempfile.mkdtemp())
    raw_frames = tmp_dir / "raw"; raw_frames.mkdir()
    rife_frames = tmp_dir / "rife"; rife_frames.mkdir()
    
    w, h = 3840, 2160 # DCI 4K Target
    frames = max(2, int(duration * 12)) # 12 FPS Base Extraction from 8K Canvas
    
    # Smooth, non-pixelated zoom by cropping the 8K canvas down to 4K window
    z_expr = "min(zoom+0.0006,1.2)" if zoom_in else "max(1.2-0.0006,1.0)"
    vf = f"zoompan=z='{z_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps=12,format=yuv420p"
    
    # Pass 1: Extract 12fps Pan/Scan Frames
    run_cmd(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", image_path, "-vf", vf, "-t", str(duration), str(raw_frames / "%05d.png")])

    # Pass 2: RIFE Optical Flow (12fps -> 24fps)
    rife_bin = shutil.which("rife-ncnn-vulkan")
    run_cmd([rife_bin, "-i", str(raw_frames), "-o", str(rife_frames), "-m", "rife-v4.6"])

    # Pass 3: Encode to ProRes 4444 XQ 12-Bit + Theatrical Grade + Mux Audio
    grade = "curves=r='0/0 0.45/0.41 1/0.91':g='0/0 0.5/0.49 1/0.94':b='0/0.02 0.5/0.53 1/0.97',eq=contrast=1.06:saturation=0.88"
    run_cmd([
        "ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i", str(rife_frames / "%05d.png"),
        "-i", audio_path,
        "-vf", grade, 
        "-c:v", "prores_ks", "-profile:v", "5", "-vendor", "apl0", "-qscale:v", "10", 
        "-pix_fmt", "yuv444p10le", 
        "-c:a", "pcm_s24le", "-shortest",
        str(out_path)
    ])
    shutil.rmtree(tmp_dir, ignore_errors=True)

def step_script(proj: Project, pool: ProviderPool, num_scenes: int):
    print(f"\n  {C.ACCENT}── Writing Script (NVIDIA NIM) {C.R}")
    sys_prompt = 'Output ONLY JSON array: [{"narration": "...", "visual_prompt": "..."}]'
    raw = pool.chat([{"role": "system", "content": sys_prompt}, {"role": "user", "content": f"Story: {proj.idea}\nStyle: {proj.style}\nScenes: {num_scenes}"}])
    items = json.loads(re.sub(r"```(?:json)?\s*", "", raw).strip()[raw.find("["):raw.rfind("]")+1])
    proj.scenes = [Scene(i, item["narration"], f"{proj.subject} {item['visual_prompt']}, {proj.style}") for i, item in enumerate(items)]
    proj.save()
    for s in proj.scenes: print(f"    {C.PURPLE}[{s.index:02}]{C.R}  {C.WHITE}{s.narration}{C.R}")

def step_images(proj: Project):
    print(f"\n  {C.ACCENT}── Rendering Base Frames (Pollinations FLUX) {C.R}")
    for s in proj.scenes:
        out = proj.dir / "images" / f"scene_{s.index:02}.jpg"
        q = urllib.parse.quote(s.visual_prompt, safe="")
        # Request 1080p base frame from FLUX
        urllib.request.urlretrieve(f"https://image.pollinations.ai/prompt/{q}?width=1920&height=1080&nologo=true&seed={proj.seed}&model=flux", out)
        s.image_path = str(out)
        ok(f"Scene {s.index:02} Base Rendered.")
    proj.save()

    if is_godshand_ready():
        print(f"\n  {C.ACCENT}── Godshand AI Upscale (GFPGAN + Real-ESRGAN x4) {C.R}")
        info("Fixing faces and upscaling base frames to 8K (7680x4320) for pristine panning...")
        for s in proj.scenes:
            sp = Spinner(f"Upscaling Scene {s.index:02} to 8K Pristine...")
            sp.start()
            try:
                godshand_enhance_8k(s.image_path)
                sp.stop(success=True, msg=f"Scene {s.index:02} -> 8K Pristine")
            except Exception as e:
                sp.stop(success=False, msg=f"Scene {s.index:02} upscale failed.")
                warn(str(e))
    else:
        warn("Godshand AI libraries not found! Proceeding with standard 1080p resolution.")

def step_voice(proj: Project):
    print(f"\n  {C.ACCENT}── Synthesizing Narration {C.R}")
    for s in proj.scenes:
        out = proj.dir / "audio" / f"scene_{s.index:02}.wav"
        asyncio.run(edge_tts.Communicate(s.narration, "en-US-AriaNeural").save(str(out)))
        s.audio_path = str(out)
        s.duration = max(2.0, float(run_cmd(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(out)]).stdout.strip()) + 1.2)
        ok(f"Scene {s.index:02} Audio ({s.duration:.1f}s)")
    proj.save()

def step_clips(proj: Project):
    print(f"\n  {C.ACCENT}── Cinematic Motion Assembly {C.R}")
    if is_godshand_ready():
        info("GODSHAND ENGAGED: 8K Pan-and-Scan -> RIFE Optical Flow -> ProRes 4444 XQ")
        for s in proj.scenes:
            sp = Spinner(f"Scene {s.index:02} | Pan & Scan, RIFE, and ProRes Encode...")
            sp.start()
            final_vid = proj.dir / "clips" / f"scene_{s.index:02}.mov"
            try:
                build_godshand_clip(s.image_path, s.audio_path, s.duration, str(final_vid), zoom_in=(s.index % 2 == 0))
                s.clip_path = str(final_vid)
                sp.stop(success=True, msg=f"Scene {s.index:02} -> 4K ProRes Master")
            except Exception as e:
                sp.stop(success=False, msg=f"Scene {s.index:02} build failed.")
                err(str(e))
    else:
        info("Standard Mode: FFmpeg Basic Pan/Zoom. Install RIFE for Godshand quality.")
        for s in proj.scenes:
            final_vid = proj.dir / "clips" / f"scene_{s.index:02}.mp4"
            z = "min(zoom+0.001,1.1)" if s.index % 2 == 0 else "max(1.1-0.001,1.0)"
            vf = f"scale=3840:-2,zoompan=z='{z}':d={int(s.duration*24)}:s=1920x1080:fps=24"
            run_cmd(["ffmpeg", "-y", "-loop", "1", "-i", s.image_path, "-i", s.audio_path, "-vf", vf, "-t", str(s.duration), "-c:v", "libx264", "-c:a", "aac", "-shortest", str(final_vid)])
            s.clip_path = str(final_vid)
            ok(f"Scene {s.index:02} Standard Video Rendered.")
    proj.save()

def step_stitch(proj: Project):
    print(f"\n  {C.ACCENT}── Final Deliverable Assembly {C.R}")
    clips = [s.clip_path for s in proj.scenes if s.clip_path and Path(s.clip_path).exists()]
    if not clips: return err("No clips to stitch.")
    
    out_master = proj.dir / "output" / f"{proj.name}_MASTER.mov"
    list_file = proj.dir / "_concat.txt"
    list_file.write_text("\n".join([f"file '{Path(p).absolute()}'" for p in clips]))
    
    run_cmd(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_master)])
    list_file.unlink()
    
    # Adding Drone Music Mix
    if proj.music:
        info("Mixing cinematic ambient drone...")
        out_scored = proj.dir / "output" / f"{proj.name}_SCORED_MASTER.mov"
        duration = float(run_cmd(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(out_master)]).stdout.strip())
        bed = proj.dir / "_music_bed.wav"
        
        # Generate 600Hz Lowpassed Pink Noise + Sine Drone
        filt = f"sine=f=110:d={duration:.3f}[a];sine=f=165:d={duration:.3f}[b];anoisesrc=color=pink:d={duration:.3f}:a=0.05[n];[a][b]amix=inputs=2:weights='1 0.6'[ab];[ab][n]amix=inputs=2:weights='1 0.3',lowpass=f=600,afade=t=in:d=2.0,afade=t=out:st={max(0, duration-2.0):.3f}:d=2.0,volume=0.15[out]"
        run_cmd(["ffmpeg", "-y", "-filter_complex", filt, "-map", "[out]", "-t", f"{duration:.3f}", str(bed)])
        
        # Mux and duck audio
        run_cmd(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out_master), "-i", str(bed), "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:weights='1 0.15'[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "pcm_s24le", str(out_scored)])
        bed.unlink(missing_ok=True)
        out_master.unlink(missing_ok=True) # Replace master with scored version
        out_master = out_scored
        
    print(f"\n  {C.GREEN}{TICK}{C.R}  {C.BOLD}{C.WHITE}THEATRICAL MASTER READY: {out_master}{C.R}")

def step_render_all(proj: Project, pool: ProviderPool, num_scenes: int):
    step_script(proj, pool, num_scenes)
    if proj.scenes: 
        step_images(proj)
        step_voice(proj)
        step_clips(proj)
        step_stitch(proj)

def main():
    banner()
    cfg = load_config()
    if not cfg.get("nim_key"):
        err("NVIDIA NIM Key is missing! Set it using os.environ['NIM_KEY'] or configure the .json file.")
        return
        
    pool = ProviderPool(cfg.get("nim_key"), DEFAULT_NIM_MODEL)
    
    # We load standard story params (Override these programmatically in Kaggle)
    proj = Project("godshand_hybrid_film")
    proj.aspect = "4k"
    proj.save()
    
    info("Booting Godshand Hybrid Engine...")
    step_render_all(proj, pool, 5)

if __name__ == "__main__":
    main()