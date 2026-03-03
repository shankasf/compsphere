import asyncio
from typing import Optional

import docker

from config import settings
from core.logging_config import get_logger

logger = get_logger("compsphere.docker")


class DockerManager:
    def __init__(
        self,
        sandbox_image: str = settings.SANDBOX_IMAGE,
        profiles_path: str = settings.BROWSER_PROFILES_PATH,
    ):
        self.client = docker.from_env()
        self.sandbox_image = sandbox_image
        self.profiles_path = profiles_path
        logger.info(f"DockerManager initialized (image={sandbox_image})")

    async def create_container(self, user_id: str, session_id: str) -> dict:
        """Create a sandbox container for an agent session."""
        container_name = f"compshere-{session_id[:8]}"
        profile_path = f"{self.profiles_path}/{user_id}"

        logger.info(
            f"Creating container {container_name}",
            extra={"session_id": session_id},
        )

        def _create():
            container = self.client.containers.run(
                self.sandbox_image,
                name=container_name,
                detach=True,
                remove=False,
                cpu_count=1,
                mem_limit="2g",
                environment={"DISPLAY": ":99"},
                volumes={
                    profile_path: {
                        "bind": "/home/agent/.browser-profile",
                        "mode": "rw",
                    }
                },
                ports={"6080/tcp": None, "5900/tcp": None},
                network_mode="bridge",
            )
            container.reload()
            ports = container.ports
            vnc_port = int(
                ports.get("6080/tcp", [{}])[0].get("HostPort", 0)
            )
            return {
                "container_id": container.id,
                "container_name": container_name,
                "vnc_port": vnc_port,
            }

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _create)
            logger.info(
                f"Container {container_name} created (id={result['container_id'][:12]}, vnc_port={result['vnc_port']})",
                extra={"session_id": session_id, "container_id": result["container_id"][:12]},
            )
            return result
        except docker.errors.ImageNotFound:
            logger.error(
                f"Sandbox image '{self.sandbox_image}' not found",
                extra={"session_id": session_id},
            )
            raise
        except docker.errors.APIError as e:
            logger.error(
                f"Docker API error creating container: {e}",
                exc_info=True,
                extra={"session_id": session_id},
            )
            raise

    async def destroy_container(self, container_id: str):
        """Stop and remove a container."""
        log_extra = {"container_id": container_id[:12]}

        def _destroy():
            try:
                container = self.client.containers.get(container_id)
                container.stop(timeout=10)
                container.remove(force=True)
                logger.info(f"Container {container_id[:12]} destroyed", extra=log_extra)
            except docker.errors.NotFound:
                logger.warning(f"Container {container_id[:12]} not found (already removed?)", extra=log_extra)
            except Exception as e:
                logger.error(
                    f"Error destroying container {container_id[:12]}: {e}",
                    exc_info=True,
                    extra=log_extra,
                )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _destroy)

    async def exec_in_container(self, container_id: str, command: str) -> str:
        """Execute a command inside the container."""
        log_extra = {"container_id": container_id[:12]}

        def _exec():
            try:
                container = self.client.containers.get(container_id)
                result = container.exec_run(command, user="agent")
                return result.output.decode("utf-8", errors="replace")
            except docker.errors.NotFound:
                logger.error(f"Container {container_id[:12]} not found for exec", extra=log_extra)
                raise
            except Exception as e:
                logger.error(
                    f"Error executing command in container {container_id[:12]}: {e}",
                    exc_info=True,
                    extra=log_extra,
                )
                raise

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _exec)

    async def get_container_status(self, container_id: str) -> Optional[str]:
        """Get container status."""

        def _status():
            try:
                container = self.client.containers.get(container_id)
                return container.status
            except docker.errors.NotFound:
                logger.debug(f"Container {container_id[:12]} not found", extra={"container_id": container_id[:12]})
                return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _status)
