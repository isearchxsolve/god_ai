# Windows 11 Web Clone – Full-Stack Application Plan

## Overview
A web-based simulation of the Windows 11 desktop environment, replicating the core UI/UX, window management, file system, and basic applications. Built as a single-page application (SPA) with a real-time backend for persistence and multi-user support.

## Tech Stack
- **Frontend**: React 18 + TypeScript, Zustand (state management), Tailwind CSS, Framer Motion (animations), react-window (virtualization)
- **Backend**: Node.js + Express, Socket.IO (real-time), Prisma ORM
- **Database**: PostgreSQL (primary), Redis (session/cache)
- **DevOps**: Docker, Nginx, GitHub Actions CI/CD
- **Testing**: Jest, Cypress, Playwright

## Features List
### Core OS Simulation
- **Desktop**: Wallpaper, icon grid, context menu, drag-and-drop icons
- **Taskbar**: Start button, pinned apps, system tray (clock, volume, network, battery), notification area
- **Start Menu**: Power menu, user avatar, pinned apps list, all apps list, search bar
- **Window Manager**: Draggable, resizable, minimizable, maximizable windows; z-index stacking; snap layouts (left/right/quadrants)
- **File Explorer**: Tree view sidebar, breadcrumb navigation, file/folder CRUD, drag-and-drop, search, context menu (copy, paste, delete, rename, properties)
- **Settings App**: Personalization (wallpaper, themes, colors), System (display, sound, notifications), Accounts (user profile, sign-in options)
- **Task View**: Virtual desktops, window thumbnails, timeline
- **Widgets Panel**: Weather, calendar, news, to-do list (configurable)
- **Lock Screen**: Clock, date, notifications, slide-to-unlock animation
- **Login Screen**: User selection, password/PIN input, accessibility options

### Built-in Applications
- **Calculator**: Standard & scientific modes
- **Notepad**: Basic text editor with save/load
- **Paint**: Simple drawing canvas (brush, eraser, color picker)
- **Terminal**: Command-line interface with basic commands (ls, cd, mkdir, rm, echo, help)
- **Browser**: Embedded WebView (iframe) with address bar, bookmarks, history
- **Media Player**: Audio/video playback with playlist support
- **Store**: App listing, install/uninstall simulation

### Multi-user & Persistence
- User accounts with authentication (JWT)
- Per-user desktop layout, settings, files
- Real-time collaboration on files (optional)

## API Endpoints
### Authentication
- `POST /api/auth/register` – Create account
- `POST /api/auth/login` – Login, returns JWT
- `POST /api/auth/refresh` – Refresh token
- `POST /api/auth/logout` – Invalidate token

### User Profile
- `GET /api/users/me` – Current user info
- `PATCH /api/users/me` – Update profile (avatar, display name)
- `GET /api/users/me/settings` – Get user settings (theme, wallpaper, etc.)
- `PATCH /api/users/me/settings` – Update settings

### File System
- `GET /api/files?path=/` – List directory contents
- `POST /api/files/upload` – Upload file (multipart)
- `POST /api/files/folder` – Create folder
- `DELETE /api/files/:id` – Delete file/folder
- `PATCH /api/files/:id` – Rename/move file/folder
- `GET /api/files/:id/download` – Download file
- `GET /api/files/search?q=...` – Search files

### Applications
- `GET /api/apps` – List installed apps
- `POST /api/apps/install` – Install app (from store)
- `DELETE /api/apps/:id` – Uninstall app
- `GET /api/apps/:id/data` – Get app-specific data (e.g., notepad content)

### Store
- `GET /api/store/apps` – List available apps
- `GET /api/store/apps/:id` – App details

### Real-time (Socket.IO)
- `file:change` – Notify other clients of file changes
- `user:status` – Online/offline status
- `desktop:update` – Sync desktop layout changes

## Database Schema Outline
```sql
-- Users
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(50) UNIQUE NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  avatar_url TEXT,
  display_name VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User Settings (JSON for flexibility)
CREATE TABLE user_settings (
  user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  theme VARCHAR(20) DEFAULT 'light',
  wallpaper_url TEXT DEFAULT '/wallpapers/default.jpg',
  accent_color VARCHAR(7) DEFAULT '#0078D4',
  taskbar_alignment VARCHAR(10) DEFAULT 'center',
  lock_screen_wallpaper TEXT DEFAULT '/wallpapers/lock_default.jpg',
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Files & Folders (hierarchical)
CREATE TABLE files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  parent_id UUID REFERENCES files(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  is_folder BOOLEAN DEFAULT FALSE,
  mime_type VARCHAR(100),
  size BIGINT DEFAULT 0,
  storage_path TEXT, -- actual file location on disk
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, parent_id, name)
);

-- Desktop Layout (icons positions)
CREATE TABLE desktop_icons (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  file_id UUID REFERENCES files(id) ON DELETE SET NULL,
  app_id UUID REFERENCES apps(id) ON DELETE SET NULL,
  x INTEGER NOT NULL,
  y INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Installed Apps
CREATE TABLE apps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) NOT NULL,
  display_name VARCHAR(100) NOT NULL,
  icon_url TEXT,
  type VARCHAR(20) DEFAULT 'builtin', -- builtin, store
  manifest JSONB, -- app metadata (version, permissions, etc.)
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- User App Installations
CREATE TABLE user_apps (
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  app_id UUID NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
  installed_at TIMESTAMPTZ DEFAULT NOW(),
  data JSONB DEFAULT '{}', -- app-specific user data
  PRIMARY KEY (user_id, app_id)
);

-- Store Apps (available for installation)
CREATE TABLE store_apps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) UNIQUE NOT NULL,
  display_name VARCHAR(100) NOT NULL,
  description TEXT,
  icon_url TEXT,
  version VARCHAR(20),
  developer VARCHAR(100),
  manifest JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sessions (for JWT refresh)
CREATE TABLE sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  refresh_token VARCHAR(255) UNIQUE NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Milestones

### Phase 1: Foundation (2 weeks)
- Set up monorepo (frontend + backend)
- Implement authentication (register, login, JWT)
- Basic desktop shell (wallpaper, taskbar, start menu)
- Window manager (drag, resize, close, minimize, maximize)
- Database schema & API for user settings

### Phase 2: File System & Explorer (2 weeks)
- File CRUD API with PostgreSQL
- File Explorer UI (tree view, breadcrumbs, context menu)
- Drag-and-drop file operations
- Search functionality
- File upload/download

### Phase 3: Built-in Apps (3 weeks)
- Calculator (standard + scientific)
- Notepad (with save/load)
- Paint (canvas drawing)
- Terminal (command parser, basic commands)
- Media Player (audio/video)
- Store (app listing, install/uninstall)

### Phase 4: Advanced Features (2 weeks)
- Task View (virtual desktops, window thumbnails)
- Widgets Panel (weather, calendar, news)
- Lock Screen & Login Screen
- Settings App (personalization, system, accounts)
- Real-time collaboration (Socket.IO for file changes)

### Phase 5: Polish & Deployment (1 week)
- Performance optimization (virtualization, lazy loading)
- Responsive design (tablet/mobile adaptations)
- Accessibility (keyboard navigation, screen reader support)
- Docker containerization
- CI/CD pipeline
- Production deployment (VPS or cloud)

### Phase 6: Extras (ongoing)
- Browser app (WebView with bookmarks/history)
- Notification system
- Multi-monitor support (simulated)
- Theme engine (light/dark/high contrast)
- User-customizable shortcuts
- App SDK for third-party developers

## Notes
- The "OS" is purely a visual simulation; no actual system-level access.
- All file operations are sandboxed per user.
- Real-time features use WebSocket for low latency.
- The project is designed to be extensible (plugin architecture for apps).
- Security: Input sanitization, rate limiting, CORS, HTTPS enforced.