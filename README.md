# CompSphere — AI Agent Platform with Live Browser View

CompSphere is a full-stack AI agent platform that executes tasks in sandboxed Docker containers with a real browser. Users can watch the agent navigate websites in real time through a live VNC stream, take control of the browser at any time, and chat with the agent — all from a single split-panel interface.

Built with Claude Code SDK, Playwright MCP, and a VNC pipeline (Xvfb → x11vnc → websockify → react-vnc).

![CompSphere](image.png)

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Build the Sandbox Image](#build-the-sandbox-image)
  - [Option A: Docker Compose (Local Dev)](#option-a-docker-compose-local-dev)
  - [Option B: Kubernetes (Production)](#option-b-kubernetes-production)
- [Configuration](#configuration)
- [API Reference](#api-reference)
  - [REST Endpoints](#rest-endpoints)
  - [WebSocket Endpoints](#websocket-endpoints)
- [Database Schema](#database-schema)
- [Sandbox Container](#sandbox-container)
- [Frontend Pages & Components](#frontend-pages--components)
- [VNC Pipeline](#vnc-pipeline)
- [Session Lifecycle](#session-lifecycle)
- [Deployment Notes](#deployment-notes)

---

## Features

- **AI Agent with Browser Control** — Claude Code SDK agent with Playwright MCP navigates real websites, fills forms, extracts data, and runs terminal commands inside a sandboxed container.
- **Live Browser View** — Real-time VNC stream of the agent's browser via react-vnc. Watch the agent work as it happens.
- **Take Control Anytime** — Toggle between view-only and interactive mode. Click, type, and scroll in the live browser while the agent is idle.
- **Persistent Browser Sessions** — Containers stay alive after the agent finishes. The browser and its state persist until you delete the task.
- **Split-Panel Interface** — Resizable chat + browser panels. Toggle browser visibility. Fullscreen mode.
- **Real-Time Chat** — WebSocket-based message streaming. See agent thoughts, tool calls, tool results, and errors as they happen.
- **Task Management** — Create, list, view, and delete tasks. Tasks are grouped by date (Today, Yesterday, Last 7 Days, Older).
- **Authentication** — JWT-based auth with email/password registration and login.
- **Browser Profile Persistence** — Each user gets a persistent browser profile directory mounted into containers.
- **Message Deduplication** — Content-based dedup with 2-second window prevents duplicate messages from React StrictMode and SDK result echoes.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         User Browser                        │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │   Chat Panel     │  │     Browser View (react-vnc)     │ │
│  │   (WebSocket)    │  │     (WebSocket binary)           │ │
│  └────────┬─────────┘  └────────────────┬─────────────────┘ │
└───────────┼─────────────────────────────┼───────────────────┘
            │ wss://host/ws/agent/{id}    │ wss://host/ws/vnc/{id}
            ▼                             ▼
┌───────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Pod)                       │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Message Bus  │  │ VNC Proxy    │  │ Agent Orchestrator   │ │
│  │ (pub/sub)    │  │ (websockets) │  │ (Claude Code SDK)    │ │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬───────────┘ │
│         │                │                      │             │
│         │                │         ┌────────────┘             │
│         │                │         │  docker exec -i          │
│         │                │         │  npx @playwright/mcp     │
└─────────┼────────────────┼─────────┼──────────────────────────┘
          │                │         │
          │                │         ▼
          │    ┌───────────────────────────────────┐
          │    │     Sandbox Docker Container       │
          │    │                                    │
          │    │  ┌─────────┐    ┌──────────────┐  │
          │    │  │  Xvfb   │───▶│  Chromium     │  │
          │    │  │ :99     │    │  (Playwright) │  │
          │    │  └────┬────┘    └──────────────┘  │
          │    │       │                            │
          │    │  ┌────▼────┐    ┌──────────────┐  │
          │    │  │ x11vnc  │───▶│  websockify   │  │
          │    │  │ :5900   │    │  :6080        │  │
          │    │  └─────────┘    └──────┬───────┘  │
          │    └───────────────────────┬┘           │
          │                            │            │
          └────────────────────────────┘            │
                    ws://host:port/websockify        │
                                                    │
┌───────────────────────────────────────────────────┘
│  PostgreSQL (users, tasks, sessions, messages)
└───────────────────────────────────────────────────
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Next.js 14, React 18, TypeScript | SSR, routing, UI |
| **Styling** | Tailwind CSS 3.4 | Utility-first CSS |
| **VNC Client** | react-vnc 2.0.3 (noVNC) | Live browser streaming |
| **Layout** | react-resizable-panels 4.7 | Split-panel interface |
| **Icons** | lucide-react | UI icons |
| **Backend** | FastAPI, Uvicorn | Async API server |
| **ORM** | SQLAlchemy 2.0 (async) | Database access |
| **Database** | PostgreSQL 16, asyncpg | Data persistence |
| **Migrations** | Alembic | Schema versioning |
| **Auth** | python-jose (JWT), passlib (bcrypt) | Authentication |
| **AI Agent** | Claude Code SDK | Agent loop & reasoning |
| **Browser Control** | Playwright MCP | Browser automation |
| **Containers** | Docker SDK for Python | Sandbox management |
| **VNC Server** | x11vnc, websockify | Screen capture & WebSocket bridge |
| **Display** | Xvfb, Fluxbox | Virtual X11 display |
| **Browser** | Chromium | Web browsing in sandbox |
| **Process Mgmt** | supervisord | Manage sandbox services |
| **Orchestration** | Kubernetes (k3s) | Production deployment |
| **Ingress** | Traefik + Let's Encrypt | HTTPS, routing |
| **Local Dev** | Docker Compose, Nginx | Development environment |

---

## Project Structure

```
compsphere/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Settings (env-based via pydantic-settings)
│   ├── core/
│   │   └── logging_config.py      # Structured JSON logging
│   ├── middleware/
│   │   └── request_logging.py     # Request/response logging middleware
│   ├── models/
│   │   ├── database.py            # SQLAlchemy engine & session factory
│   │   ├── user.py                # User model
│   │   ├── task.py                # Task model
│   │   └── session.py             # AgentSession & AgentMessage models
│   ├── routers/
│   │   ├── auth.py                # Register, login, me endpoints
│   │   ├── tasks.py               # CRUD + agent lifecycle
│   │   ├── ws.py                  # WebSocket: agent chat & VNC proxy
│   │   └── client_logs.py         # Frontend error log receiver
│   ├── services/
│   │   ├── agent_orchestrator.py  # Claude Code SDK agent loop
│   │   ├── docker_manager.py      # Container create/destroy/exec
│   │   ├── session_manager.py     # Session lifecycle (create/idle/destroy)
│   │   ├── vnc_proxy.py           # WebSocket VNC frame relay
│   │   └── message_bus.py         # In-memory pub/sub for agent messages
│   ├── alembic/                   # Database migrations
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx           # Landing page
│   │   │   ├── layout.tsx         # Root layout (dark mode, navbar)
│   │   │   ├── auth/
│   │   │   │   ├── login/page.tsx
│   │   │   │   └── register/page.tsx
│   │   │   └── chat/
│   │   │       ├── page.tsx       # New task (welcome prompt)
│   │   │       ├── layout.tsx     # Sidebar layout
│   │   │       └── [taskId]/page.tsx  # Task view (chat + browser)
│   │   ├── components/
│   │   │   ├── ChatPanel.tsx      # Message list + input
│   │   │   ├── BrowserView.tsx    # VNC viewer + controls
│   │   │   ├── AgentMessage.tsx   # Message bubble renderer
│   │   │   ├── ChatTopBar.tsx     # Status bar + toggle controls
│   │   │   ├── Sidebar.tsx        # Task list sidebar
│   │   │   ├── WelcomePrompt.tsx  # New task prompt + templates
│   │   │   └── ...
│   │   └── lib/
│   │       ├── api.ts             # REST API client (fetch + JWT)
│   │       ├── ws.ts              # WebSocket hook with deduplication
│   │       └── logger.ts          # Client-side error logger
│   ├── package.json
│   └── tailwind.config.ts
├── sandbox/
│   ├── Dockerfile.sandbox         # Ubuntu 22.04 + Xvfb + VNC + Chromium
│   ├── supervisord.conf           # Process manager config
│   └── entrypoint.sh              # Container entrypoint
├── k8s.yaml                       # Kubernetes manifests (production)
├── docker-compose.yml             # Local development setup
└── nginx.conf                     # Nginx reverse proxy config
```

---

## Getting Started

### Prerequisites

- **Docker** (with Docker Compose)
- **Node.js 20+** (for frontend development)
- **Python 3.12+** (for backend development)
- **PostgreSQL 16** (or use the Docker Compose postgres service)
- **Anthropic API Key** (for Claude Code SDK)

### Build the Sandbox Image

The sandbox image must be built before running the platform:

```bash
cd sandbox
docker build -t compshere-sandbox:latest -f Dockerfile.sandbox .
```

### Option A: Docker Compose (Local Dev)

1. **Create `.env`** in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
SECRET_KEY=your-random-secret-key
```

2. **Start all services:**

```bash
docker compose up -d
```

3. **Access the app:**
   - Frontend: http://localhost (via nginx)
   - Backend API: http://localhost:8000
   - Direct frontend: http://localhost:3000

### Option B: Kubernetes (Production)

1. **Create namespace and secrets:**

```bash
kubectl create namespace compsphere

kubectl create secret generic compsphere-secrets \
  -n compsphere \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-your-key-here \
  --from-literal=SECRET_KEY=your-random-secret-key
```

2. **Update `k8s.yaml`:**
   - Replace `YOUR_HOST_IP` with your server's IP address
   - Update the domain in the Ingress if needed
   - Adjust resource limits as needed

3. **Apply manifests:**

```bash
kubectl apply -f k8s.yaml
```

4. **Verify:**

```bash
kubectl get pods -n compsphere
curl https://your-domain/api/health
```

---

## Configuration

All backend configuration is managed via environment variables (loaded by `pydantic-settings`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/compsphere` | PostgreSQL connection string |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` (24h) | JWT token expiry |
| `ANTHROPIC_API_KEY` | *(required)* | Claude API key for agent |
| `MAX_CONCURRENT_SESSIONS` | `2` | Max simultaneous sandbox containers |
| `CONTAINER_TTL_MINUTES` | `30` | Container idle timeout (cleanup policy) |
| `SANDBOX_IMAGE` | `compshere-sandbox:latest` | Docker image for sandbox containers |
| `BROWSER_PROFILES_PATH` | `/data/browser-profiles` | Persistent browser profile storage |
| `DOCKER_HOST_IP` | `localhost` | Host IP for VNC connections (set to server IP in k8s) |

Frontend environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | *(empty = same origin)* | Backend API base URL |
| `NEXT_PUBLIC_WS_URL` | *(empty = same origin)* | WebSocket base URL |

---

## API Reference

### REST Endpoints

#### Authentication

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/auth/register` | Create account | No |
| `POST` | `/api/auth/login` | Login, returns JWT | No |
| `GET` | `/api/auth/me` | Get current user profile | Yes |

**Register/Login request:**
```json
{ "email": "user@example.com", "password": "your-password" }
```

**Response:**
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```

#### Tasks

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/tasks` | Create task & start agent | Yes |
| `GET` | `/api/tasks` | List all user's tasks | Yes |
| `GET` | `/api/tasks/{id}` | Get task detail + sessions + vnc_url | Yes |
| `DELETE` | `/api/tasks/{id}` | Delete task & destroy container | Yes |
| `POST` | `/api/tasks/{id}/message` | Send follow-up message to agent | Yes |

**Create task request:**
```json
{ "prompt": "Search for the latest AI news and summarize the top 5 stories" }
```

**Task detail response:**
```json
{
  "id": "uuid",
  "name": "Search for the latest...",
  "prompt": "Search for the latest AI news...",
  "status": "running",
  "vnc_url": "/ws/vnc/session-uuid",
  "sessions": [{ "id": "...", "status": "running", "vnc_port": 32801, "messages": [...] }],
  "created_at": "2026-03-03T04:45:38Z"
}
```

#### Other

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check with active session count |
| `POST` | `/api/client-logs` | Receive frontend error logs |

### WebSocket Endpoints

#### Agent Chat — `wss://host/ws/agent/{task_id}`

Streams agent messages in real time.

**Server → Client messages:**
```json
{ "type": "assistant", "content": "I'll search for AI news..." }
{ "type": "tool_use", "tool_name": "mcp__playwright__navigate", "tool_input": "{\"url\": \"...\"}" }
{ "type": "tool_result", "content": "Page loaded successfully" }
{ "type": "status", "content": "Agent starting up..." }
{ "type": "error", "content": "Agent error: ..." }
```

**Client → Server messages:**
```json
{ "type": "user_message", "content": "Also check TechCrunch" }
```

#### VNC Proxy — `wss://host/ws/vnc/{session_id}`

Binary WebSocket that proxies VNC frames between the frontend's react-vnc component and the container's websockify endpoint.

- **Subprotocol:** `binary`
- **Proxy target:** `ws://{DOCKER_HOST_IP}:{vnc_port}/websockify`
- **Retry logic:** 10 attempts with 1-second delay (websockify needs ~4s to start)

---

## Database Schema

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│    users     │     │      tasks       │     │  agent_sessions  │     │  agent_messages   │
├──────────────┤     ├──────────────────┤     ├──────────────────┤     ├──────────────────┤
│ id (UUID PK) │◄────│ user_id (FK)     │     │ id (UUID PK)     │     │ id (UUID PK)     │
│ email        │     │ id (UUID PK)     │◄────│ task_id (FK)     │     │ session_id (FK)  │──►
│ password_hash│     │ name             │     │ container_id     │◄────│ role             │
│ created_at   │     │ prompt           │     │ vnc_port         │     │ content          │
└──────────────┘     │ status           │     │ status           │     │ tool_name        │
                     │ result_summary   │     │ started_at       │     │ tool_input       │
                     │ created_at       │     │ ended_at         │     │ tool_result      │
                     │ updated_at       │     └──────────────────┘     │ sequence_num     │
                     └──────────────────┘                              │ created_at       │
                                                                       └──────────────────┘
```

**Status values:**
- **Task:** `pending` → `running` → `completed` | `failed`
- **Session:** `creating` → `running` → `idle` → `completed`
  - `idle` = agent finished but container still alive for user interaction

All primary keys are UUIDs. Cascade deletes propagate from users → tasks → sessions → messages.

---

## Sandbox Container

Each task gets an isolated Ubuntu 22.04 Docker container with:

| Process | Port | Startup Delay | Purpose |
|---------|------|---------------|---------|
| **Xvfb** | `:99` display | 0s | Virtual X11 framebuffer (1280x720x24) |
| **Fluxbox** | — | 2s | Lightweight window manager |
| **x11vnc** | `5900` | 3s | VNC server (no password, shared mode) |
| **websockify** | `6080` | 4s | WebSocket-to-VNC bridge, serves noVNC |

**Container specs:**
- 1 CPU, 2GB RAM limit
- Bridge network with dynamic port mapping
- Persistent browser profile mounted at `/home/agent/.browser-profile`
- Runs as non-root `agent` user
- Node.js 20 pre-installed for Playwright MCP

**Agent control flow:**
1. Backend calls `docker exec -i {container_id} npx @playwright/mcp@latest --no-sandbox`
2. Claude Code SDK sends Playwright commands (navigate, click, type, screenshot)
3. Playwright controls Chromium on the Xvfb display
4. x11vnc captures the display and streams to the user via websockify

---

## Frontend Pages & Components

### Pages

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | Landing page | Hero, features, CTA |
| `/auth/login` | Login form | Email + password, JWT stored in localStorage |
| `/auth/register` | Register form | Email + password with validation |
| `/chat` | New task | Welcome prompt + template chips |
| `/chat/[taskId]` | Task view | Split-panel: chat + live browser |
| `/dashboard` | Dashboard | Redirects to `/chat` |

### Key Components

| Component | Description |
|-----------|-------------|
| `ChatPanel` | Message list with auto-scroll, textarea input (Enter/Shift+Enter), connection indicator |
| `BrowserView` | VNC viewer with take-control toggle, fullscreen, connection status, ResizeObserver for scaling |
| `AgentMessage` | Renders messages by type: assistant (purple), user (blue), tool_use (expandable), tool_result (green), status (yellow), error (red) |
| `ChatTopBar` | Task prompt, status badge, connection dot, browser toggle, sidebar toggle |
| `Sidebar` | Task list grouped by date, new chat button, user email, sign out |
| `WelcomePrompt` | Centered prompt with templates (Research, Fill Form, Browse Website) |

---

## VNC Pipeline

The live browser view uses a multi-hop VNC pipeline:

```
Browser (react-vnc)
    │
    │  wss://domain/ws/vnc/{session_id}
    ▼
Traefik Ingress → Backend Service
    │
    │  FastAPI WebSocket handler
    ▼
VNC Proxy (vnc_proxy.py)
    │
    │  ws://{DOCKER_HOST_IP}:{mapped_port}/websockify
    ▼
Docker Container: websockify (:6080)
    │
    │  TCP localhost:5900
    ▼
Docker Container: x11vnc (:5900)
    │
    │  X11 display :99
    ▼
Docker Container: Xvfb + Chromium
```

**Key implementation details:**
- `react-vnc` wraps noVNC's RFB client with `scaleViewport` for auto-fitting
- `viewOnly` toggle is set directly on the RFB object (react-vnc prop alone is unreliable)
- `ResizeObserver` re-applies `scaleViewport` when the panel resizes (prevents blank canvas bug)
- VNC proxy retries 10 times with 1-second delays (websockify needs ~4s to start)
- Binary WebSocket subprotocol used throughout the chain

---

## Session Lifecycle

```
User creates task
    │
    ▼
POST /api/tasks ──► Container created ──► Agent starts
    │                    │                     │
    │                    │  VNC available       │  Claude Code SDK
    │                    │  (after ~4s)         │  + Playwright MCP
    │                    │                     │
    │                    ▼                     ▼
    │              Browser viewable      Agent running
    │              + controllable        (streaming messages)
    │                    │                     │
    │                    │                     ▼
    │                    │              Agent finishes
    │                    │                     │
    │                    │    ┌────────────────┘
    │                    │    │
    │                    ▼    ▼
    │              Session = "idle"
    │              Container STAYS ALIVE
    │              Browser still viewable
    │              User can take control
    │                    │
    │                    │  User deletes task
    │                    ▼
    │              Container destroyed
    │              Session = "completed"
    ▼
  Done
```

Containers persist after the agent finishes so users can continue viewing and interacting with the browser. They are only destroyed when the user explicitly deletes the task.

---

## Deployment Notes

### Building for Production

**Sandbox image** (must be built on the deployment host):
```bash
cd sandbox
docker build -t compshere-sandbox:latest -f Dockerfile.sandbox .
```

**Frontend** (for production builds):
```bash
cd frontend
npm install
npm run build
npm start
```

### Kubernetes Requirements

- **Docker socket access:** The backend pod needs `/var/run/docker.sock` mounted to create sandbox containers on the host.
- **Host networking:** Sandbox containers use bridge networking with dynamic port mapping. The backend connects to them via `DOCKER_HOST_IP`.
- **cert-manager:** Required for automatic TLS certificate provisioning with Let's Encrypt.
- **Traefik:** Used as the ingress controller. WebSocket paths (`/ws`) are routed to the backend.

### Resource Requirements

| Component | CPU Request | Memory Request | CPU Limit | Memory Limit |
|-----------|------------|----------------|-----------|-------------|
| Backend | 200m | 512Mi | 1 core | 1Gi |
| Frontend | 200m | 512Mi | 1 core | 2Gi |
| Sandbox (per container) | 1 core | — | 1 core | 2Gi |

### Security Considerations

- JWT tokens expire after 24 hours
- Passwords hashed with bcrypt
- Sandbox containers run as non-root `agent` user
- Containers are CPU/memory limited
- VNC has no password (access controlled at the WebSocket/auth layer)
- HTTPS enforced via Traefik with automatic cert renewal
- CORS allows all origins (configure for production)

---

## License

This project is proprietary. All rights reserved.
