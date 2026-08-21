'use client';

import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Film,
  Layers,
  Wand2,
  Video,
  Image as ImageIcon,
  Play,
  Settings2,
  Bot,
  Palette,
  LayoutGrid,
  CheckCircle2,
  Cpu,
  RefreshCw,
  Sliders,
  Send,
  Plus,
  Trash2,
  Share2,
  Download,
} from 'lucide-react';

interface ModelItem {
  id: string;
  category: string;
  provider: string;
  url: string;
}

interface StyleItem {
  id: string;
  name: string;
  category: string;
  thumbnail: string;
  promptSuffix: string;
}

interface StoryboardPanel {
  id: number;
  title: string;
  prompt: string;
  imageUrl?: string;
  videoUrl?: string;
  status: 'idle' | 'generating' | 'ready';
  aspectRatio: string;
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<'canvas' | 'agents' | 'models' | 'styles'>('canvas');
  const [prompt, setPrompt] = useState('Cyberpunk ninja confronting a giant neon dragon in Neo-Tokyo rain');
  const [selectedModel, setSelectedModel] = useState('gemini-2.5-flash');
  const [selectedStyle, setSelectedStyle] = useState('Anime Style 0');
  const [isGenerating, setIsGenerating] = useState(false);
  const [agentProgress, setAgentProgress] = useState<number>(0);
  const [activeAgent, setActiveAgent] = useState<string>('Director');
  
  // Storyboard panels
  const [panels, setPanels] = useState<StoryboardPanel[]>([
    {
      id: 1,
      title: 'Scene 1: The Rainy Rooftop',
      prompt: 'Cyberpunk ninja perched on a glowing skyscraper ledge in heavy rain',
      imageUrl: 'https://image.pollinations.ai/prompt/cyberpunk%20ninja%20on%20neon%20rooftop%20rain%20anime%20style',
      videoUrl: 'https://cdn.pollinations.ai/video/clip_scene1.mp4',
      status: 'ready',
      aspectRatio: '16:9',
    },
    {
      id: 2,
      title: 'Scene 2: Neon Dragon Emerges',
      prompt: 'Giant luminescent dragon rising through volumetric clouds above Neo-Tokyo',
      imageUrl: 'https://image.pollinations.ai/prompt/giant%20neon%20dragon%20clouds%20anime%20style',
      videoUrl: 'https://cdn.pollinations.ai/video/clip_scene2.mp4',
      status: 'ready',
      aspectRatio: '16:9',
    },
    {
      id: 3,
      title: 'Scene 3: The Clashing Blade',
      prompt: 'Energy katana slashing through holographic rain particles in hyper-speed',
      imageUrl: 'https://image.pollinations.ai/prompt/energy%20katana%20slash%20hologram%20anime%20style',
      videoUrl: 'https://cdn.pollinations.ai/video/clip_scene3.mp4',
      status: 'ready',
      aspectRatio: '16:9',
    },
  ]);

  // Agent team list
  const agentTeam = [
    { role: 'Scriptwriter', desc: 'Crafts narrative, story arcs, and character dialogues' },
    { role: 'Art Director', desc: 'Curates color palettes, aesthetics, and cinematic mood' },
    { role: 'Character Designer', desc: 'Generates consistent character model sheets & expressions' },
    { role: 'Scene Designer', desc: 'Constructs 3D isometric environments & spatial backgrounds' },
    { role: 'Animator', desc: 'Computes motion keyframes, frame interpolation & camera paths' },
    { role: 'Sound Director', desc: 'Synthesizes dialogue, Foley sound effects & adaptive soundtrack' },
    { role: 'Director', desc: 'Coordinates the 7-agent pipeline & approves the final master cut' },
  ];

  const handleRunPipeline = async () => {
    setIsGenerating(true);
    setAgentProgress(10);
    setActiveAgent('Scriptwriter');

    // Simulate multi-agent step progression
    for (let i = 0; i < agentTeam.length; i++) {
      setActiveAgent(agentTeam[i].role);
      setAgentProgress(Math.round(((i + 1) / agentTeam.length) * 100));
      await new Promise((r) => setTimeout(r, 600));
    }

    setIsGenerating(false);
  };

  const handleAddPanel = () => {
    const nextId = panels.length + 1;
    setPanels([
      ...panels,
      {
        id: nextId,
        title: `Scene ${nextId}: New Sequence`,
        prompt: 'Continuation of the cinematic storyline with dynamic lighting',
        imageUrl: `https://image.pollinations.ai/prompt/anime%20scene%20sequence%20${nextId}`,
        status: 'ready',
        aspectRatio: '16:9',
      },
    ]);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-slate-100 flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800/80 bg-[#0d0e15]/90 backdrop-blur-md px-6 py-3.5 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-indigo-300 to-fuchsia-400">
              OiiOii.ai Studio
            </h1>
            <p className="text-[11px] text-slate-400">Autonomous 7-Agent AI Animation Engine</p>
          </div>
        </div>

        {/* Center Tabs */}
        <nav className="flex items-center space-x-1 bg-slate-900/90 border border-slate-800 p-1 rounded-xl">
          <button
            onClick={() => setActiveTab('canvas')}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === 'canvas' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <LayoutGrid className="w-3.5 h-3.5" />
            <span>Animation Canvas</span>
          </button>
          <button
            onClick={() => setActiveTab('agents')}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === 'agents' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Bot className="w-3.5 h-3.5" />
            <span>Agent Team (7)</span>
          </button>
          <button
            onClick={() => setActiveTab('models')}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === 'models' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>25+ Free Models</span>
          </button>
          <button
            onClick={() => setActiveTab('styles')}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === 'styles' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Palette className="w-3.5 h-3.5" />
            <span>150+ Styles</span>
          </button>
        </nav>

        {/* Right Info Badges */}
        <div className="flex items-center space-x-3">
          <span className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span>Free-Tier Multi-Provider (NVIDIA-Free)</span>
          </span>
          <button className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-medium flex items-center space-x-1.5 transition-colors">
            <Download className="w-3.5 h-3.5" />
            <span>Export Film</span>
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 flex overflow-hidden">
        {/* Left Toolbar / Prompt Studio */}
        <aside className="w-80 border-r border-slate-800 bg-[#0c0d14] p-5 flex flex-col justify-between shrink-0">
          <div className="space-y-5">
            <div>
              <label className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5 mb-2">
                <Wand2 className="w-3.5 h-3.5 text-cyan-400" />
                <span>Story & Scene Prompt</span>
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={4}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 focus:outline-none focus:border-cyan-500/60 transition-colors resize-none placeholder-slate-600"
                placeholder="Describe your animation scene..."
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5 mb-2">
                <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                <span>AI Model</span>
              </label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/60"
              >
                <optgroup label="Video Generation">
                  <option value="gemini-2.5-veo">Gemini 2.5 Veo (Free)</option>
                  <option value="kling-3.0">Kling 3.0</option>
                  <option value="seedance-2.0">Seedance 2.0</option>
                  <option value="wan">Wan Video</option>
                </optgroup>
                <optgroup label="Image Generation">
                  <option value="pollinations-flux">Pollinations Flux (Keyless Free)</option>
                  <option value="cloudflare-sdxl">Cloudflare SDXL</option>
                  <option value="gpt-image-2">GPT-Image-2</option>
                </optgroup>
                <optgroup label="LLM Multi-Agent">
                  <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                  <option value="llama-3.3-70b">Groq Llama 3.3 70B</option>
                  <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
                </optgroup>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5 mb-2">
                <Palette className="w-3.5 h-3.5 text-fuchsia-400" />
                <span>Visual Style (150+ Available)</span>
              </label>
              <select
                value={selectedStyle}
                onChange={(e) => setSelectedStyle(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/60"
              >
                <option value="Anime Style 0">Anime (Cyberpunk Neon)</option>
                <option value="Realistic Style 1">Cinematic 8K Photorealistic</option>
                <option value="3D Style 2">3D Isometric Cartoon</option>
                <option value="Watercolor Style 11">Ethereal Studio Ghibli Watercolor</option>
                <option value="Pixel Art Style 3">16-Bit Retro Pixel Art</option>
                <option value="Gothic Style 21">Dark Baroque Gothic Fantasy</option>
                <option value="Synthwave Style 36">80s Neon Synthwave Grid</option>
              </select>
            </div>

            <button
              onClick={handleRunPipeline}
              disabled={isGenerating}
              className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-cyan-500 via-indigo-600 to-fuchsia-600 hover:opacity-90 transition-opacity font-semibold text-xs text-white shadow-lg shadow-indigo-600/30 flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              {isGenerating ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Agent Team Working ({activeAgent})...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Generate Full Animation Pipeline</span>
                </>
              )}
            </button>

            {isGenerating && (
              <div className="space-y-1.5">
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Pipeline Progress</span>
                  <span>{agentProgress}%</span>
                </div>
                <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-cyan-400 to-indigo-500 h-full transition-all duration-300"
                    style={{ width: `${agentProgress}%` }}
                  />
                </div>
              </div>
            )}
          </div>

          <div className="pt-4 border-t border-slate-800 text-[11px] text-slate-500 space-y-1">
            <div className="flex items-center justify-between">
              <span>Active Inference:</span>
              <span className="text-slate-300 font-medium">Multi-Vendor Mesh</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Failover State:</span>
              <span className="text-emerald-400 font-medium">Automatic / Ready</span>
            </div>
          </div>
        </aside>

        {/* Central Workspace Area */}
        <section className="flex-1 bg-[#08080c] p-6 overflow-y-auto">
          {activeTab === 'canvas' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold text-slate-100 flex items-center space-x-2">
                    <Film className="w-5 h-5 text-cyan-400" />
                    <span>Storyboard Animation Canvas</span>
                  </h2>
                  <p className="text-xs text-slate-400">
                    Linked multi-panel canvas with concurrent generation & first/last-frame animation
                  </p>
                </div>
                <button
                  onClick={handleAddPanel}
                  className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold flex items-center space-x-1.5 transition-colors shadow-md"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add Storyboard Panel</span>
                </button>
              </div>

              {/* Storyboard Panels Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                {panels.map((panel) => (
                  <div
                    key={panel.id}
                    className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden hover:border-slate-700 transition-all flex flex-col group shadow-lg"
                  >
                    <div className="relative aspect-video bg-slate-950 overflow-hidden">
                      {panel.imageUrl && (
                        <img
                          src={panel.imageUrl}
                          alt={panel.title}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                        />
                      )}
                      <div className="absolute top-3 left-3 bg-black/60 backdrop-blur-md px-2.5 py-1 rounded-full text-[10px] font-semibold text-white border border-white/10 flex items-center space-x-1">
                        <Play className="w-2.5 h-2.5 fill-current text-cyan-400" />
                        <span>Scene {panel.id}</span>
                      </div>
                      <div className="absolute top-3 right-3 bg-black/60 backdrop-blur-md px-2.5 py-1 rounded-full text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">
                        {panel.status.toUpperCase()}
                      </div>
                    </div>

                    <div className="p-4 flex-1 flex flex-col justify-between space-y-3">
                      <div>
                        <h3 className="text-sm font-semibold text-slate-100">{panel.title}</h3>
                        <p className="text-xs text-slate-400 mt-1 line-clamp-2">{panel.prompt}</p>
                      </div>

                      <div className="flex items-center justify-between pt-3 border-t border-slate-800/80">
                        <div className="flex items-center space-x-2 text-[11px] text-slate-400">
                          <ImageIcon className="w-3.5 h-3.5 text-cyan-400" />
                          <span>1024x1024</span>
                          <span>•</span>
                          <Video className="w-3.5 h-3.5 text-indigo-400" />
                          <span>Veo Motion</span>
                        </div>
                        <button className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors">
                          <Sliders className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'agents' && (
            <div className="space-y-6 max-w-4xl mx-auto">
              <div>
                <h2 className="text-lg font-bold text-slate-100 flex items-center space-x-2">
                  <Bot className="w-5 h-5 text-indigo-400" />
                  <span>The 7-Agent Animation Team</span>
                </h2>
                <p className="text-xs text-slate-400">
                  Fully autonomous pipeline transforming high-level premises into production-ready animated cuts
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {agentTeam.map((ag, idx) => (
                  <div
                    key={ag.role}
                    className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-indigo-500/40 transition-colors flex items-start space-x-3.5"
                  >
                    <div className="w-8 h-8 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center font-bold text-xs text-indigo-400 shrink-0">
                      0{idx + 1}
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-slate-100">{ag.role}</h4>
                      <p className="text-xs text-slate-400 mt-1">{ag.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'models' && (
            <div className="space-y-6 max-w-4xl mx-auto">
              <div>
                <h2 className="text-lg font-bold text-slate-100 flex items-center space-x-2">
                  <Cpu className="w-5 h-5 text-cyan-400" />
                  <span>25+ Free-Tier AI Model Registry</span>
                </h2>
                <p className="text-xs text-slate-400">
                  All models dynamically mapped to zero-cost, free-tier multi-provider inference
                </p>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
                  <h3 className="text-sm font-bold text-cyan-400 mb-3">Video Models (25+)</h3>
                  <ul className="text-xs text-slate-300 space-y-2">
                    <li>• Gemini 2.5 Veo</li>
                    <li>• Kling 3.0</li>
                    <li>• Seedance 2.0</li>
                    <li>• Vidu Video</li>
                    <li>• Wan Motion</li>
                    <li>• Hailuo Video</li>
                  </ul>
                </div>
                <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
                  <h3 className="text-sm font-bold text-fuchsia-400 mb-3">Image Models (25+)</h3>
                  <ul className="text-xs text-slate-300 space-y-2">
                    <li>• Pollinations Flux (Keyless)</li>
                    <li>• Cloudflare SDXL</li>
                    <li>• GPT-Image-2</li>
                    <li>• Midjourney Ref</li>
                    <li>• Nano Diffusion</li>
                    <li>• Seedream</li>
                  </ul>
                </div>
                <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
                  <h3 className="text-sm font-bold text-indigo-400 mb-3">LLM Multi-Agent (25+)</h3>
                  <ul className="text-xs text-slate-300 space-y-2">
                    <li>• Gemini 2.5 Flash</li>
                    <li>• Groq Llama 3.3 70B</li>
                    <li>• Cerebras Ultra-Fast</li>
                    <li>• Claude 3.5 Sonnet</li>
                    <li>• Qwen 2.5 Coder</li>
                    <li>• Mixtral 8x7B</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'styles' && (
            <div className="space-y-6 max-w-4xl mx-auto">
              <div>
                <h2 className="text-lg font-bold text-slate-100 flex items-center space-x-2">
                  <Palette className="w-5 h-5 text-fuchsia-400" />
                  <span>150+ Cinematic Visual Styles</span>
                </h2>
                <p className="text-xs text-slate-400">
                  Curated presets with custom prompt engineering rules and lighting physics
                </p>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  'Anime', 'Cyberpunk', 'Realistic 8K', '3D Isometric', 'Studio Ghibli Watercolor',
                  '16-Bit Pixel Art', 'Baroque Gothic', 'Synthwave Retro', 'Impressionist Oil',
                  'Dark Fantasy', 'Comic Book Noir', 'Voxel Low-Poly'
                ].map((st) => (
                  <div
                    key={st}
                    className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-center hover:border-fuchsia-500/40 transition-colors cursor-pointer"
                  >
                    <span className="text-xs font-semibold text-slate-200">{st}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}