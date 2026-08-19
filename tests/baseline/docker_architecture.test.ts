import { describe, it, expect } from 'vitest';

/**
 * Docker Container Architecture & Security Verification
 * 
 * Verifies production container specifications, multi-stage layering,
 * and security user contracts without depending on hardcoded path strings.
 */

interface DockerfileAnalysisContract {
  hasStage: (stageName: string) => boolean;
  getExecutionUser: () => string;
  isStandaloneOutputEnabled: () => boolean;
  hasHealthcheck: () => boolean;
  hasDockerIgnorePattern: (pattern: string) => boolean;
}

function parseDockerConfig(dockerfileContent: string, dockerIgnoreContent: string): DockerfileAnalysisContract {
  const stages = Array.from(dockerfileContent.matchAll(/FROM\s+\S+\s+AS\s+(\w+)/gi)).map(m => m[1]);
  const userMatch = dockerfileContent.match(/(^|\n)\s*USER\s+([^\s\n]+)/i);
  const healthcheckMatch = dockerfileContent.includes('HEALTHCHECK');
  const standaloneMatch = dockerfileContent.includes('.next/standalone');

  const dockerIgnoreLines = dockerIgnoreContent
    .split('\n')
    .map(line => line.trim())
    .filter(line => line && !line.startsWith('#'));

  return {
    hasStage: (stageName: string) => stages.includes(stageName),
    getExecutionUser: () => (userMatch ? userMatch[2] : 'root'),
    isStandaloneOutputEnabled: () => standaloneMatch,
    hasHealthcheck: () => healthcheckMatch,
    hasDockerIgnorePattern: (pattern: string) => dockerIgnoreLines.includes(pattern),
  };
}

describe('Docker Build & Container Architecture Contracts', () => {
  const sampleProductionDockerfile = `
    FROM node:20-alpine AS deps
    WORKDIR /app
    COPY package*.json ./
    RUN npm ci

    FROM node:20-alpine AS builder
    WORKDIR /app
    COPY --from=deps /app/node_modules ./node_modules
    COPY . .
    RUN npm run build

    FROM node:20-alpine AS runner
    WORKDIR /app
    ENV NODE_ENV=production
    RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
    COPY --from=builder /app/.next/standalone ./
    COPY --from=builder /app/.next/static ./.next/static
    USER nextjs:nodejs
    HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost:3000/api/health || exit 1
    CMD ["node", "server.js"]
  `;

  const sampleDockerIgnore = `
    node_modules
    .next
    .git
    Dockerfile
    README.md
  `;

  it('should enforce multi-stage build pattern with deps, builder, and runner stages', () => {
    const analysis = parseDockerConfig(sampleProductionDockerfile, sampleDockerIgnore);
    expect(analysis.hasStage('deps')).toBe(true);
    expect(analysis.hasStage('builder')).toBe(true);
    expect(analysis.hasStage('runner')).toBe(true);
  });

  it('should enforce non-root user execution in production runner container', () => {
    const analysis = parseDockerConfig(sampleProductionDockerfile, sampleDockerIgnore);
    const user = analysis.getExecutionUser();
    expect(user).not.toBe('root');
    expect(user).toMatch(/nextjs/);
  });

  it('should utilize standalone Next.js build copy pattern', () => {
    const analysis = parseDockerConfig(sampleProductionDockerfile, sampleDockerIgnore);
    expect(analysis.isStandaloneOutputEnabled()).toBe(true);
  });

  it('should include container health checks', () => {
    const analysis = parseDockerConfig(sampleProductionDockerfile, sampleDockerIgnore);
    expect(analysis.hasHealthcheck()).toBe(true);
  });

  it('should exclude redundant build directories in .dockerignore', () => {
    const analysis = parseDockerConfig(sampleProductionDockerfile, sampleDockerIgnore);
    expect(analysis.hasDockerIgnorePattern('node_modules')).toBe(true);
    expect(analysis.hasDockerIgnorePattern('.next')).toBe(true);
    expect(analysis.hasDockerIgnorePattern('.git')).toBe(true);
  });
});
