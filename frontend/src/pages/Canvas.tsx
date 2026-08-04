import { useState, useCallback, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { api } from '@/lib/api'
import {
  Wand2,
  Video,
  Image,
  Download,
  Plus,
  X,
  Loader2,
  Sparkles,
  ChevronDown,
  Film,
  ZoomIn,
  RefreshCw,
  Check,
  AlertCircle,
  Copy,
  Cpu,
} from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

const TEMPLATE_PROMPTS: Record<string, string> = {
  'story-anime': 'A young girl discovers a hidden portal in her grandmother\'s attic leading to a magical world of floating islands and friendly sky whales.',
  'music-video': 'A neon-lit city at midnight where a lone dancer\'s movements create ripples of light across the rain-soaked streets.',
  'creative-clip': 'A coffee cup transforming into a rocket ship that blasts through a surreal dreamscape of giant pastries and candy mountains.',
  'character-design': 'A stoic samurai-cyborg hybrid with quantum blade arms, glowing circuit tattoos, and a weathered cloth cape.',
  'scene-design': 'An ancient underwater temple overgrown with bioluminescent coral, shafts of sunlight piercing the turquoise depths.',
  'ip-creation': 'A world where emotions are visible as colored auras and a young empath must unite warring factions.',
  'viral-remake': 'The classic hero\'s journey reimagined as a modern influencer story with AI companions and digital quests.',
}

interface Panel {
  id: string
  prompt: string
  style: string
  model: string
  status: 'idle' | 'generating' | 'done' | 'error'
  imageUrl?: string
  videoUrl?: string
  type: 'image' | 'video'
  errorMsg?: string
}

function createPanel(index: number, defaults: { style: string; model: string; type: 'image' | 'video' }): Panel {
  return {
    id: `panel-${index}-${Date.now()}`,
    prompt: '',
    style: defaults.style,
    model: defaults.model,
    type: defaults.type,
    status: 'idle',
  }
}

export function Canvas() {
  const [searchParams] = useSearchParams()
  const template = searchParams.get('template') || ''
  const presetModel = searchParams.get('model') || ''

  const [globalPrompt, setGlobalPrompt] = useState(TEMPLATE_PROMPTS[template] || '')
  const [selectedStyle, setSelectedStyle] = useState('Anime')
  const [selectedModel, setSelectedModel] = useState(presetModel || 'flux')
  const [outputType, setOutputType] = useState<'image' | 'video'>('image')
  const [panels, setPanels] = useState<Panel[]>([
    createPanel(0, { style: 'Anime', model: 'flux', type: 'image' }),
    createPanel(1, { style: 'Anime', model: 'flux', type: 'image' }),
    createPanel(2, { style: 'Anime', model: 'flux', type: 'image' }),
    createPanel(3, { style: 'Anime', model: 'flux', type: 'image' }),
  ])
  const [showStylePicker, setShowStylePicker] = useState(false)
  const [showModelPicker, setShowModelPicker] = useState(false)
  const [pipelineRunning, setPipelineRunning] = useState(false)
  const [pipelineResult, setPipelineResult] = useState<any>(null)
  const stylePickerRef = useRef<HTMLDivElement>(null)

  const { data: stylesData } = useQuery({
    queryKey: ['styles'],
    queryFn: () => api.getStyles ? api.getStyles() : fetch('/api/v1/styles').then(r => r.json()),
  })

  const { data: modelsData } = useQuery({
    queryKey: ['models'],
    queryFn: () => api.getModels(),
  })

  const styles: any[] = stylesData?.styles || []
  const models: any[] = modelsData?.models || []
  const videoModels = models.filter(m => m.category === 'Video' || m.category === 'video')
  const imageModels = models.filter(m => m.category === 'Image' || m.category === 'image')

  const generatePanel = useCallback(async (panelId: string, prompt: string) => {
    const effectivePrompt = `${prompt || globalPrompt}. Style: ${selectedStyle}.`
    setPanels(prev => prev.map(p =>
      p.id === panelId ? { ...p, status: 'generating' } : p
    ))
    try {
      if (outputType === 'image') {
        // Hit the real images endpoint
        const res = await fetch('/api/v1/images/generations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt: effectivePrompt,
            model: selectedModel,
            n: 1,
            size: '1024x576',
          }),
        })
        const data = await res.json()
        const url = data?.data?.[0]?.url || data?.url || `https://image.pollinations.ai/prompt/${encodeURIComponent(effectivePrompt)}`
        setPanels(prev => prev.map(p =>
          p.id === panelId ? { ...p, status: 'done', imageUrl: url } : p
        ))
      } else {
        const res = await fetch('/api/v1/videos/generations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt: effectivePrompt,
            model: selectedModel,
            duration: 5,
          }),
        })
        const data = await res.json()
        const url = data?.data?.[0]?.url || data?.url || `https://image.pollinations.ai/prompt/${encodeURIComponent(effectivePrompt)}`
        setPanels(prev => prev.map(p =>
          p.id === panelId ? { ...p, status: 'done', videoUrl: url, imageUrl: url } : p
        ))
      }
    } catch (err: any) {
      // Fallback: use Pollinations directly for image
      const fallbackUrl = `https://image.pollinations.ai/prompt/${encodeURIComponent(effectivePrompt)}&width=1024&height=576&nologo=true`
      setPanels(prev => prev.map(p =>
        p.id === panelId ? { ...p, status: 'done', imageUrl: fallbackUrl } : p
      ))
    }
  }, [globalPrompt, selectedStyle, selectedModel, outputType])

  const generateAll = useCallback(async () => {
    for (const panel of panels) {
      await generatePanel(panel.id, panel.prompt)
    }
  }, [panels, generatePanel])

  const runFullPipeline = useCallback(async () => {
    if (!globalPrompt.trim()) return
    setPipelineRunning(true)
    setPipelineResult(null)
    try {
      const res = await fetch('/api/v1/pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idea: globalPrompt, style: selectedStyle }),
      })
      const data = await res.json()
      setPipelineResult(data)
      // Auto-populate panels from pipeline character/scene images
      const chars = data?.characters || []
      const scenes = data?.scenes || []
      const combined = [...chars, ...scenes].slice(0, panels.length)
      setPanels(prev => prev.map((p, i) => {
        const src = combined[i]
        if (!src) return p
        return {
          ...p,
          status: 'done',
          imageUrl: src.image_url || src.url,
          prompt: src.description || p.prompt,
        }
      }))
    } catch (err) {
      console.error('Pipeline error:', err)
    } finally {
      setPipelineRunning(false)
    }
  }, [globalPrompt, selectedStyle, panels.length])

  const addPanel = () => {
    setPanels(prev => [...prev, createPanel(prev.length, { style: selectedStyle, model: selectedModel, type: outputType })])
  }

  const removePanel = (id: string) => {
    setPanels(prev => prev.filter(p => p.id !== id))
  }

  const STYLE_CATEGORIES = [...new Set(styles.map(s => s.category))].filter(Boolean)
  const [styleCategory, setStyleCategory] = useState<string>('Anime')

  return (
    <div className="space-y-0 -m-6 lg:-m-8">
      {/* Top Toolbar */}
      <div className="sticky top-0 z-20 border-b border-dark-200 dark:border-dark-700 bg-white/90 dark:bg-dark-950/90 backdrop-blur-md px-6 py-3">
        <div className="flex items-center gap-3 flex-wrap">
          {/* Global Prompt */}
          <div className="flex-1 min-w-64">
            <input
              type="text"
              value={globalPrompt}
              onChange={e => setGlobalPrompt(e.target.value)}
              placeholder="Describe your animation idea..."
              className="w-full px-4 py-2 text-sm rounded-xl border border-dark-200 dark:border-dark-600 bg-white dark:bg-dark-900 text-dark-900 dark:text-white placeholder:text-dark-400 focus:outline-none focus:ring-2 focus:ring-violet-500"
            />
          </div>

          {/* Style Picker */}
          <div className="relative">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowStylePicker(v => !v)}
              className="gap-2"
            >
              <Sparkles className="h-4 w-4 text-violet-500" />
              {selectedStyle}
              <ChevronDown className="h-3 w-3" />
            </Button>
            {showStylePicker && (
              <div ref={stylePickerRef} className="absolute top-full mt-2 left-0 w-72 bg-white dark:bg-dark-900 border border-dark-200 dark:border-dark-700 rounded-xl shadow-xl z-30 overflow-hidden">
                <div className="flex overflow-x-auto border-b border-dark-100 dark:border-dark-800 p-2 gap-1">
                  {STYLE_CATEGORIES.slice(0, 8).map(cat => (
                    <button
                      key={cat}
                      onClick={() => setStyleCategory(cat)}
                      className={`px-3 py-1 text-xs rounded-full whitespace-nowrap transition-colors ${
                        styleCategory === cat
                          ? 'bg-violet-600 text-white'
                          : 'bg-dark-100 dark:bg-dark-800 text-dark-600 dark:text-dark-400 hover:bg-dark-200'
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
                <div className="max-h-48 overflow-y-auto p-2 grid grid-cols-2 gap-1">
                  {styles.filter(s => s.category === styleCategory).slice(0, 20).map((s: any) => (
                    <button
                      key={s.id}
                      onClick={() => { setSelectedStyle(s.name); setShowStylePicker(false) }}
                      className={`text-left px-3 py-2 text-xs rounded-lg transition-colors ${
                        selectedStyle === s.name
                          ? 'bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300 font-medium'
                          : 'hover:bg-dark-50 dark:hover:bg-dark-800 text-dark-700 dark:text-dark-300'
                      }`}
                    >
                      {s.name}
                    </button>
                  ))}
                  {styles.filter(s => s.category === styleCategory).length === 0 && (
                    <p className="text-xs text-dark-400 p-2 col-span-2">No styles in this category</p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Model Picker */}
          <div className="relative">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowModelPicker(v => !v)}
              className="gap-2"
            >
              <Cpu className="h-4 w-4 text-blue-500" />
              {selectedModel}
              <ChevronDown className="h-3 w-3" />
            </Button>
            {showModelPicker && (
              <div className="absolute top-full mt-2 right-0 w-64 bg-white dark:bg-dark-900 border border-dark-200 dark:border-dark-700 rounded-xl shadow-xl z-30 overflow-hidden">
                <div className="p-2 border-b border-dark-100 dark:border-dark-800">
                  <p className="text-xs font-medium text-dark-500 dark:text-dark-400 px-2 mb-1">Image Models</p>
                  {(imageModels.length > 0 ? imageModels : [
                    { id: 'flux', name: 'Flux (Pollinations)' },
                    { id: 'flux-realism', name: 'Flux Realism' },
                    { id: 'dall-e-3', name: 'DALL-E 3' },
                    { id: 'stable-diffusion-xl', name: 'SDXL' },
                  ]).slice(0, 8).map((m: any) => (
                    <button
                      key={m.id}
                      onClick={() => { setSelectedModel(m.id); setOutputType('image'); setShowModelPicker(false) }}
                      className={`w-full text-left px-3 py-1.5 text-xs rounded-lg transition-colors ${
                        selectedModel === m.id
                          ? 'bg-violet-100 dark:bg-violet-900/40 text-violet-700 font-medium'
                          : 'hover:bg-dark-50 dark:hover:bg-dark-800 text-dark-700 dark:text-dark-300'
                      }`}
                    >
                      {m.name}
                    </button>
                  ))}
                </div>
                <div className="p-2">
                  <p className="text-xs font-medium text-dark-500 dark:text-dark-400 px-2 mb-1">Video Models</p>
                  {(videoModels.length > 0 ? videoModels : [
                    { id: 'kling-3.0', name: 'Kling 3.0' },
                    { id: 'seedance-2.0', name: 'Seedance 2.0' },
                    { id: 'sora-2', name: 'Sora 2' },
                  ]).slice(0, 6).map((m: any) => (
                    <button
                      key={m.id}
                      onClick={() => { setSelectedModel(m.id); setOutputType('video'); setShowModelPicker(false) }}
                      className={`w-full text-left px-3 py-1.5 text-xs rounded-lg transition-colors ${
                        selectedModel === m.id
                          ? 'bg-violet-100 dark:bg-violet-900/40 text-violet-700 font-medium'
                          : 'hover:bg-dark-50 dark:hover:bg-dark-800 text-dark-700 dark:text-dark-300'
                      }`}
                    >
                      {m.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Output Type Toggle */}
          <div className="flex rounded-lg border border-dark-200 dark:border-dark-700 overflow-hidden">
            <button
              onClick={() => setOutputType('image')}
              className={`px-3 py-1.5 text-xs font-medium flex items-center gap-1 transition-colors ${
                outputType === 'image'
                  ? 'bg-violet-600 text-white'
                  : 'text-dark-600 dark:text-dark-400 hover:bg-dark-50 dark:hover:bg-dark-800'
              }`}
            >
              <Image className="h-3 w-3" /> Image
            </button>
            <button
              onClick={() => setOutputType('video')}
              className={`px-3 py-1.5 text-xs font-medium flex items-center gap-1 transition-colors ${
                outputType === 'video'
                  ? 'bg-violet-600 text-white'
                  : 'text-dark-600 dark:text-dark-400 hover:bg-dark-50 dark:hover:bg-dark-800'
              }`}
            >
              <Video className="h-3 w-3" /> Video
            </button>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 ml-auto">
            <Button
              variant="outline"
              size="sm"
              onClick={runFullPipeline}
              disabled={pipelineRunning || !globalPrompt.trim()}
            >
              {pipelineRunning ? (
                <><Loader2 className="h-4 w-4 mr-1 animate-spin" /> Pipeline Running...</>
              ) : (
                <><Film className="h-4 w-4 mr-1" /> Full Pipeline</>
              )}
            </Button>
            <Button
              size="sm"
              onClick={generateAll}
              disabled={!globalPrompt.trim()}
              className="bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white shadow-md"
            >
              <Wand2 className="h-4 w-4 mr-1" />
              Generate All
            </Button>
          </div>
        </div>
      </div>

      {/* Pipeline Result Banner */}
      {pipelineResult && (
        <div className="mx-6 mt-4 p-4 rounded-xl bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
          <div className="flex items-start gap-3">
            <Check className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="font-medium text-green-800 dark:text-green-200">Pipeline complete!</p>
              <p className="text-sm text-green-700 dark:text-green-300 mt-1">
                {pipelineResult.script?.slice(0, 120)}...
              </p>
              {pipelineResult.director_notes && (
                <p className="text-xs text-green-600 dark:text-green-400 mt-1">
                  Director: {pipelineResult.director_notes}
                </p>
              )}
            </div>
            <button onClick={() => setPipelineResult(null)}>
              <X className="h-4 w-4 text-green-600" />
            </button>
          </div>
        </div>
      )}

      {/* Canvas Grid */}
      <div className="p-6 lg:p-8">
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-4">
          {panels.map((panel, index) => (
            <div
              key={panel.id}
              className="group relative rounded-2xl border-2 border-dark-200 dark:border-dark-700 overflow-hidden bg-dark-50 dark:bg-dark-900 aspect-video flex flex-col hover:border-violet-400 dark:hover:border-violet-600 transition-all duration-200"
            >
              {/* Panel Header */}
              <div className="absolute top-2 left-2 right-2 z-10 flex items-center justify-between">
                <Badge variant="outline" className="text-xs bg-black/40 border-white/20 text-white backdrop-blur-sm">
                  Panel {index + 1}
                </Badge>
                <div className="flex gap-1">
                  {panel.status === 'done' && panel.imageUrl && (
                    <a
                      href={panel.imageUrl}
                      download
                      className="p-1 rounded-lg bg-black/40 text-white hover:bg-black/60 backdrop-blur-sm transition-colors"
                    >
                      <Download className="h-3.5 w-3.5" />
                    </a>
                  )}
                  <button
                    onClick={() => removePanel(panel.id)}
                    className="p-1 rounded-lg bg-black/40 text-white hover:bg-red-500/80 backdrop-blur-sm transition-colors"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              {/* Panel Content */}
              {panel.status === 'idle' && (
                <div className="flex-1 flex flex-col items-center justify-center gap-3 p-4">
                  <div className="p-3 rounded-full bg-violet-100 dark:bg-violet-900/30">
                    <Image className="h-6 w-6 text-violet-500" />
                  </div>
                  <p className="text-xs text-dark-400 text-center">Click Generate to create</p>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => generatePanel(panel.id, panel.prompt)}
                    disabled={!globalPrompt.trim()}
                    className="text-xs"
                  >
                    <Wand2 className="h-3 w-3 mr-1" />
                    Generate
                  </Button>
                </div>
              )}

              {panel.status === 'generating' && (
                <div className="flex-1 flex flex-col items-center justify-center gap-3">
                  <div className="relative">
                    <div className="h-12 w-12 rounded-full border-2 border-violet-200 dark:border-violet-800" />
                    <div className="absolute inset-0 h-12 w-12 rounded-full border-2 border-violet-600 border-t-transparent animate-spin" />
                  </div>
                  <p className="text-xs text-dark-400">Generating...</p>
                </div>
              )}

              {panel.status === 'done' && panel.imageUrl && (
                <div className="flex-1 relative">
                  <img
                    src={panel.imageUrl}
                    alt={`Panel ${index + 1}`}
                    className="w-full h-full object-cover"
                    onError={e => {
                      (e.target as HTMLImageElement).src = `https://image.pollinations.ai/prompt/${encodeURIComponent(globalPrompt + ' ' + selectedStyle)}&width=512&height=288&nologo=true&seed=${index}`
                    }}
                  />
                  <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity bg-black/30 flex items-center justify-center gap-2">
                    <button
                      onClick={() => generatePanel(panel.id, panel.prompt)}
                      className="p-2 rounded-lg bg-white/20 backdrop-blur-sm hover:bg-white/30 transition-colors text-white"
                    >
                      <RefreshCw className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => window.open(panel.imageUrl, '_blank')}
                      className="p-2 rounded-lg bg-white/20 backdrop-blur-sm hover:bg-white/30 transition-colors text-white"
                    >
                      <ZoomIn className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              )}

              {panel.status === 'error' && (
                <div className="flex-1 flex flex-col items-center justify-center gap-2 p-4">
                  <AlertCircle className="h-8 w-8 text-red-400" />
                  <p className="text-xs text-red-400 text-center">{panel.errorMsg || 'Generation failed'}</p>
                  <Button size="sm" variant="outline" onClick={() => generatePanel(panel.id, panel.prompt)} className="text-xs">
                    Retry
                  </Button>
                </div>
              )}

              {/* Per-panel prompt override */}
              <div className="border-t border-dark-200 dark:border-dark-700 p-2">
                <input
                  type="text"
                  value={panel.prompt}
                  onChange={e => setPanels(prev => prev.map(p => p.id === panel.id ? { ...p, prompt: e.target.value } : p))}
                  placeholder={`Override prompt for panel ${index + 1}...`}
                  className="w-full px-2 py-1 text-xs rounded-lg bg-transparent border border-dark-200 dark:border-dark-700 text-dark-700 dark:text-dark-300 placeholder:text-dark-400 focus:outline-none focus:border-violet-400"
                />
              </div>
            </div>
          ))}

          {/* Add Panel Button */}
          <button
            onClick={addPanel}
            className="aspect-video rounded-2xl border-2 border-dashed border-dark-300 dark:border-dark-700 flex flex-col items-center justify-center gap-2 text-dark-400 hover:border-violet-400 hover:text-violet-500 transition-all duration-200 hover:bg-violet-50 dark:hover:bg-violet-900/10"
          >
            <Plus className="h-8 w-8" />
            <span className="text-sm font-medium">Add Panel</span>
          </button>
        </div>

        {/* Script Result */}
        {pipelineResult?.script && (
          <Card className="mt-6">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-sm">
                <Film className="h-4 w-4" />
                Generated Script
              </CardTitle>
              <button
                onClick={() => navigator.clipboard.writeText(pipelineResult.script)}
                className="p-1.5 rounded-lg hover:bg-dark-100 dark:hover:bg-dark-800 transition-colors text-dark-500"
              >
                <Copy className="h-4 w-4" />
              </button>
            </CardHeader>
            <CardContent>
              <pre className="text-sm text-dark-700 dark:text-dark-300 whitespace-pre-wrap font-mono bg-dark-50 dark:bg-dark-900 p-4 rounded-xl max-h-48 overflow-y-auto">
                {pipelineResult.script}
              </pre>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}


