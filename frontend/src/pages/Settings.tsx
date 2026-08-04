import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import {
  Settings2,
  Key,
  Palette,
  Cpu,
  CheckCircle,
  Eye,
  EyeOff,
  Save,
  RefreshCw,
  Info,
  Moon,
  Sun,
} from 'lucide-react'

interface ProviderConfig {
  id: string
  name: string
  description: string
  keyRequired: boolean
  docsUrl: string
  placeholder: string
}

const PROVIDERS: ProviderConfig[] = [
  {
    id: 'gemini',
    name: 'Google Gemini',
    description: 'Gemini 2.0 Flash & Pro for text and image generation',
    keyRequired: false,
    docsUrl: 'https://aistudio.google.com',
    placeholder: 'AIza...',
  },
  {
    id: 'groq',
    name: 'Groq',
    description: 'Ultra-fast LLaMA and Mixtral inference on free tier',
    keyRequired: false,
    docsUrl: 'https://console.groq.com',
    placeholder: 'gsk_...',
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    description: 'Access 100+ models via unified API',
    keyRequired: false,
    docsUrl: 'https://openrouter.ai',
    placeholder: 'sk-or-...',
  },
  {
    id: 'pollinations',
    name: 'Pollinations.ai',
    description: 'Keyless image & video generation — always available',
    keyRequired: false,
    docsUrl: 'https://pollinations.ai',
    placeholder: 'No key required',
  },
  {
    id: 'cerebras',
    name: 'Cerebras',
    description: 'World\'s fastest AI inference for LLMs',
    keyRequired: false,
    docsUrl: 'https://cloud.cerebras.ai',
    placeholder: 'csk-...',
  },
  {
    id: 'cohere',
    name: 'Cohere',
    description: 'Command R+ for streaming text generation',
    keyRequired: false,
    docsUrl: 'https://dashboard.cohere.com',
    placeholder: '...',
  },
  {
    id: 'cloudflare',
    name: 'Cloudflare AI',
    description: 'Workers AI for edge video & image generation',
    keyRequired: false,
    docsUrl: 'https://dash.cloudflare.com',
    placeholder: 'Bearer ...',
  },
]

const DEFAULT_PIPELINE_MODELS = [
  { id: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash (Recommended)' },
  { id: 'llama-3.3-70b-versatile', label: 'LLaMA 3.3 70B (Groq)' },
  { id: 'mistral-7b-instruct', label: 'Mistral 7B (OpenRouter)' },
  { id: 'llama-3.1-8b-instant', label: 'LLaMA 3.1 8B Instant (Groq)' },
]

export function Settings() {
  const [keys, setKeys] = useState<Record<string, string>>({})
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({})
  const [savedKeys, setSavedKeys] = useState<Record<string, boolean>>({})
  const [defaultModel, setDefaultModel] = useState('gemini-2.0-flash')
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [maxConcurrent, setMaxConcurrent] = useState(3)

  const handleSaveKey = (providerId: string) => {
    // In a real app this would persist to backend / localStorage
    setSavedKeys(prev => ({ ...prev, [providerId]: true }))
    setTimeout(() => setSavedKeys(prev => ({ ...prev, [providerId]: false })), 2000)
  }

  const toggleShow = (id: string) => {
    setShowKeys(prev => ({ ...prev, [id]: !prev[id] }))
  }

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-dark-900 dark:text-white flex items-center gap-3">
          <Settings2 className="h-8 w-8 text-violet-600" />
          Settings
        </h1>
        <p className="text-dark-500 dark:text-dark-400 mt-1">
          Configure provider API keys, pipeline defaults, and appearance
        </p>
      </div>

      {/* Provider Keys */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5 text-violet-500" />
            Provider API Keys
          </CardTitle>
          <p className="text-sm text-dark-500 dark:text-dark-400">
            All providers work on free tiers — keys unlock higher rate limits.{' '}
            <span className="text-violet-600 font-medium">Pollinations.ai requires no key at all.</span>
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {PROVIDERS.map(provider => (
            <div key={provider.id} className="flex flex-col gap-2 p-4 rounded-xl border border-dark-200 dark:border-dark-700">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-dark-900 dark:text-white">{provider.name}</span>
                    {provider.id === 'pollinations' && (
                      <Badge variant="success" className="text-xs">Keyless ✓</Badge>
                    )}
                  </div>
                  <p className="text-xs text-dark-500 dark:text-dark-400 mt-0.5">{provider.description}</p>
                </div>
                <a
                  href={provider.docsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-violet-600 hover:underline flex items-center gap-1"
                >
                  <Info className="h-3 w-3" />
                  Docs
                </a>
              </div>
              {provider.id !== 'pollinations' && (
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <input
                      type={showKeys[provider.id] ? 'text' : 'password'}
                      value={keys[provider.id] || ''}
                      onChange={e => setKeys(prev => ({ ...prev, [provider.id]: e.target.value }))}
                      placeholder={provider.placeholder}
                      className="w-full px-3 py-2 text-sm rounded-lg border border-dark-200 dark:border-dark-600 bg-white dark:bg-dark-900 text-dark-900 dark:text-white placeholder:text-dark-400 focus:outline-none focus:ring-2 focus:ring-violet-500 pr-9"
                    />
                    <button
                      type="button"
                      onClick={() => toggleShow(provider.id)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-dark-400 hover:text-dark-600"
                    >
                      {showKeys[provider.id] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  <Button size="sm" onClick={() => handleSaveKey(provider.id)} disabled={!keys[provider.id]}>
                    {savedKeys[provider.id] ? (
                      <><CheckCircle className="h-4 w-4 mr-1 text-green-400" /> Saved</>
                    ) : (
                      <><Save className="h-4 w-4 mr-1" /> Save</>
                    )}
                  </Button>
                </div>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Pipeline Defaults */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cpu className="h-5 w-5 text-blue-500" />
            Pipeline Defaults
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-dark-700 dark:text-dark-300 mb-2">
              Default LLM Model (for Scriptwriter & Director agents)
            </label>
            <select
              value={defaultModel}
              onChange={e => setDefaultModel(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-dark-200 dark:border-dark-600 bg-white dark:bg-dark-900 text-dark-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              {DEFAULT_PIPELINE_MODELS.map(m => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-700 dark:text-dark-300 mb-2">
              Max Concurrent Generations: <span className="text-violet-600">{maxConcurrent}</span>
            </label>
            <input
              type="range"
              min={1}
              max={8}
              value={maxConcurrent}
              onChange={e => setMaxConcurrent(Number(e.target.value))}
              className="w-full accent-violet-600"
            />
            <div className="flex justify-between text-xs text-dark-400 mt-1">
              <span>1 (Conservative)</span>
              <span>8 (Max parallelism)</span>
            </div>
          </div>

          <Button className="w-full" onClick={() => {}}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Save Pipeline Defaults
          </Button>
        </CardContent>
      </Card>

      {/* Appearance */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Palette className="h-5 w-5 text-pink-500" />
            Appearance
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setTheme('light')}
              className={`flex-1 flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all ${
                theme === 'light'
                  ? 'border-violet-500 bg-violet-50 dark:bg-violet-900/20'
                  : 'border-dark-200 dark:border-dark-700 hover:border-dark-300'
              }`}
            >
              <Sun className="h-6 w-6 text-amber-500" />
              <span className="text-sm font-medium text-dark-700 dark:text-dark-300">Light</span>
            </button>
            <button
              onClick={() => setTheme('dark')}
              className={`flex-1 flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all ${
                theme === 'dark'
                  ? 'border-violet-500 bg-violet-50 dark:bg-violet-900/20'
                  : 'border-dark-200 dark:border-dark-700 hover:border-dark-300'
              }`}
            >
              <Moon className="h-6 w-6 text-indigo-500" />
              <span className="text-sm font-medium text-dark-700 dark:text-dark-300">Dark</span>
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
