# CompSphere

**AI assistant that controls a real web browser for you.**

Give it a task — "apply to jobs on LinkedIn", "research competitors", "fill out this form" — and watch it work in a live browser stream. Chat with it or take over the browser anytime.

---

## How It Works

1. You describe a task in the chat panel
2. A secure sandbox (Docker container) spins up with Chrome
3. The AI navigates websites, clicks, types, and scrolls — just like a human
4. You watch live via VNC and can send follow-ups or take manual control

The AI reads pages using the accessibility tree (like a screen reader) plus compressed screenshots, then acts via Chrome DevTools Protocol.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React, TypeScript, Tailwind CSS |
| Backend | FastAPI (Python), WebSockets |
| Database | PostgreSQL 16, async SQLAlchemy |
| AI Agent | Claude Code SDK |
| Browser Control | Custom CDP MCP Server |
| Sandbox | Docker (Ubuntu 22.04 + Chrome + Xvfb + x11vnc + websockify) |
| Deployment | k3s + Traefik + Let's Encrypt |

---

## Setup

### Prerequisites

- Docker with Docker Compose
- Node.js 20+, Python 3.12+
- Anthropic API key

### 1. Build the Sandbox Image

```bash
cd sandbox
docker build -t compshere-sandbox:latest -f Dockerfile.sandbox .
```

### 2. Configure Environment

Create `.env` in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=your-random-secret-key
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/compsphere
```

### 3. Run

**Docker Compose (recommended):**
```bash
docker compose up -d
```

**Manual (development):**
```bash
# Terminal 1
cd backend && pip install -r requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2
cd frontend && npm install && npm run dev
```

**Kubernetes (production):**
```bash
kubectl create namespace compsphere
kubectl create secret generic compsphere-secrets -n compsphere \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-... \
  --from-literal=SECRET_KEY=your-random-secret-key
kubectl apply -f k8s.yaml
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(required)* | API key for Claude |
| `SECRET_KEY` | `change-me` | JWT signing secret |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Database connection string |
| `SANDBOX_IMAGE` | `compshere-sandbox:latest` | Docker image for sandboxes |
| `MAX_CONCURRENT_SESSIONS` | `2` | Max simultaneous sandboxes |

---

## API

### REST Endpoints

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| `POST` | `/api/auth/register` | | Create account |
| `POST` | `/api/auth/login` | | Login, returns JWT |
| `GET` | `/api/auth/me` | Yes | Current user |
| `POST` | `/api/tasks` | Yes | Create task + start agent |
| `GET` | `/api/tasks` | Yes | List tasks |
| `GET` | `/api/tasks/{id}` | Yes | Task details |
| `DELETE` | `/api/tasks/{id}` | Yes | Delete task + destroy container |
| `POST` | `/api/tasks/{id}/message` | Yes | Send follow-up to agent |

### WebSockets

| Path | Format | Purpose |
|------|--------|---------|
| `/ws/agent/{task_id}` | JSON | Agent messages (thoughts, actions, results) |
| `/ws/vnc/{session_id}` | Binary | Live browser video stream |

---

## Live

**URL:** https://compsphere.callsphere.tech

---

## License

Proprietary. All rights reserved.
