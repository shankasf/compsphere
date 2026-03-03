import asyncio
import json
from typing import Callable, Optional

import claude_code_sdk as claude_sdk
from claude_code_sdk.types import AssistantMessage, ResultMessage, SystemMessage

from core.logging_config import get_logger

logger = get_logger("compsphere.agent")

AGENT_SYSTEM_PROMPT = """You are CompSphere, an AI agent that can browse the web, run terminal commands, and manage files to complete tasks for users.

## Core Principles
1. **Plan First**: Before acting, briefly outline your approach
2. **Execute Step by Step**: Take one action at a time, observe the result, then proceed
3. **Be Transparent**: Explain what you're doing and why
4. **Handle Errors Gracefully**: If something fails, try alternative approaches
5. **Stay Focused**: Complete the user's task efficiently without unnecessary actions

## Available Capabilities
- **Browse the Web**: Navigate websites, click elements, fill forms, extract data
- **Run Commands**: Execute terminal commands for file operations, installations, etc.
- **Read/Write Files**: Create and modify files in the workspace

## Safety Rules
- Never access sensitive system files or modify system configurations
- Never attempt to escape the sandbox environment
- Never store or transmit user credentials (except in the browser profile)
- Always respect website terms of service
- If a task seems harmful or unethical, explain why and decline
"""


class AgentOrchestrator:
    """Orchestrates the Claude agent loop with MCP tools for browser control."""

    def __init__(self):
        pass

    async def run_agent(
        self,
        task_prompt: str,
        session_id: str,
        container_id: str,
        message_callback: Callable,
        anthropic_api_key: str,
    ):
        """Run the Claude agent loop with Playwright MCP for browser control."""
        log_extra = {"session_id": session_id, "container_id": container_id[:12]}

        logger.info(
            f"Agent starting for session {session_id[:8]}",
            extra=log_extra,
        )

        try:
            await message_callback({
                "type": "status",
                "content": "Agent starting up...",
            })

            options = claude_sdk.ClaudeCodeOptions(
                system_prompt=AGENT_SYSTEM_PROMPT,
                allowed_tools=[
                    "mcp__playwright__*",
                    "Bash",
                ],
                permission_mode="bypassPermissions",
                mcp_servers={
                    "playwright": {
                        "command": "docker",
                        "args": [
                            "exec",
                            "-i",
                            container_id,
                            "npx",
                            "@playwright/mcp@latest",
                            "--no-sandbox",
                        ],
                    }
                },
                max_turns=50,
            )

            turn_count = 0
            async for message in claude_sdk.query(
                prompt=task_prompt,
                options=options,
            ):
                for parsed in self._parse_message(message):
                    turn_count += 1
                    if parsed["type"] == "tool_use":
                        logger.debug(
                            f"Agent tool call: {parsed.get('tool_name')}",
                            extra=log_extra,
                        )
                    await message_callback(parsed)

            logger.info(
                f"Agent completed for session {session_id[:8]} ({turn_count} messages)",
                extra=log_extra,
            )

            await message_callback({
                "type": "status",
                "content": "Task completed",
            })

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
                        # content can be a list of dicts with 'text' keys
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
