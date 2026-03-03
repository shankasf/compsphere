#!/usr/bin/env python3
"""
CDP-based MCP server for browser automation (Manus AI approach).

Connects directly to Chrome DevTools Protocol instead of Playwright,
using accessibility trees + screenshots for page perception.

Protocol: JSON-RPC over stdio (MCP specification).
All logging goes to stderr; stdout is reserved for MCP messages.
"""

import asyncio
import base64
import json
import subprocess
import sys
import time
import urllib.request
from typing import Any, Optional

import websockets

# ---------------------------------------------------------------------------
# Logging helper (stderr only — stdout is the MCP transport)
# ---------------------------------------------------------------------------

def log(msg: str):
    print(f"[cdp-mcp] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# CDPConnection — WebSocket client for Chrome DevTools Protocol
# ---------------------------------------------------------------------------

class CDPConnection:
    """Low-level CDP WebSocket transport."""

    def __init__(self):
        self._ws = None
        self._msg_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._event_handlers: dict[str, list] = {}
        self._recv_task: Optional[asyncio.Task] = None

    async def connect(self, ws_url: str):
        self._ws = await websockets.connect(ws_url, max_size=50 * 1024 * 1024)
        self._recv_task = asyncio.create_task(self._recv_loop())
        log(f"CDP connected to {ws_url}")

    async def _recv_loop(self):
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if "id" in msg:
                    fut = self._pending.pop(msg["id"], None)
                    if fut and not fut.done():
                        if "error" in msg:
                            fut.set_exception(
                                RuntimeError(msg["error"].get("message", str(msg["error"])))
                            )
                        else:
                            fut.set_result(msg.get("result", {}))
                elif "method" in msg:
                    for handler in self._event_handlers.get(msg["method"], []):
                        try:
                            handler(msg.get("params", {}))
                        except Exception as exc:
                            log(f"Event handler error: {exc}")
        except websockets.ConnectionClosed:
            log("CDP WebSocket closed")
        except Exception as exc:
            log(f"CDP recv loop error: {exc}")

    def on(self, event: str, handler):
        self._event_handlers.setdefault(event, []).append(handler)

    async def send(self, method: str, params: dict | None = None, timeout: float = 30.0) -> dict:
        self._msg_id += 1
        mid = self._msg_id
        fut = asyncio.get_event_loop().create_future()
        self._pending[mid] = fut
        payload = {"id": mid, "method": method}
        if params:
            payload["params"] = params
        await self._ws.send(json.dumps(payload))
        return await asyncio.wait_for(fut, timeout=timeout)

    async def close(self):
        if self._recv_task:
            self._recv_task.cancel()
        if self._ws:
            await self._ws.close()


# ---------------------------------------------------------------------------
# BrowserManager — Chrome lifecycle
# ---------------------------------------------------------------------------

class BrowserManager:
    """Launches Chrome and connects via CDP.

    Chrome is launched in its own session (``start_new_session=True``) so it
    survives the MCP server process exiting.  On subsequent invocations the
    manager detects an already-running Chrome and reconnects to it instead of
    spawning a new instance.
    """

    def __init__(self):
        self.cdp = CDPConnection()
        self._launched_new = False

    # ------------------------------------------------------------------
    def _chrome_already_running(self) -> Optional[str]:
        """Return the CDP WebSocket URL if Chrome is already listening."""
        try:
            with urllib.request.urlopen(
                "http://localhost:9222/json", timeout=2
            ) as resp:
                tabs = json.loads(resp.read())
            for tab in tabs:
                if tab.get("type") == "page" and "webSocketDebuggerUrl" in tab:
                    return tab["webSocketDebuggerUrl"]
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    async def start(self):
        # Try to reuse an already-running Chrome first
        ws_url = self._chrome_already_running()
        if ws_url:
            log("Reusing existing Chrome instance")
        else:
            log("Launching Chrome …")
            subprocess.Popen(
                [
                    "google-chrome",
                    "--no-sandbox",
                    "--remote-debugging-port=9222",
                    "--display=:99",
                    "--window-size=1280,720",
                    "--user-data-dir=/home/agent/.browser-profile",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                    "--disable-default-apps",
                    "--disable-extensions",
                    # Restore the last open tab(s) so the user sees the
                    # same page after task completion / container restart.
                    "--restore-last-session",
                    # Suppress "Chrome didn't shut down correctly" infobar
                    "--hide-crash-restore-bubble",
                    "--disable-session-crashed-bubble",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                # Detach Chrome from MCP server process group so it
                # survives when the MCP server (and its parent docker-exec)
                # exits after the agent task completes.
                start_new_session=True,
            )
            self._launched_new = True
            ws_url = await self._wait_for_cdp()

        await self.cdp.connect(ws_url)

        # Enable required CDP domains
        await self.cdp.send("Page.enable")
        await self.cdp.send("Network.enable")
        await self.cdp.send("DOM.enable")
        await self.cdp.send("Accessibility.enable")
        log("Chrome ready — CDP domains enabled")

    async def _wait_for_cdp(self, timeout: float = 15.0) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen("http://localhost:9222/json") as resp:
                    tabs = json.loads(resp.read())
                for tab in tabs:
                    if tab.get("type") == "page" and "webSocketDebuggerUrl" in tab:
                        log(f"Found CDP target: {tab['webSocketDebuggerUrl']}")
                        return tab["webSocketDebuggerUrl"]
            except Exception:
                pass
            await asyncio.sleep(0.5)
        raise RuntimeError("Chrome did not become ready within timeout")

    async def disconnect(self):
        """Close the CDP WebSocket but leave Chrome running."""
        await self.cdp.close()


# ---------------------------------------------------------------------------
# WaitController — Page stability detection
# ---------------------------------------------------------------------------

class WaitController:
    """Detects network idle + DOM settle for page stability."""

    def __init__(self, cdp: CDPConnection):
        self._cdp = cdp
        self._pending_requests = 0
        cdp.on("Network.requestWillBeSent", self._on_request_start)
        cdp.on("Network.loadingFinished", self._on_request_end)
        cdp.on("Network.loadingFailed", self._on_request_end)

    def _on_request_start(self, params):
        self._pending_requests += 1

    def _on_request_end(self, params):
        self._pending_requests = max(0, self._pending_requests - 1)

    async def wait_for_stable(self, timeout: float = 10.0):
        """Wait until network is idle for 500ms, then settle 300ms more."""
        deadline = time.monotonic() + timeout
        idle_start = None
        while time.monotonic() < deadline:
            if self._pending_requests == 0:
                if idle_start is None:
                    idle_start = time.monotonic()
                elif time.monotonic() - idle_start >= 0.5:
                    break
            else:
                idle_start = None
            await asyncio.sleep(0.1)
        # Extra settle time for rendering
        await asyncio.sleep(0.3)


# ---------------------------------------------------------------------------
# PerceptionEngine — Manus AI-style page perception
# ---------------------------------------------------------------------------

# Interactive roles worth indexing
INTERACTIVE_ROLES = {
    "button", "link", "textbox", "checkbox", "radio",
    "combobox", "listbox", "menuitem", "tab", "switch",
    "searchbox", "slider", "spinbutton", "option", "menuitemcheckbox",
    "menuitemradio", "treeitem",
}


class PerceptionEngine:
    """Takes a snapshot: screenshot + indexed interactive elements."""

    def __init__(self, cdp: CDPConnection):
        self._cdp = cdp

    async def snapshot(self) -> tuple[str, list[dict], str]:
        """Return (base64_screenshot, indexed_elements, formatted_table)."""
        # Screenshot
        result = await self._cdp.send(
            "Page.captureScreenshot",
            {"format": "webp", "quality": 70},
        )
        screenshot_b64 = result["data"]

        # Get current URL and title
        url_info = ""
        try:
            frame_tree = await self._cdp.send("Page.getFrameTree")
            frame = frame_tree.get("frameTree", {}).get("frame", {})
            url_info = f"URL: {frame.get('url', 'unknown')}\nTitle: {frame.get('name', '') or frame.get('url', '')}"
        except Exception:
            pass

        # Accessibility tree
        elements = await self._get_interactive_elements()

        # Format table
        lines = []
        if url_info:
            lines.append(url_info)
            lines.append("")
        if elements:
            lines.append(f"Found {len(elements)} interactive elements:")
            lines.append(f"{'Idx':<5} {'Role':<14} {'Name':<50} {'Focused'}")
            lines.append("-" * 80)
            for el in elements:
                focused = "*" if el.get("focused") else ""
                name = el["name"][:48] if el["name"] else "(no name)"
                lines.append(f"{el['index']:<5} {el['role']:<14} {name:<50} {focused}")
        else:
            lines.append("No interactive elements found on page.")

        return screenshot_b64, elements, "\n".join(lines)

    async def _get_interactive_elements(self) -> list[dict]:
        """Extract interactive elements from the accessibility tree."""
        try:
            tree = await self._cdp.send("Accessibility.getFullAXTree")
        except Exception as exc:
            log(f"Failed to get AX tree: {exc}")
            return []

        nodes = tree.get("nodes", [])
        elements = []
        idx = 0

        for node in nodes:
            role_obj = node.get("role", {})
            role = role_obj.get("value", "") if isinstance(role_obj, dict) else str(role_obj)

            if role not in INTERACTIVE_ROLES:
                continue

            # Get name
            name_obj = node.get("name", {})
            name = name_obj.get("value", "") if isinstance(name_obj, dict) else str(name_obj)

            # Skip elements with no name and no value
            if not name:
                # Check properties for a value
                value = ""
                for prop in node.get("properties", []):
                    if prop.get("name") == "value":
                        val_obj = prop.get("value", {})
                        value = val_obj.get("value", "") if isinstance(val_obj, dict) else str(val_obj)
                        break
                if not value:
                    # Still include unnamed elements but mark them
                    pass

            backend_node_id = node.get("backendDOMNodeId")
            if not backend_node_id:
                continue

            # Check focused state
            focused = False
            for prop in node.get("properties", []):
                if prop.get("name") == "focused":
                    val_obj = prop.get("value", {})
                    focused = (val_obj.get("value", False) if isinstance(val_obj, dict) else False)
                    break

            elements.append({
                "index": idx,
                "role": role,
                "name": name,
                "backendNodeId": backend_node_id,
                "focused": focused,
            })
            idx += 1

        return elements

    async def get_click_point(self, backend_node_id: int) -> tuple[float, float]:
        """Get center coordinates of an element for clicking."""
        try:
            # Resolve to a remote object so we can call getBoxModel
            result = await self._cdp.send(
                "DOM.resolveNode", {"backendNodeId": backend_node_id}
            )
            object_id = result["object"]["objectId"]

            # Try to scroll into view first
            try:
                await self._cdp.send(
                    "DOM.scrollIntoViewIfNeeded", {"backendNodeId": backend_node_id}
                )
            except Exception:
                pass

            # Get box model
            box = await self._cdp.send(
                "DOM.getBoxModel", {"backendNodeId": backend_node_id}
            )
            content = box["model"]["content"]
            # content is [x1,y1, x2,y2, x3,y3, x4,y4] — take center
            xs = [content[i] for i in range(0, 8, 2)]
            ys = [content[i] for i in range(1, 8, 2)]
            cx = sum(xs) / 4
            cy = sum(ys) / 4

            # Release the object
            try:
                await self._cdp.send("Runtime.releaseObject", {"objectId": object_id})
            except Exception:
                pass

            return cx, cy
        except Exception as exc:
            log(f"Failed to get click point for node {backend_node_id}: {exc}")
            raise RuntimeError(f"Cannot locate element on page: {exc}")

    def find_by_name(self, elements: list[dict], name: str, role: str | None = None) -> dict | None:
        """Self-healing: find element by semantic name (case-insensitive substring)."""
        name_lower = name.lower()
        for el in elements:
            if role and el["role"] != role:
                continue
            if name_lower in (el["name"] or "").lower():
                return el
        return None


# ---------------------------------------------------------------------------
# ActionExecutor — CDP browser actions
# ---------------------------------------------------------------------------

class ActionExecutor:
    """Executes browser actions via CDP (click, type, scroll, key press)."""

    def __init__(self, cdp: CDPConnection, perception: PerceptionEngine):
        self._cdp = cdp
        self._perception = perception

    async def click(self, elements: list[dict], index: int):
        """Click an element by its index using 3-part mouse sequence."""
        if index < 0 or index >= len(elements):
            raise ValueError(f"Element index {index} out of range (0-{len(elements)-1})")

        el = elements[index]
        cx, cy = await self._perception.get_click_point(el["backendNodeId"])

        # 3-part mouse click: move → press → release
        await self._cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": cx, "y": cy,
        })
        await self._cdp.send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": cx, "y": cy,
            "button": "left", "clickCount": 1,
        })
        await self._cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": cx, "y": cy,
            "button": "left", "clickCount": 1,
        })

    async def type_text(self, elements: list[dict], index: int, text: str):
        """Click element to focus, select all, then type text."""
        # Focus the element first
        await self.click(elements, index)
        await asyncio.sleep(0.1)

        # Select all existing text (Ctrl+A)
        await self._cdp.send("Input.dispatchKeyEvent", {
            "type": "keyDown", "key": "a", "code": "KeyA",
            "windowsVirtualKeyCode": 65, "modifiers": 2,  # Ctrl
        })
        await self._cdp.send("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": "a", "code": "KeyA",
            "windowsVirtualKeyCode": 65, "modifiers": 2,
        })
        await asyncio.sleep(0.05)

        # Insert text
        await self._cdp.send("Input.insertText", {"text": text})

    async def scroll(self, direction: str, amount: int = 3):
        """Scroll the page. direction: up/down/left/right."""
        delta_x, delta_y = 0, 0
        pixels = amount * 120  # 120 pixels per "click" of scroll wheel
        if direction == "down":
            delta_y = pixels
        elif direction == "up":
            delta_y = -pixels
        elif direction == "right":
            delta_x = pixels
        elif direction == "left":
            delta_x = -pixels

        await self._cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseWheel",
            "x": 640, "y": 360,  # Center of 1280x720 viewport
            "deltaX": delta_x, "deltaY": delta_y,
        })

    async def press_key(self, key: str):
        """Press a single key (Enter, Tab, Escape, ArrowDown, etc.)."""
        key_map = {
            "Enter": {"key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13},
            "Tab": {"key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9},
            "Escape": {"key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27},
            "Backspace": {"key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8},
            "Delete": {"key": "Delete", "code": "Delete", "windowsVirtualKeyCode": 46},
            "ArrowUp": {"key": "ArrowUp", "code": "ArrowUp", "windowsVirtualKeyCode": 38},
            "ArrowDown": {"key": "ArrowDown", "code": "ArrowDown", "windowsVirtualKeyCode": 40},
            "ArrowLeft": {"key": "ArrowLeft", "code": "ArrowLeft", "windowsVirtualKeyCode": 37},
            "ArrowRight": {"key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39},
            "Space": {"key": " ", "code": "Space", "windowsVirtualKeyCode": 32},
        }

        info = key_map.get(key, {"key": key, "code": f"Key{key.upper()}", "windowsVirtualKeyCode": ord(key[0].upper()) if key else 0})

        await self._cdp.send("Input.dispatchKeyEvent", {
            "type": "keyDown", **info,
        })
        await self._cdp.send("Input.dispatchKeyEvent", {
            "type": "keyUp", **info,
        })


# ---------------------------------------------------------------------------
# MCPServer — JSON-RPC stdio protocol handler
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "browser_navigate",
        "description": "Navigate to a URL in the browser.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to navigate to"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "browser_snapshot",
        "description": "Take a screenshot and get a list of all interactive elements on the page with their indexes. Always call this after navigation or any action to see the current page state.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "browser_click",
        "description": "Click on an interactive element by its index from the snapshot.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "Element index from snapshot"},
            },
            "required": ["index"],
        },
    },
    {
        "name": "browser_type",
        "description": "Type text into an interactive element (textbox, searchbox, etc.) by its index. Clears existing content first.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "Element index from snapshot"},
                "text": {"type": "string", "description": "Text to type"},
            },
            "required": ["index", "text"],
        },
    },
    {
        "name": "browser_scroll",
        "description": "Scroll the page in a direction.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "left", "right"],
                    "description": "Scroll direction",
                },
                "amount": {
                    "type": "integer",
                    "description": "Number of scroll clicks (default 3)",
                    "default": 3,
                },
            },
            "required": ["direction"],
        },
    },
    {
        "name": "browser_press_key",
        "description": "Press a keyboard key (Enter, Tab, Escape, ArrowDown, ArrowUp, Backspace, Space, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key to press"},
            },
            "required": ["key"],
        },
    },
    {
        "name": "browser_wait",
        "description": "Wait for the page to become stable (network idle + rendering settle). Call this after actions that trigger page loads or AJAX requests.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "timeout": {
                    "type": "number",
                    "description": "Max wait time in seconds (default 10)",
                    "default": 10,
                },
            },
        },
    },
]


class MCPServer:
    """MCP JSON-RPC stdio server wrapping CDP browser automation."""

    def __init__(self):
        self.browser = BrowserManager()
        self.wait_ctrl: Optional[WaitController] = None
        self.perception: Optional[PerceptionEngine] = None
        self.actions: Optional[ActionExecutor] = None
        self._last_elements: list[dict] = []
        self._initialized = False

    async def _ensure_browser(self):
        """Lazy-start Chrome on first tool call."""
        if self._initialized:
            return
        await self.browser.start()
        self.wait_ctrl = WaitController(self.browser.cdp)
        self.perception = PerceptionEngine(self.browser.cdp)
        self.actions = ActionExecutor(self.browser.cdp, self.perception)
        self._initialized = True

    async def handle_message(self, msg: dict) -> dict | None:
        """Process a single JSON-RPC message and return the response."""
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            return self._response(msg_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "cdp-browser", "version": "1.0.0"},
            })

        if method == "notifications/initialized":
            return None  # No response for notifications

        if method == "ping":
            return self._response(msg_id, {})

        if method == "tools/list":
            return self._response(msg_id, {"tools": TOOLS})

        if method == "tools/call":
            return await self._handle_tool_call(msg_id, params)

        # Unknown method
        return self._error(msg_id, -32601, f"Method not found: {method}")

    async def _handle_tool_call(self, msg_id: int, params: dict) -> dict:
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        try:
            await self._ensure_browser()
            result = await self._dispatch_tool(tool_name, args)
            return self._response(msg_id, {"content": result})
        except Exception as exc:
            log(f"Tool error ({tool_name}): {exc}")
            return self._response(msg_id, {
                "content": [{"type": "text", "text": f"Error: {exc}"}],
                "isError": True,
            })

    async def _dispatch_tool(self, name: str, args: dict) -> list[dict]:
        """Dispatch to the appropriate tool handler."""

        if name == "browser_navigate":
            url = args["url"]
            log(f"Navigating to {url}")
            await self.browser.cdp.send("Page.navigate", {"url": url})
            await self.wait_ctrl.wait_for_stable()
            # Auto-snapshot after navigation
            screenshot, elements, table = await self.perception.snapshot()
            self._last_elements = elements
            return [
                {"type": "text", "text": f"Navigated to {url}\n\n{table}"},
                {"type": "image", "data": screenshot, "mimeType": "image/webp"},
            ]

        if name == "browser_snapshot":
            screenshot, elements, table = await self.perception.snapshot()
            self._last_elements = elements
            return [
                {"type": "text", "text": table},
                {"type": "image", "data": screenshot, "mimeType": "image/webp"},
            ]

        if name == "browser_click":
            index = args["index"]
            await self.actions.click(self._last_elements, index)
            el = self._last_elements[index]
            await asyncio.sleep(0.3)
            await self.wait_ctrl.wait_for_stable(timeout=5)
            # Auto-snapshot after click
            screenshot, elements, table = await self.perception.snapshot()
            self._last_elements = elements
            return [
                {"type": "text", "text": f"Clicked [{index}] {el['role']} \"{el['name']}\"\n\n{table}"},
                {"type": "image", "data": screenshot, "mimeType": "image/webp"},
            ]

        if name == "browser_type":
            index = args["index"]
            text = args["text"]
            await self.actions.type_text(self._last_elements, index, text)
            el = self._last_elements[index]
            await asyncio.sleep(0.2)
            # Auto-snapshot after typing
            screenshot, elements, table = await self.perception.snapshot()
            self._last_elements = elements
            return [
                {"type": "text", "text": f"Typed \"{text}\" into [{index}] {el['role']} \"{el['name']}\"\n\n{table}"},
                {"type": "image", "data": screenshot, "mimeType": "image/webp"},
            ]

        if name == "browser_scroll":
            direction = args["direction"]
            amount = args.get("amount", 3)
            await self.actions.scroll(direction, amount)
            await asyncio.sleep(0.3)
            # Auto-snapshot after scroll
            screenshot, elements, table = await self.perception.snapshot()
            self._last_elements = elements
            return [
                {"type": "text", "text": f"Scrolled {direction} ({amount} clicks)\n\n{table}"},
                {"type": "image", "data": screenshot, "mimeType": "image/webp"},
            ]

        if name == "browser_press_key":
            key = args["key"]
            await self.actions.press_key(key)
            await asyncio.sleep(0.3)
            await self.wait_ctrl.wait_for_stable(timeout=5)
            # Auto-snapshot after key press
            screenshot, elements, table = await self.perception.snapshot()
            self._last_elements = elements
            return [
                {"type": "text", "text": f"Pressed key: {key}\n\n{table}"},
                {"type": "image", "data": screenshot, "mimeType": "image/webp"},
            ]

        if name == "browser_wait":
            timeout = args.get("timeout", 10)
            await self.wait_ctrl.wait_for_stable(timeout=timeout)
            screenshot, elements, table = await self.perception.snapshot()
            self._last_elements = elements
            return [
                {"type": "text", "text": f"Waited for page stability\n\n{table}"},
                {"type": "image", "data": screenshot, "mimeType": "image/webp"},
            ]

        raise ValueError(f"Unknown tool: {name}")

    @staticmethod
    def _response(msg_id, result) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _error(msg_id, code, message) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# Main — stdio event loop
# ---------------------------------------------------------------------------

async def main():
    log("CDP MCP server starting …")
    server = MCPServer()

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    buffer = b""
    while True:
        try:
            chunk = await reader.read(65536)
            if not chunk:
                break
            buffer += chunk

            # Process all complete lines in the buffer
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    log(f"Invalid JSON: {line[:200]}")
                    continue

                response = await server.handle_message(msg)
                if response is not None:
                    out = json.dumps(response) + "\n"
                    sys.stdout.write(out)
                    sys.stdout.flush()

        except Exception as exc:
            log(f"Main loop error: {exc}")
            break

    log("CDP MCP server shutting down — Chrome stays alive")
    if server._initialized:
        await server.browser.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
