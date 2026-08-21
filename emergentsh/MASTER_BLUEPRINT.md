# MASTER_BLUEPRINT.md — Production Repair & Hardening Roadmap

## Phase 1: Next.js Production Build & Hydration Fixes
1. **Configure Standalone Output in `frontend/next.config.js`:**
   ```javascript
   /** @type {import('next').NextConfig} */
   const nextConfig = {
     output: 'standalone',
     reactStrictMode: true,
     async rewrites() {
       return [
         {
           source: '/api/:path*',
           destination: process.env.BACKEND_API_URL || 'http://localhost:8000/api/:path*',
         },
       ];
     },
   };
   module.exports = nextConfig;
   ```
2. **Fix Client Component Hydration Mismatch in `frontend/src/app/workspace/page.tsx`:**
   - Wrap timestamp rendering in a `mounted` state check or `useEffect` to ensure identical initial SSR/CSR markup:
   ```tsx
   const [mounted, setMounted] = useState(false);
   useEffect(() => { setMounted(true); }, []);
   // Render:
   {mounted ? activity.timestamp.toLocaleTimeString() : null}
   ```

## Phase 2: Multi-Stage Production Docker Container Architecture
1. **Create Optimized `frontend/Dockerfile`:**
   ```dockerfile
   FROM node:20-alpine AS base

   FROM base AS deps
   RUN apk add --no-cache libc6-compat
   WORKDIR /app
   COPY package.json package-lock.json* ./
   RUN npm ci

   FROM base AS builder
   WORKDIR /app
   COPY --from=deps /app/node_modules ./node_modules
   COPY . .
   ENV NEXT_TELEMETRY_DISABLED 1
   RUN npm run build

   FROM base AS runner
   WORKDIR /app
   ENV NODE_ENV production
   ENV NEXT_TELEMETRY_DISABLED 1
   RUN addgroup --system --gid 1001 nodejs
   RUN adduser --system --uid 1001 nextjs
   COPY --from=builder /app/public ./public
   COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
   COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
   USER nextjs
   EXPOSE 3000
   ENV PORT 3000
   CMD ["node", "server.js"]
   ```

2. **Create Production `docker-compose.yml` for Platform Stack:**
   - Standardize service names (`backend`, `frontend`, `preview_proxy`).
   - Wire explicit environment variables (`NIM_API_KEY`, `NVIDIA_API_KEY`).
   - Disallow silent mock degradation when `NIM_STRICT_MODE=true`.

## Phase 3: Real Agent Progress SSE Wiring
1. **Update `backend/app/api/pipeline.py`:**
   - Provide a Server-Sent Events (SSE) streaming route (`/api/pipeline/stream/{job_id}`) yielding JSON chunks for every agent event (`agent_start`, `agent_done`, `token_delta`).
2. **Update Workspace Frontend:**
   - Replace fake `setInterval` timers in `frontend/src/app/workspace/page.tsx` with an `EventSource` listening to `/api/pipeline/stream/{job_id}`.

## Phase 4: Strict NIM Exclusivity & Code Verification
1. **Enforce Strict NIM Provider Exception Handling:**
   - Remove automatic fallbacks to `_make_mock_client()` in production mode (`NIM_STRICT_MODE=1`).
   - Raise explicit `NIMInferenceError` if `NIM_API_KEY` is missing or invalid.
2. **Code AST Verification:**
   - Pass all generated Python files through `ast.parse()` and JavaScript/TypeScript files through basic syntax validation before saving artifacts.