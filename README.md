# CompSphere

**Your AI assistant that can actually use a web browser.**

CompSphere is a platform where you give an AI agent a task — like "apply to jobs on LinkedIn" or "research competitors" — and it opens a real browser, navigates websites, fills forms, clicks buttons, and gets things done. You watch everything happen live and can jump in to help at any time.

---

## What Does It Do?

Think of CompSphere as hiring a virtual assistant who sits at a computer and does web tasks for you — except the computer is in the cloud, the assistant is an AI (Claude), and you can watch their screen in real time.

```mermaid
flowchart LR
    A["You type a task"] --> B["AI opens a browser"]
    B --> C["AI navigates websites"]
    C --> D["You watch live"]
    D --> E["You chat or take over"]
    E --> C
```

**Example tasks:**
- "Go to LinkedIn and apply to Software Engineer jobs with Easy Apply"
- "Search Google for the top 10 project management tools and summarize them"
- "Log into my email and find all invoices from last month"
- "Fill out this web form with the following information..."

---

## How It Works (The Simple Version)

```mermaid
flowchart TB
    subgraph YOU["What You See"]
        direction LR
        Chat["Chat Panel\n(talk to the AI)"]
        Browser["Browser Panel\n(watch the AI work)"]
    end

    subgraph CLOUD["What Happens Behind the Scenes"]
        AI["AI Agent\n(Claude)"]
        Container["Isolated Sandbox\n(Docker Container)"]
        RealBrowser["Real Chrome Browser"]
    end

    Chat <-->|"messages"| AI
    AI -->|"controls"| RealBrowser
    RealBrowser -->|"lives inside"| Container
    Container -->|"streams video"| Browser
```

1. **You describe what you want** in the chat panel
2. **The AI reads your request** and starts working
3. **A secure sandbox spins up** — a private computer in the cloud just for your task
4. **Chrome opens** inside the sandbox, and the AI starts browsing
5. **You watch live** — the browser panel streams what's happening in real time
6. **You can chat** — send follow-up instructions or corrections anytime
7. **You can take control** — click the "Take Control" button to use the browser yourself

---

## Features

| Feature | Description |
|---------|-------------|
| **AI Browser Control** | The agent navigates websites, clicks buttons, fills forms, scrolls, and reads page content — just like a human would |
| **Live Browser Stream** | Watch every action in real time through a VNC video stream embedded in your browser |
| **Take Control Anytime** | Toggle between watching and controlling — click, type, and scroll in the live browser yourself |
| **Persistent Sessions** | Close the tab and come back later — your browser session (cookies, logins, open tabs) is still there |
| **Split-Panel UI** | Resizable chat + browser side by side, with fullscreen mode |
| **Follow-Up Chat** | Send new instructions while the agent is idle — it picks up right where it left off |
| **Auto-Login** | Pre-configured credentials (e.g., LinkedIn) are used automatically when a login page is detected |
| **Task History** | All tasks are saved and grouped by date — revisit any past session |
| **Secure Sandbox** | Each task runs in an isolated Docker container — nothing can escape to your real system |

---

## Architecture Overview

### System Diagram

```mermaid
flowchart TB
    subgraph Client["Your Browser"]
        UI["Next.js Frontend\n(React + Tailwind CSS)"]
        VNCViewer["VNC Viewer\n(react-vnc)"]
    end

    subgraph Backend["FastAPI Backend"]
        REST["REST API\n/api/auth, /api/tasks"]
        WSChat["WebSocket\n/ws/agent/task_id"]
        WSVnc["WebSocket\n/ws/vnc/session_id"]
        Bus["Message Bus\nin-memory pub/sub"]
        Orch["Agent Orchestrator\nClaude Code SDK"]
        VProxy["VNC Proxy\nbinary frame relay"]
        DockerMgr["Docker Manager\ncreate, destroy containers"]
        SessionMgr["Session Manager\nlifecycle tracking"]
    end

    subgraph Sandbox["Sandbox Container (per task)"]
        Super["supervisord"]
        Xvfb["Xvfb :99\nvirtual display"]
        Flux["Fluxbox\nwindow manager"]
        Chrome["Google Chrome\nCDP on port 9222"]
        MCP["CDP MCP Server\nbrowser automation"]
        VNC["x11vnc :5900"]
        WSify["websockify :6080"]
    end

    DB[("PostgreSQL\nusers, tasks,\nsessions, messages")]

    %% Client to Backend
    UI -->|"REST + JWT"| REST
    UI -->|"wss:// JSON"| WSChat
    VNCViewer -->|"wss:// binary"| WSVnc

    %% Backend internal
    REST --> SessionMgr
    REST --> DockerMgr
    WSChat <--> Bus
    Bus <--> Orch
    WSVnc <--> VProxy

    %% Backend to Sandbox
    Orch -->|"docker exec\nstdio MCP"| MCP
    DockerMgr -->|"create/destroy"| Sandbox
    VProxy -->|"TCP :6080"| WSify

    %% Sandbox internal
    Super -.->|"manages"| Xvfb & VNC & WSify & Flux
    Xvfb --> Chrome
    MCP -->|"ws://localhost:9222"| Chrome
    VNC -->|"captures screen"| Xvfb
    VNC --> WSify

    %% Backend to DB
    REST --> DB
    SessionMgr --> DB
    Orch --> DB
```

---

### What Happens When You Create a Task

```mermaid
sequenceDiagram
    actor You
    participant FE as Frontend
    participant API as Backend API
    participant Docker as Docker Manager
    participant Sandbox as Sandbox Container
    participant Agent as AI Agent (Claude)
    participant Chrome as Chrome Browser

    You->>FE: Type task and press Enter
    FE->>API: POST /api/tasks {prompt}
    API->>Docker: Create sandbox container
    Docker-->>API: container_id + vnc_port

    Note over API: Task saved to database<br/>Status: "pending"

    API->>Agent: Start agent loop (background)
    API-->>FE: task_id + session_id

    par Connect Streams
        FE->>API: WebSocket /ws/agent/{task_id}
        FE->>API: WebSocket /ws/vnc/{session_id}
    end

    Note over Agent: Agent reads your prompt<br/>and starts working

    loop AI Works Step by Step
        Agent->>Sandbox: docker exec cdp_mcp_server.py
        Sandbox->>Chrome: CDP command (navigate/click/type)
        Chrome-->>Sandbox: Result + screenshot
        Sandbox-->>Agent: Page snapshot + element list
        Agent-->>FE: Streams thoughts and actions
        Note over FE: You see messages in chat<br/>and browser updates in VNC
    end

    Note over Agent: Task complete<br/>Status: "idle"

    You->>FE: Type follow-up message
    FE->>API: WebSocket message
    API->>Agent: Enqueue follow-up
    Agent->>Sandbox: Resume working

    Note over Agent: Waits up to 1 hour<br/>for more messages
```

---

### How the AI Sees and Controls the Browser

The AI doesn't "see" pixels like a human. Instead, it reads the page structure (like a screen reader) and gets a compressed screenshot for context.

```mermaid
flowchart LR
    subgraph Perception["How the AI 'Sees' a Page"]
        direction TB
        AT["Accessibility Tree\n(list of buttons, links, inputs\neach with a number)"]
        SS["Screenshot\n(compressed WebP image\nfor visual context)"]
    end

    subgraph Action["How the AI Acts"]
        direction TB
        Nav["browser_navigate(url)\nGo to a URL"]
        Click["browser_click(index)\nClick element #5"]
        Type["browser_type(index, text)\nType into field #3"]
        Scroll["browser_scroll(down, 3)\nScroll the page"]
        Key["browser_press_key(Enter)\nPress a key"]
    end

    Chrome["Chrome Browser"] --> AT
    Chrome --> SS
    AT --> AI["AI Agent"]
    SS --> AI
    AI --> Nav & Click & Type & Scroll & Key
    Nav & Click & Type & Scroll & Key --> Chrome
```

**Example interaction:**
```
AI sees:   [1] link "Home"  [2] link "Jobs"  [3] textbox "Search"  [4] button "Sign In"
AI thinks: "I need to search for jobs, so I'll click element [2]"
AI calls:  browser_click(2)
AI sees:   (new page snapshot with job listings)
```

---

### VNC Live Streaming Pipeline

This is how the browser video reaches your screen:

```mermaid
flowchart LR
    Xvfb["Virtual Display\n(Xvfb :99)"] -->|"renders pixels"| VNC["x11vnc\n(VNC server)"]
    VNC -->|"VNC protocol\nport 5900"| WSify["websockify\n(port 6080)"]
    WSify -->|"WebSocket\nbinary frames"| Proxy["VNC Proxy\n(backend)"]
    Proxy -->|"wss://"| Viewer["react-vnc\n(your browser)"]
```

When you click **"Take Control"**, the VNC viewer switches from view-only to interactive mode — your mouse clicks and keyboard input are sent back through the same pipeline in reverse.

---

## User Flow

```mermaid
flowchart TD
    Start(["Visit compsphere.callsphere.tech"]) --> HasAccount{Have an account?}

    HasAccount -->|No| Register["Register with email + password"]
    HasAccount -->|Yes| Login["Log in"]
    Register --> Dashboard
    Login --> Dashboard

    Dashboard["Chat Page"] --> NewTask["Type your task\ne.g. 'Search for flights to NYC'"]
    NewTask --> TaskCreated["Task created\nSandbox starts spinning up"]
    TaskCreated --> SplitView["Split-panel view opens\nChat on left, Browser on right"]

    SplitView --> WatchAI["Watch the AI work\nin the browser panel"]
    WatchAI --> Decide{What do you want to do?}

    Decide -->|"Send a message"| FollowUp["Type a follow-up\ne.g. 'Also check Delta flights'"]
    FollowUp --> WatchAI

    Decide -->|"Take control"| TakeOver["Click 'Take Control'\nUse the browser yourself"]
    TakeOver --> WatchAI

    Decide -->|"Done"| Close["Close or delete the task"]
    Close --> Dashboard

    style Start fill:#8b5cf6,color:#fff
    style Dashboard fill:#3b82f6,color:#fff
    style SplitView fill:#10b981,color:#fff
    style Close fill:#6b7280,color:#fff
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Next.js 14, React 18, TypeScript, Tailwind CSS | Web interface |
| **VNC Client** | react-vnc (noVNC) | Live browser streaming to user |
| **Layout** | react-resizable-panels | Draggable split-panel UI |
| **Backend** | FastAPI + Uvicorn (Python) | REST API + WebSocket server |
| **Database** | PostgreSQL 16 + SQLAlchemy 2.0 (async) | Users, tasks, sessions, messages |
| **Auth** | JWT (HS256) + bcrypt | 24-hour token, secure password hashing |
| **AI Agent** | Claude Code SDK | Orchestrates the AI with tool access |
| **Browser Automation** | Custom CDP MCP Server | Controls Chrome via DevTools Protocol |
| **Sandboxing** | Docker SDK for Python | Isolated container per task |
| **VNC Pipeline** | Xvfb + Fluxbox + x11vnc + websockify | Virtual display to WebSocket stream |
| **Browser** | Google Chrome 145+ | Runs inside each sandbox container |
| **Process Manager** | supervisord | Manages sandbox services |
| **Deployment** | Kubernetes (k3s) + Traefik + Let's Encrypt | Production hosting with HTTPS |

---

## Project Structure

```
compsphere/
├── backend/                          # Python FastAPI server
│   ├── main.py                       # App entry point + startup hooks
│   ├── config.py                     # Environment-based settings
│   ├── requirements.txt              # Python dependencies
│   ├── core/
│   │   └── logging_config.py         # Structured JSON logging
│   ├── middleware/
│   │   └── request_logging.py        # HTTP request/response logger
│   ├── models/
│   │   ├── database.py               # Async SQLAlchemy engine + session
│   │   ├── user.py                   # User model (email, password)
│   │   ├── task.py                   # Task model (prompt, status)
│   │   └── session.py                # AgentSession + AgentMessage models
│   ├── routers/
│   │   ├── auth.py                   # Register, login, current user
│   │   ├── tasks.py                  # Task CRUD + follow-up messages
│   │   ├── ws.py                     # WebSocket: chat + VNC proxy
│   │   └── client_logs.py            # Frontend error receiver
│   └── services/
│       ├── agent_orchestrator.py     # Claude SDK agent loop + MCP config
│       ├── docker_manager.py         # Container create/destroy
│       ├── session_manager.py        # Session lifecycle management
│       ├── vnc_proxy.py              # WebSocket VNC frame relay
│       ├── message_bus.py            # In-memory pub/sub for messages
│       └── agent_message_queue.py    # Per-task follow-up queues
│
├── frontend/                         # Next.js React app
│   ├── package.json                  # Node.js dependencies
│   └── src/
│       ├── app/
│       │   ├── page.tsx              # Landing / homepage
│       │   ├── layout.tsx            # Root layout (dark theme, navbar)
│       │   ├── auth/
│       │   │   ├── login/page.tsx    # Login page
│       │   │   └── register/page.tsx # Registration page
│       │   └── chat/
│       │       ├── page.tsx          # New task creation
│       │       ├── layout.tsx        # Chat layout with sidebar
│       │       └── [taskId]/page.tsx # Task view (chat + browser)
│       ├── components/
│       │   ├── BrowserView.tsx       # VNC viewer + Take Control toggle
│       │   ├── ChatPanel.tsx         # Message list + text input
│       │   ├── AgentMessage.tsx      # Message bubble renderer
│       │   ├── ChatTopBar.tsx        # Status bar + controls
│       │   ├── WelcomePrompt.tsx     # Task creation with templates
│       │   ├── Sidebar.tsx           # Task list sidebar
│       │   └── Navbar.tsx            # Top navigation bar
│       └── lib/
│           ├── api.ts                # REST client with JWT injection
│           ├── ws.ts                 # WebSocket hook with dedup
│           └── logger.ts             # Client-side error logger
│
├── sandbox/                          # Docker sandbox for browser
│   ├── Dockerfile.sandbox            # Ubuntu 22.04 + Chrome + VNC
│   ├── cdp_mcp_server.py            # CDP browser automation (~840 lines)
│   ├── supervisord.conf              # Process startup order
│   └── entrypoint.sh                # Container entrypoint script
│
├── docker-compose.yml                # Local dev (Postgres, backend, frontend, nginx)
├── k8s.yaml                          # Kubernetes manifests (production)
└── nginx.conf                        # Reverse proxy config
```

---

## API Reference

### REST Endpoints

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| `POST` | `/api/auth/register` | | Create account (email + password) |
| `POST` | `/api/auth/login` | | Login, returns JWT token |
| `GET` | `/api/auth/me` | Yes | Get current user profile |
| `POST` | `/api/tasks` | Yes | Create task and start AI agent |
| `GET` | `/api/tasks` | Yes | List all your tasks |
| `GET` | `/api/tasks/{id}` | Yes | Task details + sessions + messages + VNC URL |
| `DELETE` | `/api/tasks/{id}` | Yes | Delete task, kill agent, destroy container |
| `POST` | `/api/tasks/{id}/message` | Yes | Send follow-up message to agent |
| `GET` | `/api/health` | | Health check + active session count |
| `POST` | `/api/client-logs` | | Receive frontend error logs |

### WebSocket Channels

| Path | Direction | Format | Purpose |
|------|-----------|--------|---------|
| `/ws/agent/{task_id}` | Bidirectional | JSON | Agent messages (thoughts, tool calls, results, errors) |
| `/ws/vnc/{session_id}` | Bidirectional | Binary | VNC video stream + user input relay |

---

## Database Schema

```mermaid
erDiagram
    users {
        uuid id PK
        string email UK
        string password_hash
        timestamp created_at
    }

    tasks {
        uuid id PK
        uuid user_id FK
        string name
        text prompt
        string status
        text result_summary
        timestamp created_at
        timestamp updated_at
    }

    agent_sessions {
        uuid id PK
        uuid task_id FK
        string container_id
        int vnc_port
        string status
        timestamp started_at
        timestamp ended_at
    }

    agent_messages {
        uuid id PK
        uuid session_id FK
        string role
        text content
        string tool_name
        text tool_input
        text tool_result
        int sequence_num
        timestamp created_at
    }

    users ||--o{ tasks : "creates"
    tasks ||--o{ agent_sessions : "has"
    agent_sessions ||--o{ agent_messages : "contains"
```

**Task statuses:** `pending` → `running` → `idle` (waiting for follow-up) → `completed` or `failed`

---

## Setup

### Prerequisites

- Docker with Docker Compose
- Node.js 20+
- Python 3.12+
- PostgreSQL 16 (or use Docker Compose)
- Anthropic API key

### 1. Build the Sandbox Image

```bash
cd sandbox
docker build -t compshere-sandbox:latest -f Dockerfile.sandbox .
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=your-random-secret-key
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/compsphere

# Optional: auto-login credentials
LINKEDIN_EMAIL=your@email.com
LINKEDIN_PASSWORD=your-password
```

### 3a. Run with Docker Compose (Local)

```bash
docker compose up -d
```

Access at http://localhost (nginx) or http://localhost:3000 (frontend direct)

### 3b. Run with Kubernetes (Production)

```bash
# Create namespace and secrets
kubectl create namespace compsphere
kubectl create secret generic compsphere-secrets -n compsphere \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-... \
  --from-literal=SECRET_KEY=your-random-secret-key

# Deploy
kubectl apply -f k8s.yaml

# Verify
kubectl get pods -n compsphere
```

### 3c. Run Without Docker (Development)

```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(required)* | API key for Claude |
| `SECRET_KEY` | `change-me` | JWT signing secret |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Database connection string |
| `SANDBOX_IMAGE` | `compshere-sandbox:latest` | Docker image for sandboxes |
| `BROWSER_PROFILES_PATH` | `/data/browser-profiles` | Where browser profiles are stored |
| `DOCKER_HOST_IP` | `localhost` | Host IP for VNC proxy connections |
| `MAX_CONCURRENT_SESSIONS` | `2` | Max simultaneous sandboxes |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT token lifetime (24 hours) |
| `LINKEDIN_EMAIL` | *(optional)* | Auto-fill LinkedIn login |
| `LINKEDIN_PASSWORD` | *(optional)* | Auto-fill LinkedIn password |

---

## How Key Things Work

### Browser Profile Persistence

Each user gets a dedicated Chrome profile stored on disk. When a new task is created, the profile is mounted into the sandbox container. This means:

- **Cookies persist** — log into a site once, stay logged in across tasks
- **Open tabs persist** — Chrome restores the last session on restart
- **Bookmarks, history, extensions** — all saved per user

### Message Deduplication

Messages can arrive twice due to WebSocket reconnections or React StrictMode. CompSphere handles this at two levels:

1. **Frontend:** Content-based dedup with a 2-second sliding window
2. **Backend:** Skips duplicate `ResultMessage` events from Claude SDK

### Prompt Caching Strategy

CompSphere minimizes token costs using Anthropic's prompt caching. The system prompt is structured so the static prefix gets cached and reused across turns at 90% discount.

```mermaid
flowchart LR
    subgraph SystemPrompt["System Prompt (structured for caching)"]
        direction TB
        Static["Static Instructions\n(core rules, browser tools,\nsafety, formatting)\n~1500 tokens"]
        FileRef["Profile File Reference\n'cat /home/agent/user_profile.txt'\n(loaded on demand)"]
        Dynamic["Dynamic Credentials\n(changes per env)\nKept LAST"]
    end

    subgraph Turn1["Turn 1"]
        CW["Cache WRITE\n$3.75/MTok"]
    end

    subgraph TurnN["Turns 2–50"]
        CR["Cache READ\n$0.30/MTok\n(90% cheaper)"]
    end

    Static --> CW
    CW --> CR

    style Static fill:#10b981,color:#fff
    style FileRef fill:#3b82f6,color:#fff
    style Dynamic fill:#f59e0b,color:#fff
    style CR fill:#10b981,color:#fff
```

**Key optimizations:**
- **Slim prompt** — user profile (~3000 tokens) moved to file, read only when forms are encountered
- **Static prefix first** — maximizes cache hit on every turn
- **Dynamic content last** — credentials at the end don't invalidate the cached prefix
- **Model routing** — optional `model` param to route simple tasks to Haiku (75% cheaper)
- **Cache analytics** — admin dashboard tracks hit rate, savings, and per-request cache breakdown

### Container Lifecycle

```mermaid
flowchart LR
    Create["Task Created"] -->|"docker create"| Running["Container Running\n(Chrome + VNC active)"]
    Running -->|"agent completes"| Idle["Container Idle\n(browser still accessible)"]
    Idle -->|"follow-up message"| Running
    Idle -->|"1 hour timeout"| Idle
    Idle -->|"task deleted"| Destroyed["Container Destroyed"]
    Running -->|"task deleted"| Destroyed

    style Create fill:#8b5cf6,color:#fff
    style Running fill:#10b981,color:#fff
    style Idle fill:#f59e0b,color:#fff
    style Destroyed fill:#ef4444,color:#fff
```

Containers are **only destroyed when you delete the task** — not when the agent finishes. This lets you go back and use the browser manually even after the AI is done.

---

## Live Deployment

**URL:** https://compsphere.callsphere.tech

Hosted on k3s (lightweight Kubernetes) with Traefik ingress and Let's Encrypt TLS.

---

## License

Proprietary. All rights reserved.
