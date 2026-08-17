
--- SpecializedAgent ---
class SpecializedAgent:
    """Base class for all generation-layer agents.

    Each agent holds a tightly-scoped system prompt and calls the
    existing NIM provider pool for inference — no new HTTP clients.
    """
    role: str = 'agent'
    _system_prompt: str = 'You are a senior software engineer.'

    def __init__(self, pool: 'ProviderPool', config: Dict[str, Any]) -> None:
        self.pool = pool
        self.config = config

    def _call_nim(self, messages: List[Dict[str, str]], max_tokens: int=8192) -> str:
        """Synchronous NIM call through the existing provider pool."""
        if not HAS_OPENAI:
            return f'# {self.role} output\n# openai package not available\n'
        for attempt in range(8):
            provider = None
            for _ in range(30):
                provider = self.pool.next_available()
                if provider:
                    break
                time.sleep(2.0)
            if not provider:
                raise RuntimeError(f'[{self.role}] No NIM provider available after 60 s')
            model_cfg = provider.model_cfg
            payload: Dict[str, Any] = {'model': model_cfg['id'], 'messages': messages, 'max_tokens': max_tokens, 'stream': False}
            if model_cfg.get('temperature') is not None:
                payload['temperature'] = model_cfg['temperature']
            if model_cfg.get('top_p') is not None:
                payload['top_p'] = model_cfg['top_p']
            try:
                resp = provider.client.chat.completions.create(**payload)
                if not getattr(resp, 'choices', None):
                    raise RuntimeError(f'Empty choices in response from {provider.name}')
                provider.record_success()
                return (resp.choices[0].message.content or '').strip()
            except OPENAI_ERRORS as e:
                err_str = str(e).lower()
                if '429' in err_str or 'rate' in err_str:
                    provider.record_failure(cooldown=self.config.get('post_429_backoff', 25.0))
                    self.pool.propagate_shared_cooldown(provider, self.config.get('post_429_backoff', 25.0))
                    time.sleep(5.0 * (attempt + 1))
                elif '404' in err_str or '410' in err_str:
                    provider.record_failure(permanent=True)
                else:
                    provider.record_failure()
                    time.sleep(2.0)
            except (IndexError, AttributeError, KeyError, RuntimeError) as e:
                provider.record_failure()
                time.sleep(2.0)
        raise RuntimeError(f'[{self.role}] All NIM attempts exhausted')

    def _messages(self, user_content: str) -> List[Dict[str, str]]:
        return [{'role': 'system', 'content': self._system_prompt}, {'role': 'user', 'content': user_content}]

    def run(self, ctx: Dict[str, Any]) -> Dict[str, str]:
        """Run the agent. Returns {rel_path: content} of files to write."""
        raise NotImplementedError
--- PlannerAgent ---
class PlannerAgent(SpecializedAgent):
    role = 'planner'
    _system_prompt = 'You are a senior software architect writing a project plan.\nOutput ONLY the content of PLAN.md — a markdown document with exactly these sections:\n## Requirements\n## Risks\n## Acceptance Criteria\n\nBe specific, actionable, and technical. No preamble, no code blocks wrapping the markdown. Never wrap your output in ``` fences of any kind — output raw markdown text only, starting directly with the first heading.'

    def run(self, ctx: Dict[str, Any]) -> Dict[str, str]:
        prompt = f"Project: {ctx['project_name']}\nStack: {ctx['stack']}\nDescription: {ctx['description']}\n\nWrite PLAN.md with sections: Requirements, Risks, Acceptance Criteria."
        content = self._call_nim(self._messages(prompt), max_tokens=4096)
        return {'PLAN.md': content}
--- ArchitectAgent ---
class ArchitectAgent(SpecializedAgent):
    role = 'architect'
    _BACKEND_ROOT_BY_STACK = {'fastapi-react': 'backend/ (module path: backend.main, backend.routers, backend.models)', 'flutter-fastapi': 'backend/ (module path: backend.main, backend.routers, backend.models)', 'nextjs-postgres': 'app/ (Next.js 14 App Router — app/api/.../route.ts)', 'expo-node': 'server/ (Express — server/routes/*.js)'}
    _system_prompt = 'You are a senior software architect writing ARCHITECTURE.md.\nOutput ONLY the markdown document with these sections:\n## Components\n## Data Flow\n## Tech Stack\n## API Surface\n\nBe specific about module names, file paths, and data schemas. CRITICAL: the backend package root and its exact path/module convention will be given to you in the prompt — you MUST use that exact root for every backend file path and import example you write. Do not invent or default to any other root (never use app/main.py unless told to). Every other agent in this pipeline (backend, database, tests, deployment) hardcodes this same root, so any deviation here breaks the entire generated project. Never wrap your output in ``` fences of any kind — output raw markdown text only, starting directly with the first heading.'

    def run(self, ctx: Dict[str, Any]) -> Dict[str, str]:
        plan = ctx.get('PLAN.md', 'No plan yet.')
        stack = ctx['stack']
        backend_root = self._BACKEND_ROOT_BY_STACK.get(stack, 'backend/ (module path: backend.main)')
        prompt = f"Project: {ctx['project_name']} ({stack})\nDescription: {ctx['description']}\n\nPLAN.md:\n{plan[:3000]}\n\nMANDATORY backend package root for this stack: {backend_root}\nUse this exact root for every backend file path, import statement, and module reference in the document. Do not use any other backend root.\n\nWrite ARCHITECTURE.md with sections: Components, Data Flow, Tech Stack, API Surface."
        content = self._call_nim(self._messages(prompt), max_tokens=4096)
        return {'ARCHITECTURE.md': content}
--- DesignerAgent ---
class DesignerAgent(SpecializedAgent):
    role = 'designer'
    _system_prompt = 'You are a senior UI/UX designer and frontend engineer.\nOutput ONLY valid TypeScript/JavaScript/Dart code — no markdown fences, no explanations.\nDesign a clean, modern dark-mode color theme and component system for the given project.'

    def run(self, ctx: Dict[str, Any]) -> Dict[str, str]:
        stack = ctx['stack']
        if stack == 'fastapi-react':
            prompt = f"Project: {ctx['project_name']}\nDescription: {ctx['description']}\n\nWrite frontend/src/theme.ts — a TypeScript module exporting a COLORS object and a TYPOGRAPHY object. Use a professional dark-mode palette with primary=#38bdf8, background=#0f172a, surface=#1e293b, text=#e2e8f0, muted=#94a3b8, danger=#fb7185, success=#4ade80. No imports needed. Export as: export const COLORS = {{{{...}}}}; export const TYPOGRAPHY = {{{{...}}}};"
            out = self._call_nim(self._messages(prompt), max_tokens=2048)
            return {'frontend/src/theme.ts': out}
        elif stack == 'nextjs-postgres':
            prompt = f"Project: {ctx['project_name']}\nDescription: {ctx['description']}\n\nWrite lib/theme.ts — a TypeScript module exporting a COLORS object and a TYPOGRAPHY object. Use a professional dark-mode palette with primary=#38bdf8, background=#0f172a, surface=#1e293b, text=#e2e8f0, muted=#94a3b8, danger=#fb7185, success=#4ade80. No imports needed. Export as: export const COLORS = {{{{...}}}}; export const TYPOGRAPHY = {{{{...}}}};"
            out = self._call_nim(self._messages(prompt), max_tokens=2048)
            return {'lib/theme.ts': out}
        elif stack == 'flutter-fastapi':
            prompt = f"Project: {ctx['project_name']}\n\nWrite lib/theme.dart — a Flutter file that defines AppTheme with a dark ThemeData. Primary color #38bdf8, background #0f172a. Export: class AppTheme {{{{ static ThemeData dark() {{{{...}}}} }}}}"
            out = self._call_nim(self._messages(prompt), max_tokens=2048)
            return {'lib/theme.dart': out}
        else:
            return {}
--- FrontendAgent ---
class FrontendAgent(SpecializedAgent):
    role = 'frontend'
    _system_prompt = 'You are a senior frontend engineer. Output ONLY valid source code — no markdown fences.\nWrite complete, working components. Never write TODO stubs or placeholder implementations.\nUse the dark color system: primary=#38bdf8, bg=#0f172a, surface=#1e293b.'

    def run(self, ctx: Dict[str, Any]) -> Dict[str, str]:
        stack = ctx['stack']
        arch = ctx.get('ARCHITECTURE.md', '')[:2000]
        results: Dict[str, str] = {}
        if stack == 'fastapi-react':
            prompt = f"Project: {ctx['project_name']}\nDescription: {ctx['description']}\nArchitecture:\n{arch}\n\nWrite frontend/src/components/ProjectCard.tsx — a React component that accepts a project object {{{{id, name, description, status, created_at}}}} as props and renders a polished dark-mode card. Include hover effects via inline style state. Export as: export default function ProjectCard({{{{ project }}}}: {{{{ project: any }}}}) {{{{...}}}}"
            results['frontend/src/components/ProjectCard.tsx'] = self._call_nim(self._messages(prompt), max_tokens=3000)
            prompt2 = f"Project: {ctx['project_name']}\n\nWrite frontend/src/components/ChatPanel.tsx — a React component for an AI chat interface. It should have a messages list area (scrollable), a text input at the bottom, and a Send button. State: messages array, input string. Each message has {{{{role: 'user'|'assistant', content: string}}}}. Assistant messages render in #1e293b bubbles, user messages in #38bdf8 bubbles. Export as: export default function ChatPanel() {{{{...}}}}"
            results['frontend/src/components/ChatPanel.tsx'] = self._call_nim(self._messages(prompt2), max_tokens=3000)
        elif stack == 'nextjs-postgres':
            prompt = f"Project: {ctx['project_name']}\nDescription: {ctx['description']}\nArchitecture:\n{arch}\n\nWrite components/ProjectCard.tsx — a React Server/Client component that accepts a project object {{{{id, name, description, status, created_at}}}} as props and renders a polished dark-mode card. Include hover effects via inline style state. Add 'use client' at the top if it uses hooks/state. Export as: export default function ProjectCard({{{{ project }}}}: {{{{ project: any }}}}) {{{{...}}}}"
            results['components/ProjectCard.tsx'] = self._call_nim(self._messages(prompt), max_tokens=3000)
            prompt2 = f"Project: {ctx['project_name']}\n\nWrite components/ChatPanel.tsx — a React Client Component for an AI chat interface. Start with 'use client'. It should have a messages list area (scrollable), a text input at the bottom, and a Send button. State: messages array, input string. Each message has {{{{role: 'user'|'assistant', content: string}}}}. Assistant messages render in #1e293b bubbles, user messages in #38bdf8 bubbles. Export as: export default function ChatPanel() {{{{...}}}}"
            results['components/ChatPanel.tsx'] = self._call_nim(self._messages(prompt2), max_tokens=3000)
        elif stack == 'flutter-fastapi':
            prompt = f"Project: {ctx['project_name']}\n\nWrite lib/widgets/project_card.dart — a Flutter StatelessWidget that renders a dark-mode project card given name, description, and status strings. Use Card, ListTile, and Chip widgets. Export: class ProjectCard extends StatelessWidget {{{{...}}}}"
            results['lib/widgets/project_card.dart'] = self._call_nim(self._messages(prompt), max_tokens=2000)
        elif stack == 'expo-node':
            prompt = f"Project: {ctx['project_name']}\n\nWrite app/components/ProjectCard.tsx — a React Native component that renders a project card (name, description, status) using View, Text, and StyleSheet. Dark background #1e293b, primary #38bdf8. Export as: export default function ProjectCard({{{{ project }}}}: {{{{ project: any }}}}) {{{{...}}}}"
            results['app/components/ProjectCard.tsx'] = self._call_nim(self._messages(prompt), max_tokens=2000)
        return results
--- BackendAgent ---
class BackendAgent(SpecializedAgent):
    role = 'backend'
    _system_prompt = 'You are a senior backend engineer. Output ONLY valid Python or JavaScript source code — no markdown fences.\nWrite complete, working implementations — never placeholder functions or TODO stubs.\nFollow REST conventions. Include proper error handling and input validation.'

    def run(self, ctx: Dict[str, Any]) -> Dict[str, str]:
        stack = ctx['stack']
        arch = ctx.get('ARCHITECTURE.md', '')[:2000]
        results: Dict[str, str] = {}
        if stack in ('fastapi-react', 'flutter-fastapi'):
            prompt = f"Project: {ctx['project_name']}\nDescription: {ctx['description']}\nArchitecture:\n{arch}\n\nWrite backend/nim_service.py — a Python module that wraps NVIDIA NIM API calls. It should have a function: async def generate_code(prompt: str, api_key: str, model: str = 'z-ai/glm-5.2') -> str that calls https://integrate.api.nvidia.com/v1/chat/completions using the openai Python package with OpenAI(base_url='https://integrate.api.nvidia.com/v1', api_key=api_key). Return the assistant message content as a string. Include proper error handling."
            results['backend/nim_service.py'] = self._call_nim(self._messages(prompt), max_tokens=3000)
            prompt2 = f"Project: {ctx['project_name']}\n\nWrite backend/routers/generate.py — a FastAPI router at prefix /api/generate. POST /api/generate/code accepts {{{{prompt: str, stack: str}}}} JSON body and auth header. It calls nim_service.generate_code() and returns {{{{code: str, files: list}}}}. Include streaming via StreamingResponse for large outputs. Import: from backend.routers.auth import current_user, from backend.nim_service import generate_code"
            results['backend/routers/generate.py'] = self._call_nim(self._messages(prompt2), max_tokens=3000)
        elif stack == 'nextjs-postgres':
            prompt = f"Project: {ctx['project_name']}\n\nWrite app/api/generate/route.ts — a Next.js 14 App Router API route (POST). It accepts {{{{prompt: string}}}} in the body and calls NVIDIA NIM API (https://integrate.api.nvidia.com/v1/chat/completions) using fetch with streaming. Return a ReadableStream of text chunks. Use process.env.NIM_API_KEY."
            results['app/api/generate/route.ts'] = self._call_nim(self._messages(prompt), max_tokens=3000)
        elif stack == 'expo-node':
            prompt = f"Project: {ctx['project_name']}\n\nWrite server/routes/generate.js — an Express router at /api/generate. POST /api/generate/code accepts {{{{prompt, stack}}}} and calls NVIDIA NIM using node-fetch. Auth middleware: require Bearer JWT. Return {{{{code: string}}}}."
            results['server/routes/generate.js'] = self._call_nim(self._messages(prompt), max_tokens=3000)
        return results
--- DatabaseAgent ---
class DatabaseAgent(SpecializedAgent):
    role = 'database'
    _system_prompt = 'You are a senior database engineer. Output ONLY valid Python or SQL source code — no markdown fences.\nWrite complete SQLAlchemy models or Prisma schemas. No placeholder fields.'

    def run(self, ctx: Dict[str, Any]) -> Dict[str, str]:
        stack = ctx['stack']
        arch = ctx.get('ARCHITECTURE.md', '')[:2000]
        results: Dict[str, str] = {}
        if stack in ('fastapi-react', 'flutter-fastapi'):
            prompt = f"Project: {ctx['project_name']}\nDescription: {ctx['description']}\nArchitecture:\n{arch}\n\nWrite backend/models.py — SQLAlchemy 2.x ORM models for this project. Include: Base = declarative_base(), User model (id UUID pk, email unique, password_hash, created_at), Project model (id UUID pk, owner_id FK→users, name, description, status, stack, created_at, updated_at). Use proper types: String, DateTime, ForeignKey. Add __repr__ methods."
            results['backend/models.py'] = self._call_nim(self._messages(prompt), max_tokens=3000)
            prompt2 = 'Write backend/database.py — SQLAlchemy 2.x database setup. Use create_engine with DATABASE_URL from env (default: sqlite:///./app.db). Include: engine, SessionLocal = sessionmaker(...), get_db() FastAPI dependency, init_db() that calls Base.metadata.create_all. Import Base from backend.models.'
            results['backend/database.py'] = self._call_nim(self._messages(prompt2), max_tokens=2000)
        elif stack == 'nextjs-postgres':
            prompt = f"""Project: {ctx['project_name']}\nDescription: {ctx['description']}\nArchitecture:\n{arch}\n\nWrite prisma/schema.prisma — a Prisma schema for PostgreSQL. Include: generator client {{ provider = "prisma-client-js" }}, datasource db {{ provider = "postgresql", url = env("DATABASE_URL") }}, model User (id String @id @default(uuid()), email String @unique, passwordHash String, createdAt DateTime @default(now())), model Project (id String @id @default(uuid()), ownerId String, owner User @relation(fields: [ownerId], references: [id]), name String, description String, status String, stack String, createdAt DateTime @default(now()), updatedAt DateTime @updatedAt). No placeholder fields."""
            results['prisma/schema.prisma'] = self._call_nim(self._messages(prompt), max_tokens=2000)
        elif stack == 'expo-node':
            prompt = f"Project: {ctx['project_name']}\nDescription: {ctx['description']}\n\nWrite server/db.js — a Node.js module setting up a local SQLite database via better-sqlite3. Export: const db = new Database(process.env.DB_PATH || './app.db'); and a function initDb() that runs CREATE TABLE IF NOT EXISTS for a users table (id TEXT PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT, created_at TEXT) and a projects table (id TEXT PRIMARY KEY, owner_id TEXT, name TEXT, description TEXT, status TEXT, stack TEXT, created_at TEXT, updated_at TEXT). Export: module.exports = {{ db, initDb }};"
            results['server/db.js'] = self._call_nim(self._messages(prompt), max_tokens=2000)
        return results
--- TesterAgent ---
class TesterAgent(SpecializedAgent):
    role = 'tester'
    _system_prompt = 'You are a QA engineer. Output ONLY valid Python pytest test code — no markdown fences.\nWrite real tests with meaningful assertions — never trivial assert True.\nUse httpx.TestClient or fastapi.testclient.TestClient for API tests.'

    def run(self, ctx: Dict[str, Any]) -> Dict[str, str]:
        stack = ctx['stack']
        results: Dict[str, str] = {}
        if stack in ('fastapi-react', 'flutter-fastapi'):
            prompt = f"Project: {ctx['project_name']}\n\nWrite tests/test_api.py — pytest integration tests for the FastAPI backend.\nInclude:\n1. test_health() — GET /api/health returns 200 with status=ok\n2. test_register() — POST /api/auth/register with email/password returns token\n3. test_login() — POST /api/auth/login with correct credentials returns token\n4. test_login_wrong_password() — returns 401\n5. test_create_project() — POST /api/projects/ with auth header creates project\n6. test_list_projects() — GET /api/projects/ returns list\n\nUse: from fastapi.testclient import TestClient; from backend.main import app\nclient = TestClient(app)"
            results['tests/test_api.py'] = self._call_nim(self._messages(prompt), max_tokens=4000)
            results['tests/__init__.py'] = ''
            results['tests/conftest.py'] = 'import pytest\nfrom fastapi.testclient import TestClient\nfrom backend.main import app\n\n@pytest.fixture\ndef client():\n    with TestClient(app) as c:\n        yield c\n'
        elif stack == 'nextjs-postgres':
            prompt = f"Project: {ctx['project_name']}\n\nWrite tests/api.test.ts — Jest tests for Next.js API routes using node-fetch.\nTest: health endpoint, register, login, create project endpoints.\nUse: const BASE = 'http://localhost:3000'"
            results['tests/api.test.ts'] = self._call_nim(self._messages(prompt), max_tokens=3000)
        elif stack == 'expo-node':
            prompt = f"Project: {ctx['project_name']}\n\nWrite server/tests/api.test.js — Jest + supertest integration tests for the Express backend.\nIMPORTANT: there is no server/app.js entrypoint in this project. Build the test app inline:\n  const express = require('express');\n  const app = express();\n  app.use(express.json());\n  app.get('/api/health', (req, res) => res.json({{ status: 'ok' }}));\n  // mount any other generated routers under server/routes/ here if present\nInclude:\n1. test for GET /api/health returns 200 with status='ok'\n2. a second test exercising one route from server/routes/generate.js if it can be required without a live NIM API key, otherwise skip it with test.skip and a comment why\n\nUse: const request = require('supertest');"
            results['server/tests/api.test.js'] = self._call_nim(self._messages(prompt), max_tokens=3000)
        return results
--- DevOpsAgent ---
class DevOpsAgent(SpecializedAgent):
    role = 'devops'
    _system_prompt = 'You are a DevOps engineer. Output ONLY valid YAML, shell scripts, or Dockerfile content.\nNever output markdown fences or explanations in your files.'

    def run(self, ctx: Dict[str, Any]) -> Dict[str, str]:
        results: Dict[str, str] = {}
        prompt = f"Project: {ctx['project_name']}\nStack: {ctx['stack']}\n\nWrite .github/workflows/ci.yml — a GitHub Actions workflow that:\n1. Triggers on push to main and pull_request\n2. Sets up Python 3.12 (or Node 20 for nextjs/expo stacks)\n3. Installs dependencies\n4. Runs tests (pytest for Python, npm test for Node)\nUse ubuntu-latest runner."
        results['.github/workflows/ci.yml'] = self._call_nim(self._messages(prompt), max_tokens=2000)
        test_output = ctx.get('test_output')
        if test_output is None:
            test_section = 'Tests have not been executed yet for this generation.'
        elif not test_output.ran:
            test_section = f'Test runner did not run (no test files or unsupported stack).\n{test_output.output[:1500]}'
        else:
            test_section = f"Test run {('PASSED' if test_output.passed else 'FAILED')}.\nRaw output:\n{test_output.output[:3000]}"
        prompt2 = f"Project: {ctx['project_name']}\nStack: {ctx['stack']}\nDescription: {ctx['description']}\n\nActual test results:\n{test_section}\n\nWrite VERIFICATION.md — a checklist verifying acceptance criteria.\nFormat each item as: | Criterion | Test | Status |\nInclude checks for: auth works, projects CRUD works, Docker builds, CI passes, preview loads.\nMark a criterion ✅ Pass ONLY if the actual test results above confirm it. If tests did not run, or failed, or don't cover a criterion, mark it ⚠️ Unverified or ❌ Fail as appropriate — do not mark anything Pass on the assumption that it probably works."
        results['VERIFICATION.md'] = self._call_nim(self._messages(prompt2), max_tokens=2000)
        return results