import asyncio

import websockets

from core.logging_config import get_logger

logger = get_logger("compsphere.vnc")

MAX_CONNECT_RETRIES = 10
RETRY_DELAY_SECONDS = 1.0


async def vnc_proxy(
    client_ws,
    container_host: str,
    container_vnc_port: int,
):
    """Proxy WebSocket frames between a frontend NoVNC client and the
    container's websockify endpoint."""
    target_url = f"ws://{container_host}:{container_vnc_port}/websockify"
    log_extra = {"ws_event": "vnc_proxy"}

    logger.info(f"VNC proxy connecting to {target_url}", extra=log_extra)

    # Retry connection — websockify inside the container may take a few
    # seconds to start (supervisord sleep + startup time).
    server_ws = None
    for attempt in range(1, MAX_CONNECT_RETRIES + 1):
        try:
            server_ws = await websockets.connect(
                target_url, subprotocols=["binary"]
            )
            logger.info(
                f"VNC proxy connected to {target_url} (attempt {attempt})",
                extra=log_extra,
            )
            break
        except (ConnectionRefusedError, OSError) as e:
            if attempt == MAX_CONNECT_RETRIES:
                logger.error(
                    f"VNC proxy: failed to connect after {MAX_CONNECT_RETRIES} "
                    f"attempts to {target_url}: {e}",
                    extra=log_extra,
                )
                await client_ws.close(code=1011, reason="VNC backend unreachable")
                return
            logger.debug(
                f"VNC proxy: attempt {attempt} refused, retrying in "
                f"{RETRY_DELAY_SECONDS}s...",
                extra=log_extra,
            )
            await asyncio.sleep(RETRY_DELAY_SECONDS)

    if server_ws is None:
        await client_ws.close(code=1011, reason="VNC backend unreachable")
        return

    try:
        async def client_to_server():
            try:
                async for msg in client_ws.iter_bytes():
                    await server_ws.send(msg)
            except Exception as e:
                logger.debug(f"VNC client->server stream ended: {type(e).__name__}", extra=log_extra)

        async def server_to_client():
            try:
                async for msg in server_ws:
                    if isinstance(msg, bytes):
                        await client_ws.send_bytes(msg)
                    else:
                        await client_ws.send_text(msg)
            except Exception as e:
                logger.debug(f"VNC server->client stream ended: {type(e).__name__}", extra=log_extra)

        done, pending = await asyncio.wait(
            [
                asyncio.create_task(client_to_server()),
                asyncio.create_task(server_to_client()),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

        logger.info("VNC proxy session ended normally", extra=log_extra)

    except websockets.exceptions.ConnectionClosedError:
        logger.info("VNC proxy: remote websockify connection closed", extra=log_extra)
    except Exception as e:
        logger.error(
            f"VNC proxy error: {type(e).__name__}: {e}",
            exc_info=True,
            extra=log_extra,
        )
    finally:
        await server_ws.close()
