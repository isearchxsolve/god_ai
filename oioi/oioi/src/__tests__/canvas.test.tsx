import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// React Flow requires ResizeObserver + DOM measurement not available in jsdom,
// so stub the canvas surface. The panels, tabs, and data wiring are what we
// actually exercise here.
jest.mock('@xyflow/react', () => {
  const actual = jest.requireActual('@xyflow/react');
  return {
    ...actual,
    ReactFlow: ({ children }: { children?: React.ReactNode }) => (
      <div data-testid="react-flow">{children}</div>
    ),
    ReactFlowProvider: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    Handle: () => null,
    applyNodeChanges: (changes: unknown[], nodes: unknown[]) => nodes,
    applyEdgeChanges: (changes: unknown[], edges: unknown[]) => edges,
    addEdge: (edge: unknown, edges: unknown[]) => [...edges, edge],
  };
});

// Stub the canvas stylesheet (CSS imports are side-effect only).
jest.mock('@xyflow/react/dist/style.css', () => ({}));

import Home from '../app/page';

const mockModels = {
  categories: ['Video', 'Image', 'LLM'],
  counts: { Video: 26, Image: 26, LLM: 25, Total: 77 },
  video_models: [
    { id: 'kenburns-frames', display_name: 'Ken Burns Motion', name: 'Ken Burns', category: 'Video', provider: 'local', url: '', capabilities: [] },
  ],
  image_models: [
    { id: 'flux', display_name: 'Flux', name: 'Flux', category: 'Image', provider: 'pollinations', url: '', capabilities: [] },
  ],
  llm_models: [
    { id: 'google/gemma-4-26b-a4b-it:free', display_name: 'Gemma 4 26B (Free)', name: 'Gemma', category: 'LLM', provider: 'openrouter', url: '', capabilities: [] },
  ],
};

const mockStyles = {
  styles: [
    { id: 'anime-ghibli', name: 'Ghibli Style', category: 'Anime', thumbnail: '', previewUrl: '', promptSuffix: '', negativePrompt: '', isBuiltIn: true },
  ],
  total: 160,
  counts: {},
};

const mockHealth = {
  status: 'healthy',
  active_providers: 2,
  providers: [
    { name: 'openrouter', priority: 0, capabilities: ['chat'], status: 'healthy', latency_ms: 100, consecutive_failures: 0, in_cooldown: false },
    { name: 'pollinations', priority: 6, capabilities: ['image'], status: 'healthy', latency_ms: 50, consecutive_failures: 0, in_cooldown: false },
  ],
};

beforeEach(() => {
  global.fetch = jest.fn((url: string) => {
    const u = String(url);
    if (u.includes('/models/')) return Promise.resolve({ ok: true, json: () => Promise.resolve(mockModels) } as Response);
    if (u.includes('/styles/')) return Promise.resolve({ ok: true, json: () => Promise.resolve(mockStyles) } as Response);
    if (u.includes('/providers/health')) return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealth) } as Response);
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response);
  }) as jest.Mock;
});

afterEach(() => {
  jest.clearAllMocks();
});

describe('OiiOii Studio — wired frontend', () => {
  it('renders the studio shell with title and tabs', async () => {
    render(<Home />);
    expect(screen.getByText(/OiiOii Studio/i)).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Create/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Film/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Chat/i })).toBeInTheDocument();
  });

  it('shows the empty-canvas hint before any nodes exist', () => {
    render(<Home />);
    expect(screen.getByText(/Your animation canvas is empty/i)).toBeInTheDocument();
  });

  it('loads real models and styles into the Create panel', async () => {
    render(<Home />);
    // Model select should populate from the mocked registry.
    await waitFor(() => {
      expect(screen.getByText(/Auto \(best available\)/i)).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText(/Flux · pollinations/i)).toBeInTheDocument();
    });
    // Style select should show the style count from the registry.
    await waitFor(() => {
      expect(screen.getByText(/Style \(160\)/i)).toBeInTheDocument();
    });
  });

  it('shows live provider health badges in the top bar', async () => {
    render(<Home />);
    await waitFor(() => {
      expect(screen.getByText(/openrouter/i)).toBeInTheDocument();
      expect(screen.getByText(/pollinations/i)).toBeInTheDocument();
    });
  });

  it('switches to the Film (pipeline) tab and shows the agent runner', () => {
    render(<Home />);
    fireEvent.click(screen.getByRole('tab', { name: /Film/i }));
    expect(screen.getByText(/Film Idea/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Run 7-Agent Pipeline/i })).toBeInTheDocument();
  });

  it('switches to the Chat tab and shows the streaming chat panel', () => {
    render(<Home />);
    fireEvent.click(screen.getByRole('tab', { name: /Chat/i }));
    expect(screen.getByText(/Director Chat/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Send/i })).toBeInTheDocument();
  });
});
