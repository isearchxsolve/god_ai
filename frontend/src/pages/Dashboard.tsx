import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { api } from '@/lib/api'
import {
  Video,
  FileText,
  Cpu,
  FolderKanban,
  Sparkles,
  TrendingUp,
  Clock,
  CheckCircle,
  Loader2,
  AlertCircle,
  ArrowRight,
  Plus,
  ExternalLink,
  Brain,
  Image,
  Music,
  Wand2,
  Film,
  Star,
  Clapperboard,
  Pen,
  Layers,
  Zap,
  BookOpen,
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { useNavigate } from 'react-router-dom'

function getGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

const QUICK_CREATE_CARDS = [
  {
    id: 'story-anime',
    label: 'Story Anime',
    description: 'Turn any idea into an animated short story',
    icon: Film,
    color: 'from-violet-500 to-purple-600',
    bg: 'bg-violet-50 dark:bg-violet-900/20',
    route: '/canvas?template=story-anime',
  },
  {
    id: 'music-video',
    label: 'Music Video',
    description: 'Sync animation to music beats',
    icon: Music,
    color: 'from-pink-500 to-rose-600',
    bg: 'bg-pink-50 dark:bg-pink-900/20',
    route: '/canvas?template=music-video',
  },
  {
    id: 'creative-clip',
    label: '15s Creative Clip',
    description: 'Fast, punchy 15-second animations',
    icon: Zap,
    color: 'from-amber-500 to-orange-600',
    bg: 'bg-amber-50 dark:bg-amber-900/20',
    route: '/canvas?template=creative-clip',
  },
  {
    id: 'character-design',
    label: 'Character Design',
    description: 'AI-generated character sheets & keyframes',
    icon: Star,
    color: 'from-sky-500 to-blue-600',
    bg: 'bg-sky-50 dark:bg-sky-900/20',
    route: '/canvas?template=character-design',
  },
  {
    id: 'scene-design',
    label: 'Scene Design',
    description: 'Environment layouts & mood boards',
    icon: Layers,
    color: 'from-emerald-500 to-teal-600',
    bg: 'bg-emerald-50 dark:bg-emerald-900/20',
    route: '/canvas?template=scene-design',
  },
  {
    id: 'ip-creation',
    label: 'IP Creation',
    description: 'Build a full original IP universe',
    icon: Sparkles,
    color: 'from-fuchsia-500 to-purple-600',
    bg: 'bg-fuchsia-50 dark:bg-fuchsia-900/20',
    route: '/canvas?template=ip-creation',
  },
  {
    id: 'viral-remake',
    label: 'Viral Remake',
    description: 'Reimagine trending content with AI',
    icon: TrendingUp,
    color: 'from-red-500 to-rose-600',
    bg: 'bg-red-50 dark:bg-red-900/20',
    route: '/canvas?template=viral-remake',
  },
  {
    id: 'script-breakdown',
    label: 'Smart Script Breakdown',
    description: 'Parse & storyboard any script automatically',
    icon: Pen,
    color: 'from-indigo-500 to-blue-600',
    bg: 'bg-indigo-50 dark:bg-indigo-900/20',
    route: '/script-generator',
  },
]

export function Dashboard() {
  const navigate = useNavigate()

  const { data: projectsData } = useQuery({
    queryKey: ['projects', 1, 5],
    queryFn: () => api.getVideoProjects(1, 5),
  })

  const { data: modelsData } = useQuery({
    queryKey: ['models'],
    queryFn: () => api.getModels(),
  })

  const projects = projectsData?.items || []
  const models = modelsData?.models || []

  const recentProjects = projects.slice(0, 4)
  const readyModels = models.filter((m: any) => m.status === 'ready').slice(0, 4)

  const stats = {
    totalProjects: projectsData?.total || 0,
    completedProjects: projects.filter((p: any) => p.status === 'completed').length,
    readyModels: models.filter((m: any) => m.status === 'ready').length,
    totalModels: models.length,
  }

  return (
    <div className="space-y-8">
      {/* Hero Greeting */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-violet-600 via-purple-600 to-indigo-700 p-8 text-white">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute -top-8 -right-8 h-64 w-64 rounded-full bg-white blur-3xl" />
          <div className="absolute -bottom-8 -left-8 h-48 w-48 rounded-full bg-white blur-3xl" />
        </div>
        <div className="relative">
          <div className="flex items-center gap-2 text-violet-200 text-sm font-medium mb-2">
            <Clapperboard className="h-4 w-4" />
            OiiOii.ai Clone
          </div>
          <h1 className="text-4xl font-bold mb-1">
            {getGreeting()}, director! 🎬
          </h1>
          <p className="text-violet-200 text-lg">
            What story will you bring to life today?
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button
              className="bg-white text-violet-700 hover:bg-violet-50 font-semibold shadow-lg"
              onClick={() => navigate('/canvas')}
            >
              <Wand2 className="h-4 w-4 mr-2" />
              Open AI Canvas
            </Button>
            <Button
              variant="outline"
              className="border-white/40 text-white hover:bg-white/10"
              onClick={() => navigate('/projects')}
            >
              <FolderKanban className="h-4 w-4 mr-2" />
              My Projects
            </Button>
          </div>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-500 dark:text-dark-400">Total Projects</p>
                <p className="text-3xl font-bold text-dark-900 dark:text-white">{stats.totalProjects}</p>
              </div>
              <div className="p-3 bg-violet-100 dark:bg-violet-900/30 rounded-xl">
                <FolderKanban className="h-6 w-6 text-violet-600 dark:text-violet-400" />
              </div>
            </div>
            <Button variant="ghost" size="sm" className="w-full mt-4" onClick={() => navigate('/projects')}>
              <ArrowRight className="h-4 w-4 mr-1" />
              View All
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-500 dark:text-dark-400">Completed Videos</p>
                <p className="text-3xl font-bold text-green-600 dark:text-green-400">{stats.completedProjects}</p>
              </div>
              <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-xl">
                <CheckCircle className="h-6 w-6 text-green-600 dark:text-green-400" />
              </div>
            </div>
            <Button variant="ghost" size="sm" className="w-full mt-4" onClick={() => navigate('/projects?status=completed')}>
              <ArrowRight className="h-4 w-4 mr-1" />
              View Completed
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-500 dark:text-dark-400">AI Models</p>
                <p className="text-3xl font-bold text-dark-900 dark:text-white">{stats.totalModels || 75}+</p>
              </div>
              <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-xl">
                <Cpu className="h-6 w-6 text-blue-600 dark:text-blue-400" />
              </div>
            </div>
            <Button variant="ghost" size="sm" className="w-full mt-4" onClick={() => navigate('/models')}>
              <ArrowRight className="h-4 w-4 mr-1" />
              Browse Models
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-500 dark:text-dark-400">Animation Styles</p>
                <p className="text-3xl font-bold text-dark-900 dark:text-white">150+</p>
              </div>
              <div className="p-3 bg-pink-100 dark:bg-pink-900/30 rounded-xl">
                <Sparkles className="h-6 w-6 text-pink-600 dark:text-pink-400" />
              </div>
            </div>
            <Button variant="ghost" size="sm" className="w-full mt-4" onClick={() => navigate('/canvas')}>
              <ArrowRight className="h-4 w-4 mr-1" />
              Explore Styles
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Quick Create Cards */}
      <div>
        <h2 className="text-xl font-bold text-dark-900 dark:text-white mb-4 flex items-center gap-2">
          <Wand2 className="h-5 w-5 text-violet-500" />
          Quick Create
        </h2>
        <div className="grid gap-3 grid-cols-2 md:grid-cols-4 lg:grid-cols-4">
          {QUICK_CREATE_CARDS.map((card) => {
            const Icon = card.icon
            return (
              <button
                key={card.id}
                onClick={() => navigate(card.route)}
                className={`group relative text-left rounded-xl p-4 ${card.bg} border border-transparent hover:border-violet-300 dark:hover:border-violet-600 transition-all duration-200 hover:shadow-md hover:-translate-y-0.5`}
              >
                <div className={`inline-flex p-2 rounded-lg bg-gradient-to-br ${card.color} mb-3`}>
                  <Icon className="h-5 w-5 text-white" />
                </div>
                <h3 className="font-semibold text-dark-900 dark:text-white text-sm mb-1">
                  {card.label}
                </h3>
                <p className="text-xs text-dark-500 dark:text-dark-400 leading-relaxed">
                  {card.description}
                </p>
                <ArrowRight className="absolute bottom-3 right-3 h-4 w-4 text-dark-300 group-hover:text-violet-500 transition-colors" />
              </button>
            )
          })}
        </div>
      </div>

      {/* Recent Activity + Sidebar */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recent Projects */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <FolderKanban className="h-5 w-5" />
              Recent Projects
            </CardTitle>
            <Button variant="ghost" size="sm" onClick={() => navigate('/projects')}>
              View All
              <ArrowRight className="h-3 w-3 ml-1" />
            </Button>
          </CardHeader>
          <CardContent>
            {recentProjects.length === 0 ? (
              <div className="text-center py-10">
                <Clapperboard className="h-12 w-12 text-dark-300 dark:text-dark-600 mx-auto mb-3" />
                <p className="text-dark-500 dark:text-dark-400 mb-1">No projects yet</p>
                <p className="text-xs text-dark-400 dark:text-dark-500 mb-4">
                  Pick a template above to create your first animation
                </p>
                <Button variant="outline" size="sm" onClick={() => navigate('/canvas')}>
                  <Plus className="h-3 w-3 mr-1" />
                  Open Canvas
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {recentProjects.map((project: any) => (
                  <div
                    key={project.id}
                    className="flex items-center gap-4 p-3 rounded-lg hover:bg-dark-50 dark:hover:bg-dark-800/50 transition-colors cursor-pointer"
                    onClick={() => navigate(`/projects/${project.id}`)}
                  >
                    <div className="relative h-16 w-16 rounded-lg bg-dark-100 dark:bg-dark-800 overflow-hidden flex-shrink-0 flex items-center justify-center">
                      {project.thumbnail_url ? (
                        <img src={project.thumbnail_url} alt={project.title} className="w-full h-full object-cover" />
                      ) : (
                        <Video className="h-8 w-8 text-dark-400" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-dark-900 dark:text-white truncate">{project.title}</p>
                      <p className="text-sm text-dark-500 dark:text-dark-400 truncate">
                        {project.prompt?.slice(0, 80)}...
                      </p>
                      <div className="flex items-center gap-3 mt-1 text-xs text-dark-400">
                        <span>{project.model}</span>
                        <span>{project.duration}s</span>
                        <span>{project.resolution}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {project.status === 'completed' && <Badge variant="success">Completed</Badge>}
                      {project.status === 'processing' && (
                        <Badge variant="warning">
                          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                          Processing
                        </Badge>
                      )}
                      {project.status === 'failed' && <Badge variant="destructive">Failed</Badge>}
                      {project.status === 'pending' && <Badge variant="secondary">Pending</Badge>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Ready Models */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Cpu className="h-5 w-5" />
                Ready Models
              </CardTitle>
              <Button variant="ghost" size="sm" onClick={() => navigate('/models')}>
                View All
              </Button>
            </CardHeader>
            <CardContent>
              {readyModels.length === 0 ? (
                <div className="text-center py-6">
                  <Cpu className="h-10 w-10 text-dark-300 dark:text-dark-600 mx-auto mb-3" />
                  <p className="text-dark-500 dark:text-dark-400 text-sm mb-1">75+ models available</p>
                  <p className="text-xs text-dark-400 dark:text-dark-500 mb-3">
                    Pollinations, Groq, Gemini & more
                  </p>
                  <Button variant="outline" size="sm" onClick={() => navigate('/models')}>
                    Browse Models
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {readyModels.map((model: any) => (
                    <div
                      key={model.id}
                      className="p-3 rounded-lg hover:bg-dark-50 dark:hover:bg-dark-800/50 transition-colors cursor-pointer"
                      onClick={() => navigate(`/canvas?model=${model.id}`)}
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-violet-100 dark:bg-violet-900/30 rounded-lg">
                          {model.category === 'llm' && <Brain className="h-4 w-4 text-violet-600" />}
                          {model.category === 'video' && <Video className="h-4 w-4 text-violet-600" />}
                          {model.category === 'image' && <Image className="h-4 w-4 text-violet-600" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-dark-900 dark:text-white truncate text-sm">{model.name}</p>
                          <p className="text-xs text-dark-500 truncate">{model.id}</p>
                        </div>
                        <Badge variant="success" className="text-xs">Ready</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Free Tier Resources */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BookOpen className="h-5 w-5" />
                Free-Tier Providers
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <a href="https://pollinations.ai" target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-3 p-2 rounded-lg hover:bg-dark-50 dark:hover:bg-dark-800/50 transition-colors">
                <ExternalLink className="h-5 w-5 text-violet-600" />
                <div>
                  <span className="text-sm font-medium text-dark-700 dark:text-dark-300">Pollinations.ai</span>
                  <p className="text-xs text-dark-500">Keyless image & video generation</p>
                </div>
              </a>
              <a href="https://console.groq.com" target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-3 p-2 rounded-lg hover:bg-dark-50 dark:hover:bg-dark-800/50 transition-colors">
                <ExternalLink className="h-5 w-5 text-blue-600" />
                <div>
                  <span className="text-sm font-medium text-dark-700 dark:text-dark-300">Groq Console</span>
                  <p className="text-xs text-dark-500">Ultra-fast LLM inference (free tier)</p>
                </div>
              </a>
              <a href="https://aistudio.google.com" target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-3 p-2 rounded-lg hover:bg-dark-50 dark:hover:bg-dark-800/50 transition-colors">
                <ExternalLink className="h-5 w-5 text-green-600" />
                <div>
                  <span className="text-sm font-medium text-dark-700 dark:text-dark-300">Google AI Studio</span>
                  <p className="text-xs text-dark-500">Gemini models — free quota</p>
                </div>
              </a>
              <a href="https://openrouter.ai" target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-3 p-2 rounded-lg hover:bg-dark-50 dark:hover:bg-dark-800/50 transition-colors">
                <ExternalLink className="h-5 w-5 text-orange-600" />
                <div>
                  <span className="text-sm font-medium text-dark-700 dark:text-dark-300">OpenRouter</span>
                  <p className="text-xs text-dark-500">100+ models via unified API</p>
                </div>
              </a>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}