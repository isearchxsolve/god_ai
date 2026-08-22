# MASTER_WORKLOG - OiiOii Studio Pipeline

Non-volatile state log. **Append-only. Never batch.** If the session dies, the next
agent reads this file bottom-up, finds the last `STATUS:` line, and resumes there.

Encoding: **UTF-8, LF**. Do not let an editor rewrite this as UTF-16; a mixed-encoding
recovery log is worse than none. Appends from code go through
`RunStore.worklog()` which always writes UTF-8.

Format per entry:

```
## [<ISO timestamp>] STAGE <n> - <name>
STATUS: NOT_STARTED | IN_PROGRESS | DONE | BLOCKED
FILES: <paths touched>
FACTS: <verified facts, one per line>
NEXT: <the exact next action>
```

---

## [2026-08-22T01:30+05:30] STAGE 0 - Environment & OmniRoute probe
STATUS: DONE
FILES: (read-only reconnaissance)
FACTS:
- Repo root is `C:/god_ai/oioi` (git). Working dir for this task is `C:/god_ai/oioi/oioi`
  (a nested project dir tracked under the `oioi/` prefix in git). Both contain a
  `backend/agent_pipeline.py`; the LIVE one is `oioi/backend/agent_pipeline.py`
  (7536 bytes, touched by commit aed509cc). The copy at `<repo>/backend/` (11764 bytes)
  is a stale duplicate - DO NOT EDIT IT.
- Branch: `neon/20260803-212543`. HEAD: 43a6e841 ("fuck"). Prior: aed509cc.
- OmniRoute runs as node.exe PID 3828, listening 0.0.0.0:20128 (+127.0.0.1:20131, :20132).
- OmniRoute CHAT IS HEALTHY:
  `POST /v1/chat/completions {"model":"frontier","stream":false}` -> HTTP 200 in ~10.4s.
  Served by upstream model `nvidia/nemotron-3-super-120b-a12b`. Returns a
  `reasoning_content` field alongside `content` - parsers must read `content` only.
  NOTE: latency is ~10s for a trivial prompt. Long generations need generous timeouts
  (>=300s) and MUST NOT be run with the default httpx 5s/30s timeouts.
- OmniRoute VIDEO IS **NOT** HEALTHY / DOES NOT EXIST:
  - `POST /v1/videos`             -> HTTP 404 `{"code":"unknown_route"}`
  - `POST /v1/videos/generations` -> HTTP 000 (TCP accepted, no HTTP response, hangs >20s)
  - `POST /v1/video/generations`  -> HTTP 000 (same hang)
  - `POST /v1/images/generations` -> HTTP 401 "A valid API key is required. Get one at
    https://enter.pollinations.ai/keys" (Pollinations key not configured in OmniRoute)
  - `GET /v1/models`              -> HTTP 000, hangs (timed out at 45s). Do not depend on it.
- ffmpeg/ffprobe 9.0-full_build ARE on PATH (Gyan build, winget). Concat + filtergraph OK.
- Python 3.11.9 at `oioi/.venv/Scripts/python.exe`.
- `oioi/backend/app/api/v1/endpoints/videos.py` returns a FABRICATED fallback URL
  (`https://cdn.pollinations.ai/video/clip_*.mp4`) that does not exist. Not a usable source.
- `oioi/backend/providers/pollinations.py::generate_video` raises NotImplementedError.
  Pollinations image URLs (`https://image.pollinations.ai/prompt/...`) work keylessly.
NEXT: Build the event-driven state machine. Video generation must be behind a pluggable
provider with a live health probe so the pipeline degrades to ffmpeg Ken-Burns clip
synthesis (real MP4s, real durations) instead of emitting dead URLs.

---

## [2026-08-22T01:52+05:30] STAGE 1 - Foundations: events, store, OmniRoute client, media
STATUS: DONE (code written; media layer NOT YET VERIFIED - see STAGE 2)
FILES: oioi/backend/studio_pipeline/{__init__,events,store,omniroute,media}.py
FACTS:
- New package `backend/studio_pipeline/` (name chosen to avoid colliding with the
  existing `app.api.v1.endpoints.pipeline` module).
- events.py: PipelineStage enum (QUEUED -> SCRIPTWRITING -> AWAITING_APPROVAL ->
  ART_DIRECTION -> SCENE_DESIGN -> ANIMATION -> SOUND_DESIGN -> DIRECTING ->
  COMPLETED|FAILED|CANCELLED), EventType enum, and EventBus with per-subscriber bounded
  queues. Every event has a monotonic `seq`; subscribe(from_seq=N) replays from
  journal.jsonl then switches to the live queue, deduping on seq. Slow subscribers get a
  GAP event; publishing never blocks the render.
- store.py: RunStore = the non-volatile RAM. Per-run dir under
  backend/storage/runs/<run_id>/ with state.json (atomic os.replace), journal.jsonl
  (append + fsync per event), WORKLOG.md, bible.json, script/act_NNN.json,
  scenes/scene_NNNNN.json, characters/, clips/, audio/, final/.
  `iter_scenes()` is a generator -> the Animator never materialises 500-1000 scenes.
  `worklog()` appends to BOTH the run log and MASTER_WORKLOG.md, flushed+fsynced per
  call (never batched), per mandate.
- omniroute.py: OmniRouteClient. Single pooled httpx.AsyncClient (hundreds of calls per
  render would exhaust Windows ephemeral ports otherwise). 300s default read timeout.
  Retries only on transport errors + 429/5xx; other 4xx fail fast. Reads `content` and
  explicitly ignores `reasoning_content`. `chat_json()` does fence-stripping /
  outermost-brace slicing / trailing-comma repair, and on failure feeds the bad output
  back to the model for a repair round-trip. `probe_video()` walks candidate routes with
  an 8s timeout and CACHES the verdict, so the known hanging route costs 8s once, not
  8s x 600 scenes.
- media.py: real ffmpeg work. Uniform render profile (1280x720@24, yuv420p, AAC 44.1k
  stereo) so the Director can stream-copy instead of re-encoding 3 hours.
  synthesize_kenburns_clip() renders a genuine MP4 from a Pollinations still using a
  zoompan filtergraph driven by the storyboard's camera move (zoom in/out, pan L/R,
  tilt U/D, static), with fades and a silent stereo track. synthesize_music_bed()
  procedurally builds an ambient score (detuned root+fifth+octave drone, tremolo at
  tempo, lowpass, aecho) - there is no keyless music API here, so it synthesises rather
  than link a track that does not exist. mix_final_audio() ducks music under narration
  via sidechaincompress with an amix fallback. concat_copy() uses the concat demuxer
  with POSIX-quoted paths (backslashes are escape chars in manifests) and falls back to
  re-encode if stream copy rejects a residual mismatch.
- GOTCHA FIXED: MASTER_WORKLOG.md was UTF-16LE on disk; a shell `cat >>` append produced
  a mixed-encoding file. Recreated as UTF-8/LF. All programmatic appends are UTF-8.
NEXT: STAGE 2 - verify the media layer end to end against live network + ffmpeg before
building agents on top of it (download still -> kenburns clip -> probe duration ->
music bed -> concat -> mix).

---

## [2026-08-22T02:20+05:30] STAGE 2 - Media layer VERIFIED against live ffmpeg + network
STATUS: DONE
FILES: oioi/backend/studio_pipeline/selfcheck.py, media.py (TTS rewritten)
HOW TO RERUN: cd oioi/backend && ../.venv/Scripts/python.exe -m studio_pipeline.selfcheck
FACTS (all measured, not assumed):
- PASS ffmpeg 9.0-full_build.
- PASS omniroute chat: 7.2s round trip. CAVEAT: this model sometimes emits its
  reasoning INTO the content field (probe returned "The user says: ..."). So prose
  before JSON is normal and extract_json()s brace-slicing is load-bearing, not defensive.
- PASS omniroute json mode: chat_json() returned a real parsed dict {"ok": True, "n": 3}.
- PASS pollinations still: 51 KB JPEG, keyless, no API key.
- PASS kenburns clip: asked 6.0s got 6.00s (411 KB); asked 5.0s got 5.00s (185 KB).
  The zoompan filtergraph and duration control are exact.
- PASS music bed: 12.00s procedural ambient score.
- PASS ffmpeg concat (stream copy): 11.02s from 2 clips. Uniform-profile normalisation
  means -c copy works, so 3 hours will stitch without a re-encode.
- PASS final audio mix: 11.02s, sidechaincompress ducking path works.
- CORRECTED EARLIER FINDING - OmniRoute video route IS LIVE. My STAGE 0 probe saw a
  hang; on retry POST /v1/videos/generations answers properly. The gateway validates
  "provider/model" and its error text reveals the registry:
    * alibaba    -> "Unsupported alibaba video model: <x>" = provider recognised AND
                    CREDENTIALED. Only the model id is wrong. THIS IS THE ONE TO UNLOCK.
    * minimax    -> "No credentials for video provider: minimax"  (recognised, no key)
    * replicate  -> "No credentials for video provider: replicate" (recognised, no key)
    * pollinations -> "Unsupported video format: pollinations-video" (no video support)
    * google/gemini/kling/sora/fal/bytedance/openai -> "Invalid video model" = provider
      NOT in the registry at all.
  Tried and REJECTED as alibaba model ids: wanx2.1-t2v-turbo, wanx2.1-t2v-plus,
  wan2.2-t2v-plus, wanx-v1, text2video-synthesis, wanx2.1-i2v-turbo, wan2.5-t2v-preview,
  wanx2.1-t2v. The allowlist is hardcoded in OmniRoute at D:/omniroute-monetizer
  (grep for "Unsupported alibaba video model" timed out; not pursued further).
  => ACTION FOR OPERATOR: set OMNIROUTE_VIDEO_MODEL=alibaba/<correct-id> and the
     Animator switches from synthesis to real generated video with no code change.
- POST /v1/audio/speech exists but -> "No credentials for provider: openai".
- TTS: StreamElements is DEAD (401 "No API key was found"). The old pipeline hard-coded
  such a URL as its voice_track, so every "finished" film linked to a 401.
  REPLACEMENT (verified): Google Translate TTS returns HTTP 200 audio/mpeg 24 kHz mono,
  keyless, needs a browser User-Agent, ~200 char cap -> chunk_text() splits on sentence
  boundaries. Tier 2 is Windows SAPI via PowerShell (offline, no cap); tier 3 is silence
  so the cut timing survives regardless.
NEXT: STAGE 3 - write the 7 agents (hierarchical Scriptwriter with a bounded story-bible
digest, approval gate, art director, scene designer, animator, sound director, director).
