# Building a CompSphere AI Agent Application with Claude Code API (Single VM Architecture)

This document outlines a comprehensive technical prompt, implementation steps, and a database schema for developing an AI agent application similar to CompSphere, specifically tailored for deployment on a **single Hostinger VM**. The core idea is to leverage Anthropic's Claude Code API for intelligent decision-making and tool use, combined with isolated environments (e.g., Docker containers) within the single VM for executing real-world computer interactions.

## 1. Technical Prompt for the AI Agent (Claude)

The following prompt is designed to guide the Claude AI model in its role as an autonomous agent operating within a secure, isolated computing environment *within a shared VM*. It defines the AI's capabilities, objectives, and interaction protocols.

```
Your role is an autonomous AI agent operating within a secure, isolated computing environment. You have full access to a virtual desktop, a web browser (Chromium), a shell terminal, and a text editor. Your primary objective is to understand and execute complex user-defined tasks by intelligently utilizing these tools. You must prioritize safety, efficiency, and adherence to user instructions.

**Available Tools:**

1.  **`computer_use` (Anthropic's Computer Use Tool):** This tool allows you to interact with the virtual desktop environment. It provides:
    *   `screenshot_capture()`: Captures the current state of the virtual desktop as an image.
    *   `mouse_click(x, y)`: Clicks at specified coordinates on the screen.
    *   `keyboard_input(text)`: Types text into the active input field.
    *   `navigate_browser(url)`: Opens a new browser tab and navigates to the specified URL.
    *   `scroll_page(direction)`: Scrolls the current browser page (up, down, left, right).
    *   `find_element(selector)`: Locates elements on the page using CSS selectors and returns their properties.

2.  **`bash` (Bash Terminal):** Executes shell commands within your isolated environment. Use this for file system operations, installing packages, running scripts, and general system interaction.
    *   `execute_command(command)`: Runs a bash command and returns its stdout and stderr.

3.  **`text_editor` (Text Editor):** For creating, reading, and modifying files within your isolated environment's file system.
    *   `read_file(path)`: Reads the content of a file.
    *   `write_file(path, content)`: Writes content to a file (overwrites if exists).
    *   `append_file(path, content)`: Appends content to a file.

**Agent Loop Protocol:**

1.  **Receive Task:** You will receive a user prompt describing the task.
2.  **Plan:** Formulate a step-by-step plan to achieve the task using the available tools. Break down complex tasks into smaller, manageable sub-tasks.
3.  **Execute:** Select the most appropriate tool and construct the `tool_code` call with necessary parameters.
4.  **Observe:** After tool execution, you will receive an observation (e.g., screenshot, terminal output, browser DOM, tool result).
5.  **Reflect & Iterate:** Analyze the observation, update your internal state, and determine the next action. If the task is not complete, return to step 2. If the task is complete, provide a concise summary of the outcome.

**Constraints & Guidelines:**

*   **Safety First:** Always prioritize safe operations. Avoid actions that could lead to data loss or system instability. If a task involves sensitive data, request explicit user confirmation.
*   **Efficiency:** Strive for the most efficient path to task completion. Minimize unnecessary tool calls or redundant actions.
*   **Transparency:** Clearly articulate your reasoning and actions. Provide progress updates to the user.
*   **Error Handling:** Anticipate potential errors and include recovery strategies in your plan. If an error occurs, attempt to diagnose and fix it.
*   **Context Management:** Keep track of relevant information from previous steps and observations to maintain coherence throughout the task.
*   **Confirmation:** For actions with significant real-world consequences (e.g., posting content, making purchases), always request user confirmation.

**Example Task:** "Log in to LinkedIn, search for 'AI Agent Developers', and send a connection request to the first 5 relevant profiles with a personalized message." 
```

## 2. System Architecture (Single VM, Multi-Tenant)

To host the entire application on a single Hostinger VM while supporting multiple concurrent agent sessions, a multi-tenant architecture with strong process isolation is crucial. Instead of provisioning a new VM for each task, we will leverage containerization (e.g., Docker) to create isolated environments within the single VM. Within each container, a single Chromium instance can host multiple isolated browser contexts, each serving a different chat/agent session. This approach allows for efficient resource utilization while maintaining session isolation.

```mermaid
graph TD
    User -->|1. Task Request| Frontend
    Frontend -->|2. API Call| BackendService
    BackendService -->|3. Create Task| Database
    BackendService -->|4. Request Agent Session| AgentOrchestrator
    AgentOrchestrator -->|5. Launch Container| DockerDaemon(on Hostinger VM)
    DockerDaemon -->|6. Container Ready| IsolatedContainer[Isolated Container (Agent Session)]
    IsolatedContainer -->|7. Install Tools (Chromium, Xvfb, etc.)| IsolatedContainer
    AgentOrchestrator -->|8. Send Prompt| ClaudeAPI(Anthropic Claude Code API)
    ClaudeAPI -->|9. Tool Call| AgentOrchestrator
    AgentOrchestrator -->|10. Execute Tool (via Docker exec)| IsolatedContainer
    IsolatedContainer -->|11. Return Observation| AgentOrchestrator
    AgentOrchestrator -->|12. Stream Display| Frontend
    AgentOrchestrator -->|13. Update Task Status/Logs| Database
    Frontend -->|14. Display Live View & Results| User
```

**Key Components (Adjusted for Single VM):**

*   **Frontend:** User interface (web/desktop/mobile) for task submission, live view display, and interaction.
*   **Backend Service (API Gateway):** Handles user requests, authentication, task creation, and orchestrates interactions with other services. Runs directly on the Hostinger VM.
*   **Database:** Stores user data, task details, agent session logs, and tool definitions. Runs directly on the Hostinger VM (e.g., PostgreSQL).
*   **Agent Orchestrator:** The brain of the operation. Runs directly on the Hostinger VM. It manages the agent loop:
    *   Sends prompts to the Claude API.
    *   Parses Claude's tool calls.
    *   Executes tools *within* the designated Docker container using `docker exec`.
    *   Captures observations (screenshots, terminal output, DOM) from the container.
    *   Feeds observations back to Claude.
    *   Streams live display data to the frontend.
*   **Docker Daemon:** Manages Docker containers on the Hostinger VM. Each agent session will run in its own Docker container.
*   **Isolated Container (Agent Session):** A Docker container where a single AI agent session operates. Each container will have:
    *   A single Chromium instance capable of running multiple isolated browser contexts [3]. Each browser context will represent an independent agent session, complete with its own cookies, local storage, and cache, ensuring session isolation for different chats/tasks.
    *   A virtual display server (e.g., Xvfb) to render graphical output.
    *   A headless browser (e.g., Chromium with Playwright/Selenium) capable of managing multiple browser contexts.
    *   A shell environment.
    *   Its own isolated file system.
    *   Resource limits (CPU, RAM) enforced by Docker to prevent resource contention.
*   **Claude API (Anthropic):** The large language model responsible for understanding tasks, planning actions, and generating tool calls.
*   **Browser Automation Library (e.g., Playwright, Selenium):** Used within each container to programmatically control the browser.

## 3. Implementation Steps (Single VM Focus)

Here's a step-by-step guide to building the application with a single Hostinger VM:

### Step 1: Hostinger VM Setup and Core Infrastructure

1.  **Hostinger VM Provisioning:** Provision a sufficiently powerful Linux VM on Hostinger. Ensure it has enough CPU, RAM, and disk space to handle multiple concurrent agent sessions.
2.  **Docker Installation:** Install Docker and Docker Compose on your Hostinger VM.
3.  **Database Setup:** Install and configure PostgreSQL (or your chosen database) directly on the Hostinger VM. (Refer to the provided `db_schema.md` for schema details).
4.  **Backend Service Framework:** Choose a backend framework (e.g., Node.js with Express, Python with FastAPI/Django, Go with Gin) and set up a basic API structure. Deploy this service directly on the Hostinger VM.
5.  **Frontend Framework:** Choose a frontend framework (e.g., React, Vue, Angular) and set up a basic UI. Deploy this as static files served by your backend or a web server (e.g., Nginx) on the Hostinger VM.

### Step 2: Containerized Agent Environment

1.  **Docker Image Creation:** Create a Dockerfile for your agent environment. This image should include:
    *   A base Linux distribution (e.g., Ubuntu).
    *   Xvfb (X Virtual Framebuffer) for a virtual display.
    *   Chromium browser.
    *   A browser automation library (e.g., Playwright, Selenium).
    *   Any other necessary tools (e.g., `ffmpeg` for streaming, Python/Node.js runtime).
    *   Configure Xvfb to run on a unique display for each container (e.g., using environment variables).
2.  **Container Orchestration (within VM):** The Agent Orchestrator will be responsible for:
    *   Launching new Docker containers for each agent session.
    *   Assigning unique display numbers to Xvfb within each container.
    *   Setting resource limits (CPU, memory) for each container using Docker run options (`--cpus`, `--memory`).
    *   Managing container lifecycle (start, stop, remove).
3.  **Browser Automation within Container:** The browser automation library (e.g., Playwright) will connect to the Chromium instance running within its respective container. It will then create and manage multiple isolated browser contexts, each corresponding to a different agent session/chat, all utilizing the container's Xvfb display.
4.  **File System Isolation:** Each container will have its own isolated file system. If persistent storage is needed for agent sessions, consider Docker volumes or bind mounts, ensuring proper isolation per session.
5.  **Live Display Streaming:** Implement a mechanism to stream the virtual display from *each container* to the frontend. This could involve:
    *   Running `ffmpeg` within each container to encode the Xvfb display into a video stream.
    *   Streaming this video data out of the container (e.g., via WebSockets or a dedicated streaming server running on the Hostinger VM that aggregates streams).
    *   Alternatively, capture screenshots from each container and send them to the frontend.

### Step 3: Implement Agent Orchestrator (on Hostinger VM)

1.  **Claude API Integration:** Use the Anthropic Python or TypeScript SDK to interact with the Claude API. Ensure you use the `computer_use` tool and the appropriate beta header [2].
2.  **Tool Definition Mapping:** Create a mapping between Claude's `computer_use` tool actions (e.g., `navigate_browser`) and the actual functions that execute these actions *within a specific Docker container*.
3.  **Agent Loop Implementation:**
    *   **Initial Prompt:** Send the user's task description to Claude.
    *   **Tool Call Handling:** When Claude responds with a `tool_use` request, parse the tool name and arguments.
    *   **Tool Execution:** Use `docker exec` to run commands within the target container to execute the tool (e.g., a Python script that uses Playwright to navigate).
    *   **Observation Generation:** Capture the result of the tool execution (e.g., browser screenshot, terminal output, DOM snapshot) from the container as an observation.
    *   **Feedback to Claude:** Send the observation back to Claude as a `tool_result` in a new message.
    *   **Loop Termination:** Continue this loop until Claude indicates the task is complete or requests user input.
4.  **State Management:** Maintain the state of each agent session, including the conversation history with Claude, current container status, and any intermediate data.

### Step 4: Develop Backend Services (on Hostinger VM)

1.  **User Management:** Implement user registration, login, and authentication (e.g., JWT).
2.  **Task API:** Create endpoints for:
    *   `POST /tasks`: Submit a new task (user prompt).
    *   `GET /tasks/{id}`: Retrieve task status and history.
    *   `GET /tasks/{id}/live_stream`: Establish a WebSocket connection for live browser view from a specific container.
    *   `POST /tasks/{id}/user_input`: Send user input/confirmation to the agent.
3.  **Orchestration Logic:** The backend service will initiate agent sessions, manage container lifecycles through the Agent Orchestrator, and interact with the Agent Orchestrator.

### Step 5: Build Frontend

1.  **Task Submission Interface:** Allow users to input task descriptions.
2.  **Live View Component:** Display the streamed browser view from the specific agent session's container. This could be an `<img>` tag updated with new screenshots or a video player for a continuous stream.
3.  **Interaction Elements:** Provide UI elements for users to intervene, confirm actions, or provide additional input to the agent.
4.  **Task History and Results:** Display a list of past tasks, their status, and final outcomes.

### Step 6: Security, Monitoring, and Deployment

1.  **Container Security:** Implement strict resource limits, network isolation, and user permissions for Docker containers. Ensure containers run as non-root users. Regularly update Docker images and host OS.
2.  **API Security:** Secure all API endpoints with authentication and authorization.
3.  **Logging and Monitoring:** Implement comprehensive logging for agent actions, observations, and system events. Set up monitoring and alerting for container health, resource usage, and overall VM performance.
4.  **Deployment:** Deploy all components (backend, frontend, Docker images) to your Hostinger VM.

## 4. Database Schema

```sql
-- Users Table
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tasks Table
CREATE TABLE tasks (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- e.g., 'pending', 'running', 'completed', 'failed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- AgentSessions Table
CREATE TABLE agent_sessions (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES tasks(id),
    container_id VARCHAR(255) UNIQUE, -- Docker Container ID
    status VARCHAR(50) NOT NULL DEFAULT 'initializing', -- e.g., 'initializing', 'active', 'terminated'
    start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- AgentActions Table
CREATE TABLE agent_actions (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES agent_sessions(id),
    action_type VARCHAR(50) NOT NULL, -- e.g., 'browser_navigate', 'browser_click', 'shell_exec', 'llm_tool_call'
    action_details JSONB, -- JSON representation of the action parameters
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sequence_num INTEGER NOT NULL,
    llm_prompt_tokens INTEGER,
    llm_completion_tokens INTEGER
);

-- AgentObservations Table
CREATE TABLE agent_observations (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES agent_sessions(id),
    observation_type VARCHAR(50) NOT NULL, -- e.g., 'screenshot', 'terminal_output', 'browser_dom', 'llm_response'
    observation_data TEXT, -- Textual data (e.g., terminal output, DOM), or path to file (screenshot)
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sequence_num INTEGER NOT NULL
);

-- ToolDefinitions Table (for dynamic tool management)
CREATE TABLE tool_definitions (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    schema JSONB, -- JSON schema for the tool's input/output
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

## 5. References

1.  [How I taught an AI to use a computer — E2B Blog](https://e2b.dev/blog/how-i-taught-an-ai-to-use-a-computer)
2.  [Computer use tool - Claude API Docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)
3.  [Isolation - Playwright Documentation](https://playwright.dev/docs/browser-contexts)
