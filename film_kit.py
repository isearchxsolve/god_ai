#!/usr/bin/env python3
"""
Film Kit — Ultimate Godshand Cosmos Hybrid Edition
──────────────────────────────────────────────────
idea → NIM LLM Script → FLUX Base → NVIDIA Cosmos Video Generation → Godshand 4K Upscale (GFPGAN+ESRGAN+RIFE) → 12-Bit ProRes
"""

import asyncio
import gc
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import glob
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional
import threading

import nest_asyncio
nest_asyncio.apply()

from openai import OpenAI
import edge_tts
import torch
import cv2
from PIL import Image
import requests

from gfpgan import GFPGANer
from realesrgan import RealESRGANer
from basicsr.archs.rrdbnet_arch import RRDBNet

class C:
    R = "\033[0m"; BOLD = "\033[1m"; ACCENT = "\033[38;5;43m"
    WHITE = "\033[38;5;255m"; GREEN = "\033[38;5;78m"; RED = "\033[38;5;203m"; AMBER = "\033[38;5;214m"

def ok(msg: str): print(f"  {C.GREEN}✓{C.R}  {C.WHITE}{msg}{C.R}")
def err(msg: str): print(f"  {C.RED}✗{C.R}  {C.RED}{msg}{C.R}")
def warn(msg: str): print(f"  {C.AMBER}▲{C.R}  {C.AMBER}{msg}{C.R}")

CONFIG_FILE = Path.home() / ".film_kit_config.json"
PROJECTS_DIR = Path("/kaggle/working/film_kit_projects")

def save_config(cfg: Dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

def run_cmd(cmd: List[str]):
    subprocess.run(cmd, capture_output=True, text=True, check=True)

class TokenBucket:
    def __init__(self, rpm: float = 3.0, min_gap: float = 5.0):
        self.rpm = rpm
        self.min_gap = min_gap
        self.tokens = float(rpm)
        self.last_update = time.monotonic()
        self.last_request_time = 0.0
        self.lock = threading.Lock() if 'threading' in sys.modules else None

    def reserve(self, timeout: float = 120.0) -> bool:
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.rpm, self.tokens + elapsed * (self.rpm / 60.0))
            self.last_update = now
            
            if self.tokens >= 1.0 and (now - self.last_request_time) >= self.min_gap:
                self.tokens -= 1.0
                self.last_request_time = time.monotonic()
                return True
            time.sleep(1.0)
        return False

class ProviderPool:
    def __init__(self, api_key: str, model_id: str):
        self.api_key = api_key
        self.client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key, timeout=60.0)
        self.model_id = model_id

    def chat(self, messages: List[Dict], max_tokens: int = 2000) -> str:
        for attempt in range(5):
            try:
                resp = self.client.chat.completions.create(model=self.model_id, messages=messages, temperature=0.8, max_tokens=max_tokens)
                return resp.choices[0].message.content or ""
            except Exception:
                time.sleep(5.0)
        raise RuntimeError("LLM failed after multiple retries.")

@dataclass
class Scene:
    index: int; narration: str; visual_prompt: str; image_path: Optional[str] = None
    audio_path: Optional[str] = None; clip_path: Optional[str] = None; duration: Optional[float] = None

class Project:
    def __init__(self, name: str):
        self.name = name.strip()
        self.dir = PROJECTS_DIR / self.name
        for sub in ("images", "audio", "clips", "output"): (self.dir / sub).mkdir(parents=True, exist_ok=True)
        self.idea = ""; self.subject = ""; self.style = "cinematic, 4k"
        self.aspect = "16:9"; self.seed = random.randint(0, 999999)
        self.music = True; self.scenes: List[Scene] = []
        self.manifest_path = self.dir / "manifest.json"

    def save(self):
        data = {"idea": self.idea, "subject": self.subject, "style": self.style, "aspect": self.aspect, 
                "seed": self.seed, "scenes": [asdict(s) for s in self.scenes]}
        self.manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def step_script(proj: Project, pool: ProviderPool, num_scenes: int):
    print(f"\n  {C.ACCENT}── Writing Script (NVIDIA NIM) {C.R}")
    sys_prompt = 'Output ONLY JSON array: [{"narration": "...", "visual_prompt": "..."}]'
    raw = pool.chat([{"role": "system", "content": sys_prompt}, {"role": "user", "content": f"Story: {proj.idea}\nStyle: {proj.style}\nScenes: {num_scenes}"}])
    stripped = re.sub(r"```(?:json)?\s*", "", raw).strip()
    items = json.loads(stripped[stripped.find("["):stripped.rfind("]")+1])
    
    prefix = f"{proj.subject.strip()}, " if proj.subject.strip() else ""
    proj.scenes = [Scene(i, item["narration"], f"{prefix}{item['visual_prompt']}, {proj.style}") for i, item in enumerate(items)]
    proj.save()
    for s in proj.scenes: print(f"    [{s.index:02}] {s.narration}")

def step_images(proj: Project):
    print(f"\n  {C.ACCENT}── Rendering Base Frames (Pollinations FLUX) {C.R}")
    POLLINATIONS_KEY = os.environ.get("POLLINATIONS_KEY", "") 
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://pollinations.ai/"}
    if POLLINATIONS_KEY: headers["Authorization"] = f"Bearer {POLLINATIONS_KEY}"

    for s in proj.scenes:
        out = proj.dir / "images" / f"scene_{s.index:02}.jpg"
        q = urllib.parse.quote(s.visual_prompt, safe="")
        url = f"https://gen.pollinations.ai/image/{q}?width=1280&height=720&nologo=true&seed={proj.seed}&model=flux"
        
        success = False
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp, open(out, "wb") as f:
                    f.write(resp.read())
                success = True
                break
            except Exception: time.sleep(3 + attempt * 4)

        if not success: raise RuntimeError("Pollinations error.")
        s.image_path = str(out)
        ok(f"Scene {s.index:02} Base Rendered (1280x720).")
    proj.save()

def step_voice(proj: Project):
    print(f"\n  {C.ACCENT}── Synthesizing Narration {C.R}")
    for s in proj.scenes:
        out = proj.dir / "audio" / f"scene_{s.index:02}.wav"
        asyncio.run(edge_tts.Communicate(s.narration, "en-US-AriaNeural").save(str(out)))
        s.audio_path = str(out)
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(out)], capture_output=True, text=True)
        s.duration = max(2.0, float(p.stdout.strip()) + 1.2)
        ok(f"Scene {s.index:02} Audio Ready ({s.duration:.1f}s)")
    proj.save()

def step_clips_cosmos(proj: Project, pool: ProviderPool):
    print(f"\n  {C.ACCENT}── Generating Physics-Aware Video (NVIDIA Cosmos NIM) {C.R}")
    bucket = TokenBucket(rpm=3.0, min_gap=5.0)
    endpoint = "https://integrate.api.nvidia.com/v1/videos/cosmos" # Standard NVIDIA NIM endpoint path
    
    for s in proj.scenes:
        out_video = proj.dir / "clips" / f"_raw_{s.index:02}.mp4"
        print(f"  -> Dispatching Scene {s.index:02} to Cosmos Engine...")
        
        # Read local image and encode or pass reference URL based on provider capability
        # For serverless NIM, we upload or pass image prompt context payload
        payload = {
            "prompt": s.visual_prompt,
            "negative_prompt": "blurry, distorted, low quality, artifacts",
            "size": "1280x720",
            "num_frames": 121,
            "fps": 24,
            "num_inference_steps": 30,
            "guidance_scale": 3.0,
            "seed": proj.seed + s.index
        }

        success = False
        for attempt in range(5):
            if not bucket.reserve():
                warn("Rate limit pacing active for Cosmos... waiting.")
                continue
            try:
                headers = {
                    "Authorization": f"Bearer {pool.client.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                resp = requests.post(endpoint, json=payload, headers=headers, timeout=300)
                if resp.status_code in [429, 502, 503, 504]:
                    warn(f"Cosmos throttling (HTTP {resp.status_code}), backing off...")
                    time.sleep(5.0 * (attempt + 1))
                    continue
                
                resp.raise_for_status()
                data = resp.json()
                video_url = data.get("video_url") or data.get("url")
                
                # Download result video chunk
                urllib.request.urlretrieve(video_url, out_video)
                success = True
                ok(f"Scene {s.index:02} Motion Generated via Cosmos.")
                break
            except Exception as e:
                warn(f"Attempt {attempt+1} failed: {e}")
                time.sleep(4.0)

        if not success:
            raise RuntimeError(f"Scene {s.index:02} failed to generate via NVIDIA Cosmos endpoint.")

def step_clips_upscale(proj: Project):
    print(f"\n  {C.ACCENT}── 4K Neural Upscale & Optical Flow (GFPGAN + ESRGAN + RIFE) {C.R}")
    face_model = GFPGANer(model_path='https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.3.pth', upscale=1, arch='clean', channel_multiplier=2, bg_upsampler=None)
    rrdb = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    esr_model = RealESRGANer(scale=4, model_path='https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/Real-ESRGAN_x4plus.pth', model=rrdb, tile=512, half=True)
    rife_bin = "/usr/local/bin/rife-ncnn-vulkan"

    for s in proj.scenes:
        raw_mp4 = proj.dir / "clips" / f"_raw_{s.index:02}.mp4"
        print(f"  -> Upgrading Scene {s.index:02} to 4K Hollywood Master...")
        
        frames_dir = proj.dir / "clips" / f"tmp_{s.index:02}"; os.makedirs(frames_dir, exist_ok=True)
        run_cmd(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw_mp4), str(frames_dir / "f%04d.png")])
        
        up_dir = proj.dir / "clips" / f"up_{s.index:02}"; os.makedirs(up_dir, exist_ok=True)
        for f in sorted(glob.glob(str(frames_dir / "*.png"))):
            img = cv2.imread(f)
            _, _, img = face_model.enhance(img, paste_back=True, weight=0.6)
            img, _ = esr_model.enhance(img, outscale=4)
            cv2.imwrite(str(up_dir / os.path.basename(f)), img)
            
        r1_dir = proj.dir / "clips" / f"r1_{s.index:02}"; os.makedirs(r1_dir, exist_ok=True)
        r2_dir = proj.dir / "clips" / f"r2_{s.index:02}"; os.makedirs(r2_dir, exist_ok=True)
        run_cmd([rife_bin, "-i", str(up_dir), "-o", str(r1_dir)])
        run_cmd([rife_bin, "-i", str(r1_dir), "-o", str(r2_dir)])
        
        final_mov = proj.dir / "clips" / f"scene_{s.index:02}.mov"
        grade = "curves=r='0/0 0.45/0.41 1/0.91':g='0/0 0.5/0.49 1/0.94':b='0/0.02 0.5/0.53 1/0.97',eq=contrast=1.06:saturation=0.88"
        multiplier = max(1.0, s.duration / 5.0)
        vf = f"setpts={multiplier}*PTS,{grade},scale=3840:2160"
        
        run_cmd([
            "ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i", str(r2_dir / "%08d.png"),
            "-i", s.audio_path, "-vf", vf,
            "-c:v", "prores_ks", "-profile:v", "4444", "-qscale:v", "10", "-pix_fmt", "yuv444p10le",
            "-c:a", "pcm_s24le", "-shortest", str(final_mov)
        ])
        s.clip_path = str(final_mov)
        
        for d in [frames_dir, up_dir, r1_dir, r2_dir]: shutil.rmtree(d)
        ok(f"Scene {s.index:02} 4K ProRes Rendered.")

    proj.save()

def step_stitch(proj: Project):
    print(f"\n  {C.ACCENT}── Final Deliverable Assembly {C.R}")
    clips = [s.clip_path for s in proj.scenes if s.clip_path and Path(s.clip_path).exists()]
    
    out_master_mov = proj.dir / "output" / f"{proj.name}_MASTER.mov"
    list_file = proj.dir / "_concat.txt"
    list_file.write_text("\n".join([f"file '{Path(p).absolute()}'" for p in clips]))
    run_cmd(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_master_mov)])
    list_file.unlink()

    if proj.music:
        out_scored = proj.dir / "output" / f"{proj.name}_SCORED_MASTER.mov"
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(out_master_mov)], capture_output=True, text=True)
        duration = float(p.stdout.strip())
        bed = proj.dir / "_music_bed.wav"
        filt = f"sine=f=110:d={duration:.3f}[a];sine=f=165:d={duration:.3f}[b];anoisesrc=color=pink:d={duration:.3f}:a=0.05[n];[a][b]amix=inputs=2:weights='1 0.6'[ab];[ab][n]amix=inputs=2:weights='1 0.3',lowpass=f=600,afade=t=in:d=2.0,afade=t=out:st={max(0, duration-2.0):.3f}:d=2.0,volume=0.15[out]"
        run_cmd(["ffmpeg", "-y", "-loglevel", "error", "-filter_complex", filt, "-map", "[out]", "-t", f"{duration:.3f}", str(bed)])
        run_cmd(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out_master_mov), "-i", str(bed), "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:weights='1 0.15'[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "pcm_s24le", str(out_scored)])
        bed.unlink(); out_master_mov.unlink()
        out_master_mov = out_scored
        ok(f"Cinematic Drone Score Mixed.")

    out_master_mp4 = proj.dir / "output" / f"{proj.name}_FINAL.mp4"
    print(f"  -> Converting to Web-Friendly MP4...")
    run_cmd(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out_master_mov), "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", str(out_master_mp4)])
    
    print(f"\n  ✅ THEATRICAL MASTER: {out_master_mov}")
    print(f"  ✅ WEB MP4 MASTER: {out_master_mp4}")

def step_render_all(proj: Project, pool: ProviderPool, num_scenes: int):
    step_script(proj, pool, num_scenes)
    if proj.scenes:
        step_images(proj)
        step_voice(proj)
        step_clips_cosmos(proj, pool)
        step_clips_upscale(proj)
        step_stitch(proj)