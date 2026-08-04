'use client';

import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, 
  Send, 
  Mic, 
  MicOff, 
  RotateCcw, 
  Copy, 
  Check, 
  X,
  Sparkles,
  MessageSquare,
  Zap,
  Settings
} from 'lucide-react';
import { Button, Card, CardHeader, CardContent, Input, Label, Select, SelectTrigger, SelectValue, SelectContent, SelectItem, Toaster, toast } from '@/components/ui';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'agent';
  content: string;
  agent?: string;
  timestamp: Date;
  status?: 'sending' | 'sent' | 'error';
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
  mode: 'smart' | 'chat';
}

const CHAT_API = '/api/v1/chat';

const ChatMode: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Welcome to OiiOii.ai Chat Mode! I'm your creative director. How can I help you create an animated story today? You can:\n\n• Describe a story idea and I'll guide the 7-agent team\n• Ask me to refine specific elements (characters, scenes, style)\n• Request re-generation of any agent's output\n• Get creative suggestions and feedback\n\nWhat's your story idea?",
      timestamp: new Date()
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [agentProgress, setAgentProgress] = useState<Record<string, number>>({});
  const [mode, setMode] = useState<'smart' | 'chat'>('chat');
  const [selectedModel, setSelectedModel] = useState('gemini-2.5-flash');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  // Scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Fetch chat sessions
  const { data: sessions } = useQuery({
    queryKey: ['chat-sessions'],
    queryFn: async () => {
      try {
        const { data } = await axios.get(`${CHAT_API}/sessions`);
        return data;
      } catch {
        return [];
      }
    }
  });

  // Send message mutation
  const sendMessageMutation = useMutation({
    mutationFn: async ({ message, sessionId }: { message: string; sessionId?: string }) => {
      const { data } = await axios.post(`${CHAT_API}/send`, { message, sessionId, mode });
      return data;
    },
    onSuccess: (response) => {
      // Handle agent streaming updates
      if (response.agentUpdates) {
        response.agentUpdates.forEach((update: any) => {
          setAgentProgress(prev => ({ ...prev, [update.agent]: update.progress }));
          if (update.status === 'running') {
            setActiveAgent(update.agent);
          }
        });
      }
    }
  });

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date(),
      status: 'sent'
    };
    
    setMessages(prev => [...prev, userMessage]);
    const currentInput = input;
    setInput('');
    setIsLoading(true);
    
    try {
      const response = await sendMessageMutation.mutateAsync({ message: currentInput });
      
      // Add assistant response
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.content || 'Processing...',
        timestamp: new Date(),
        status: 'sent'
      };
      
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      toast.error('Failed to send message');
      // Add error message
      setMessages(prev => [...prev, {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
        status: 'error'
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleAgentAction = async (action: string, agentName: string) => {
    setActiveAgent(agentName);
    setAgentProgress(prev => ({ ...prev, [agentName]: 0 }));
    
    // Simulate agent action
    for (let i = 0; i <= 100; i += 10) {
      setAgentProgress(prev => ({ ...prev, [agentName]: i }));
      await new Promise(r => setTimeout(r, 200));
    }
    
    // Add result message
    setMessages(prev => [...prev, {
      id: `agent-${Date.now()}`,
      role: 'agent',
      content: `${agentName} has completed: ${action}`,
      agent: agentName,
      timestamp: new Date()
    }]);
    
    setActiveAgent(null);
  };

  const handleNewChat = () => {
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: "New chat started! What would you like to create today?",
        timestamp: new Date()
      }
    ]);
  };

  const AGENTS = [
    { name: 'Scriptwriter', action: 'Write/Refine Script', description: 'Story structure, dialogue, scenes' },
    { name: 'Art Director', action: 'Define Visual Style', description: 'Color palette, lighting, mood' },
    { name: 'Character Designer', action: 'Design Characters', description: 'Appearance, expressions, consistency' },
    { name: 'Scene Designer', action: 'Design Scenes', description: 'Environments, backgrounds, composition' },
    { name: 'Storyboard Artist', action: 'Create Storyboard', description: 'Panel layout, camera angles' },
    { name: 'Animator', action: 'Animate Scenes', description: 'Motion, timing, camera movement' },
    { name: 'Sound Director', action: 'Design Audio', description: 'Music, SFX, voice lines' },
    { name: 'Director', action: 'Final Review', description: 'Approval, final cut, export' },
  ];

  return (
    <div className="flex h-screen bg-[#0a0a0f] text-slate-100">
      {/* Sidebar */}
      <aside className="w-80 border-r border-slate-800 bg-[#0c0d14] flex flex-col">
        <div className="p-4 border-b border-slate-800">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-6 h-6 text-cyan-400" />
            <h2 className="font-bold text-lg">Chat Mode</h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">Conversational agent control</p>
        </div>

        {/* Mode Selector */}
        <div className="p-4 border-b border-slate-800">
          <div className="flex space-x-2">
            <Button 
              variant={mode === 'smart' ? 'default' : 'outline'} 
              onClick={() => setMode('smart')}
              className="flex-1"
            >
              <Zap className="mr-2 h-3 w-3" />
              <span className="text-xs">Smart</span>
            </Button>
            <Button 
              variant={mode === 'chat' ? 'default' : 'outline'} 
              onClick={() => setMode('chat')}
              className="flex-1"
            >
              <MessageSquare className="mr-2 h-3 w-3" />
              <span className="text-xs">Chat</span>
            </Button>
          </div>
          <p className="text-xs text-slate-400 mt-2 text-center">
            {mode === 'smart' 
              ? 'One-click full pipeline execution' 
              : 'Step-by-step conversational control'}
          </p>
        </div>

        {/* Model Selector */}
        <div className="p-4 border-b border-slate-800">
          <Label className="text-xs font-semibold text-slate-300 mb-2 block">Model</Label>
          <Select value={selectedModel} onValueChange={setSelectedModel}>
            <SelectTrigger>
              <SelectValue placeholder="Select model..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="gemini-2.5-flash">Gemini 2.5 Flash</SelectItem>
              <SelectItem value="llama-3.3-70b">Llama 3.3 70B</SelectItem>
              <SelectItem value="claude-3-5-sonnet">Claude 3.5 Sonnet</SelectItem>
              <SelectItem value="mixtral-8x7b">Mixtral 8x7B</SelectItem>
              <SelectItem value="qwen-2.5-72b">Qwen 2.5 72B</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Agent Quick Actions */}
        <div className="flex-1 p-4 overflow-y-auto">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Quick Agent Actions</h3>
          <div className="space-y-2">
            {AGENTS.map((agent) => (
              <Button
                key={agent.name}
                variant="outline"
                size="sm"
                className="w-full justify-start text-left px-3 py-2"
                onClick={() => handleAgentAction(agent.action, agent.name)}
                disabled={isLoading}
              >
                <div className="flex items-center space-x-2 w-full">
                  <Bot className="h-4 w-4 text-indigo-400" />
                  <div className="flex-1 text-left">
                    <p className="text-xs font-medium">{agent.name}</p>
                    <p className="text-[10px] text-slate-400">{agent.description}</p>
                  </div>
                  {agentProgress[agent.name] !== undefined && agentProgress[agent.name] > 0 && (
                    <div className="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-indigo-500 transition-all duration-300"
                        style={{ width: `${agentProgress[agent.name]}%` }}
                      />
                    </div>
                  )}
                </div>
              </Button>
            ))}
          </div>
        </div>

        {/* Session History */}
        <div className="p-4 border-t border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-slate-300">Recent Chats</h3>
            <Button variant="ghost" size="icon" onClick={handleNewChat} className="h-6 w-6">
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {sessions?.slice(0, 5).map((session: any) => (
              <button
                key={session.id}
                className="w-full text-left p-2 rounded text-xs text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
                onClick={() => {
                  // Load session
                }}
              >
                {session.title}
              </button>
            ))}
            {!sessions?.length && (
              <p className="text-xs text-slate-500 text-center py-4">No recent chats</p>
            )}
          </div>
        </div>
      </aside>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Chat Header */}
        <header className="border-b border-slate-800 bg-[#0d0e15]/90 backdrop-blur-md px-6 py-3 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Bot className="w-6 h-6 text-cyan-400" />
            <div>
              <h2 className="font-semibold">Creative Director</h2>
              <p className="text-xs text-slate-400">
                {activeAgent ? `${activeAgent} is working...` : 'Ready to assist'}
              </p>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            {activeAgent && (
              <div className="flex items-center space-x-2 px-3 py-1 bg-indigo-600/20 border border-indigo-500/30 rounded-full">
                <Bot className="h-3 w-3 text-indigo-400" />
                <span className="text-xs font-medium text-indigo-300">{activeAgent}</span>
                <div className="w-20 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-indigo-500 animate-pulse"
                    style={{ width: `${agentProgress[activeAgent] || 0}%` }}
                  />
                </div>
              </div>
            )}
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <Settings className="h-4 w-4" />
            </Button>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((message) => (
            <div 
              key={message.id} 
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`max-w-[70%] ${message.role === 'user' ? 'order-2' : 'order-1'}`}>
                <div className={`flex items-start space-x-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
                  <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${message.role === 'user' ? 'bg-slate-700' : 'bg-indigo-600'}`}>
                    {message.role === 'user' ? (
                      <span className="text-xs font-bold">U</span>
                    ) : message.role === 'agent' ? (
                      <Bot className="h-4 w-4 text-white" />
                    ) : (
                      <Sparkles className="h-4 w-4 text-white" />
                    )}
                  </div>
                  
                  <div className={`max-w-full ${message.role === 'user' ? 'text-right' : ''}`}>
                    {(message.role === 'assistant' || message.role === 'agent') && (
                      <p className="text-xs text-slate-400 mb-1">
                        {message.agent ? `${message.agent} • ` : ''}Assistant
                      </p>
                    )}
                    
                    <div 
                      className={`rounded-2xl p-4 ${
                        message.role === 'user' 
                          ? 'bg-indigo-600 text-white rounded-br-none' 
                          : message.role === 'agent'
                            ? 'bg-indigo-600/20 border border-indigo-500/30 text-slate-100 rounded-bl-none'
                            : 'bg-slate-800 text-slate-100 rounded-bl-none'
                      }`}
                    >
                      <p className="whitespace-pre-wrap text-sm">{message.content}</p>
                    </div>
                    
                    <p className={`text-[10px] text-slate-500 mt-1 ${message.role === 'user' ? 'text-right' : ''}`}>
                      {message.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ))}
          
          {isLoading && (
            <div className="flex justify-start">
              <div className="max-w-[70%]">
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center">
                    <Sparkles className="h-4 w-4 text-white" />
                  </div>
                  <div className="bg-slate-800 rounded-2xl rounded-bl-none p-4">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="border-t border-slate-800 bg-[#0d0e15]/90 backdrop-blur-md p-4">
          <div className="flex items-end space-x-3">
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Message the Creative Director... (Enter to send, Shift+Enter for new line)"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 pr-12 text-sm text-slate-200 focus:outline-none focus:border-cyan-500/60 resize-none min-h-[50px] max-h-48"
                rows={1}
              />
            </div>
            <Button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              size="icon"
              className="h-10 w-10 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50"
            >
              <Send className="h-5 w-5" />
            </Button>
          </div>
          <p className="text-[10px] text-slate-500 text-center mt-2">
            {mode === 'smart' 
              ? 'Smart Mode: One-click full pipeline. Describe your idea and watch the team work.'
              : 'Chat Mode: Guide each agent step by step. Ask for refinements, re-generations, or creative input.'}
          </p>
        </div>
      </div>
    </div>
  );
};

export default ChatMode;