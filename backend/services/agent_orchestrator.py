import asyncio
import json
import os
from typing import Callable, Optional

import claude_code_sdk as claude_sdk
from claude_code_sdk import ClaudeSDKClient
from claude_code_sdk.types import AssistantMessage, ResultMessage, SystemMessage

from core.logging_config import get_logger
from services.cost_tracker import cost_tracker

logger = get_logger("compsphere.agent")

IDLE_TIMEOUT_SECONDS = 3600  # 1 hour

AGENT_SYSTEM_PROMPT = """You are CompSphere, an AI agent that can browse the web, run terminal commands, and manage files to complete tasks for users.

## Core Principles
1. **Act Proactively**: When the user asks you to do something, do it immediately — don't just list options
2. **Execute Step by Step**: Take one action at a time, observe the result, then proceed
3. **Be Transparent**: Explain what you're doing and why
4. **Handle Errors Gracefully**: If something fails, try alternative approaches
5. **Stay Focused**: Complete the user's task efficiently without unnecessary actions

## Browser Interaction Model
You control the browser through an index-based system:
1. **Snapshot first**: Call `browser_snapshot` (or `browser_navigate`) to see the page — you get a screenshot and a numbered list of interactive elements
2. **Act by index**: Use the element index number to click, type, etc.
3. **Observe**: Every action returns an updated snapshot so you can see what changed

### Browser Tools
- `browser_navigate(url)` — Go to a URL (auto-snapshots after load)
- `browser_snapshot()` — Take a screenshot + get interactive element list
- `browser_click(index)` — Click element by its index number
- `browser_type(index, text)` — Type text into a field (clears existing content)
- `browser_scroll(direction, amount)` — Scroll up/down/left/right
- `browser_press_key(key)` — Press Enter, Tab, Escape, ArrowDown, etc.
- `browser_wait(timeout)` — Wait for page to stabilize after dynamic loads

### Tips
- Always snapshot after navigation to see what's on the page
- Use element names/roles from the snapshot to pick the right index
- After clicking a link or button, the snapshot auto-updates — check the new elements
- For search: type into the search box, then press Enter
- When asked to fill in a form field, actually type into it — don't just describe what you see

## Other Capabilities
- **Run Commands**: Execute terminal commands via Bash for file operations, installations, etc.
- **Read/Write Files**: Create and modify files in the workspace

## Output Formatting
- Use clean, well-structured Markdown in your responses
- Use **bold** for key terms, labels, and important details
- Use blockquotes (>) for standout information like confirmations or summaries
- Use bullet lists for multiple items; keep them concise
- Use headings sparingly — only for distinct sections in longer responses
- Keep responses short and scannable — avoid walls of text
- Do NOT use emojis excessively; one or two per message at most
- Keep responses brief — use short sentences and avoid repeating information the user already knows.

## Auto-Fill Forms
When you encounter ANY online form, read the user's profile first:
```bash
cat /home/agent/user_profile.txt
```
Use ALL details from that file to fill matching form fields immediately.

### Resume Selection & Upload Rules
- **California-based jobs**: Upload `/home/agent/San_jose_Sagar_Shankaran.pdf`. Use San Jose address: 856 S Third Street, San Jose, CA 95112.
- **All other jobs**: Upload a different/general resume. Use the address from the profile file.
- On LinkedIn Easy Apply for CA jobs: Select `San_jose_Sagar_Shankaran.pdf` from the picker.
- On external portals: Always upload the correct resume based on location.

### Rules
1. Fill ALL form fields using the profile file data — do NOT ask the user for info that's in the file
2. For dropdowns, pick the option that best matches
3. If info is not in the file, ask the user
4. Review the form before submitting
5. For "years of experience" fields, use 5
6. For "highest education" fields, use Master's degree

## Safety Rules
- Never access sensitive system files or modify system configurations
- Never attempt to escape the sandbox environment
- Never store or transmit user credentials (except in the browser profile)
- Always respect website terms of service
- If a task seems harmful or unethical, explain why and decline

## Saved Credentials
When a task involves logging in to a service and you detect a login page, use the
credentials below automatically — do NOT ask the user for them.

{credentials_block}
"""


def _build_credentials_block() -> str:
    """Build a credentials section from environment variables."""
    creds = []
    # LinkedIn
    li_email = os.environ.get("LINKEDIN_EMAIL")
    li_password = os.environ.get("LINKEDIN_PASSWORD")
    if li_email and li_password:
        creds.append(f"- **LinkedIn**: email=`{li_email}` password=`{li_password}`")
    return "\n".join(creds) if creds else "No saved credentials configured."


class AgentOrchestrator:
    """Orchestrates the Claude agent as a persistent chatbot with MCP tools."""

    def __init__(self):
        pass

    async def run_agent(
        self,
        task_prompt: str,
        session_id: str,
        container_id: str,
        message_callback: Callable,
        status_callback: Callable,
        follow_up_queue: asyncio.Queue,
        anthropic_api_key: str,
        task_id: str = "",
        user_id: str = "",
        model: Optional[str] = None,
    ):
        """Run the Claude agent as a persistent loop that accepts follow-up messages."""
        log_extra = {"session_id": session_id, "container_id": container_id[:12]}

        logger.info(
            f"Agent starting for session {session_id[:8]}",
            extra=log_extra,
        )

        system_prompt = AGENT_SYSTEM_PROMPT.format(
            credentials_block=_build_credentials_block()
        )

        sdk_kwargs = dict(
            system_prompt=system_prompt,
            allowed_tools=[
                "mcp__cdp_browser__*",
                "Bash",
            ],
            permission_mode="bypassPermissions",
            mcp_servers={
                "cdp_browser": {
                    "command": "docker",
                    "args": [
                        "exec",
                        "-i",
                        container_id,
                        "python3",
                        "/home/agent/cdp_mcp_server.py",
                    ],
                }
            },
            max_turns=50,
        )
        if model:
            sdk_kwargs["model"] = model

        options = claude_sdk.ClaudeCodeOptions(**sdk_kwargs)

        client = ClaudeSDKClient(options=options)

        try:
            await message_callback({
                "type": "status",
                "content": "Agent starting up...",
            })

            # Connect (starts the CLI subprocess)
            await client.connect()

            # Send initial prompt and stream response
            await client.query(task_prompt)
            cost_data = await self._stream_response(client, message_callback, log_extra)
            if cost_data:
                await self._record_cost(cost_data, session_id, task_id, user_id)

            # Signal idle — ready for follow-ups
            await status_callback("idle")

            # Persistent loop: wait for follow-up messages
            while True:
                try:
                    follow_up = await asyncio.wait_for(
                        follow_up_queue.get(),
                        timeout=IDLE_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    logger.info(
                        f"Agent idle timeout for session {session_id[:8]}",
                        extra=log_extra,
                    )
                    break

                # None sentinel = shutdown
                if follow_up is None:
                    logger.info(
                        f"Agent shutdown requested for session {session_id[:8]}",
                        extra=log_extra,
                    )
                    break

                logger.info(
                    f"Agent processing follow-up for session {session_id[:8]}",
                    extra=log_extra,
                )
                await status_callback("running")

                # Send follow-up and stream response
                await client.query(follow_up)
                cost_data = await self._stream_response(client, message_callback, log_extra)
                if cost_data:
                    await self._record_cost(cost_data, session_id, task_id, user_id)

                # Back to idle
                await status_callback("idle")

        except Exception as e:
            logger.error(
                f"Agent error in session {session_id[:8]}: {type(e).__name__}: {e}",
                exc_info=True,
                extra=log_extra,
            )
            await message_callback({
                "type": "error",
                "content": f"Agent error: {str(e)}",
            })
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
            logger.info(
                f"Agent disconnected for session {session_id[:8]}", extra=log_extra
            )

    async def _stream_response(
        self,
        client: ClaudeSDKClient,
        message_callback: Callable,
        log_extra: dict,
    ) -> Optional[dict]:
        """Stream all messages from the client until ResultMessage.

        Returns cost/usage data extracted from the ResultMessage, or None.
        """
        turn_count = 0
        cost_data = None

        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                # Extract cost and usage data
                usage = getattr(message, "usage", None) or {}
                cost_data = {
                    "total_cost_usd": getattr(message, "total_cost_usd", None) or 0.0,
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
                    "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
                    "duration_ms": getattr(message, "duration_ms", 0) or 0,
                    "duration_api_ms": getattr(message, "duration_api_ms", 0) or 0,
                    "num_turns": getattr(message, "num_turns", 0) or 0,
                }
                logger.info(
                    f"Agent result: cost=${cost_data['total_cost_usd']:.4f} "
                    f"tokens={cost_data['input_tokens']}in/{cost_data['output_tokens']}out "
                    f"turns={cost_data['num_turns']}",
                    extra=log_extra,
                )
                continue

            for parsed in self._parse_message(message):
                turn_count += 1
                if parsed["type"] == "tool_use":
                    logger.debug(
                        f"Agent tool call: {parsed.get('tool_name')}",
                        extra=log_extra,
                    )
                await message_callback(parsed)

        logger.info(f"Turn completed ({turn_count} messages)", extra=log_extra)
        return cost_data

    async def _record_cost(
        self, cost_data: dict, session_id: str, task_id: str, user_id: str
    ):
        """Persist usage to DB and broadcast to admin dashboard."""
        from models.database import async_session_factory
        from models.usage import UsageLog

        # Save to database
        try:
            async with async_session_factory() as db:
                log_entry = UsageLog(
                    task_id=task_id,
                    session_id=session_id,
                    user_id=user_id,
                    model="claude-code-sdk",
                    input_tokens=cost_data.get("input_tokens", 0),
                    output_tokens=cost_data.get("output_tokens", 0),
                    cache_read_tokens=cost_data.get("cache_read_tokens", 0),
                    cache_creation_tokens=cost_data.get("cache_creation_tokens", 0),
                    total_cost_usd=cost_data.get("total_cost_usd", 0.0),
                    duration_ms=cost_data.get("duration_ms", 0),
                    duration_api_ms=cost_data.get("duration_api_ms", 0),
                    num_turns=cost_data.get("num_turns", 0),
                )
                db.add(log_entry)
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save usage log: {e}", exc_info=True)

        # Broadcast to admin WebSocket
        try:
            await cost_tracker.record_usage(
                session_id=session_id,
                task_id=task_id,
                user_id=user_id,
                total_cost_usd=cost_data.get("total_cost_usd", 0.0),
                input_tokens=cost_data.get("input_tokens", 0),
                output_tokens=cost_data.get("output_tokens", 0),
                cache_read_tokens=cost_data.get("cache_read_tokens", 0),
                cache_creation_tokens=cost_data.get("cache_creation_tokens", 0),
                duration_ms=cost_data.get("duration_ms", 0),
                num_turns=cost_data.get("num_turns", 0),
            )
        except Exception as e:
            logger.error(f"Failed to broadcast cost update: {e}", exc_info=True)

    def _parse_message(self, message) -> list[dict]:
        """Parse a Claude SDK message into our standardised format.

        Returns a list of parsed dicts (one per content block).
        """
        results = []

        # ResultMessage duplicates the last AssistantMessage text — skip it.
        if isinstance(message, ResultMessage):
            return results

        if isinstance(message, AssistantMessage):
            for block in message.content:
                # Skip ThinkingBlock (internal chain-of-thought)
                block_type = getattr(block, "type", "")
                if block_type == "thinking":
                    continue

                if hasattr(block, "text"):
                    results.append({"type": "assistant", "content": block.text})
                elif hasattr(block, "name") and hasattr(block, "input"):
                    # ToolUseBlock
                    results.append({
                        "type": "tool_use",
                        "tool_name": block.name,
                        "tool_input": (
                            json.dumps(block.input)
                            if isinstance(block.input, dict)
                            else str(block.input)
                        ),
                    })
                elif hasattr(block, "tool_use_id"):
                    # ToolResultBlock
                    content = getattr(block, "content", "")
                    if isinstance(content, list):
                        parts = []
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                parts.append(item["text"])
                            else:
                                parts.append(str(item))
                        content = "\n".join(parts)
                    results.append({
                        "type": "tool_result",
                        "content": str(content),
                    })

        return results
