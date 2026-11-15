"""Lifecycle wrapper for the asynchronous gRPC server."""

from __future__ import annotations

import logging

import grpc

from . import config as _config  # noqa: F401 - sets up generated/ on sys.path
import payment_pb2_grpc as payment_pb2_grpc  # noqa: E402

from .config import Settings, settings as default_settings  # noqa: E402
from .grpc_servicer import PaymentServicer  # noqa: E402
from .services.payment_service import PaymentService  # noqa: E402

logger = logging.getLogger("payment-service.grpc-server")


class GrpcServer:
    def __init__(
        self,
        service: PaymentService,
        *,
        host: str | None = None,
        port: int | None = None,
        config: Settings | None = None,
    ) -> None:
        self.service = service
        self.settings = config or default_settings
        self.host = host or self.settings.grpc_host
        self.port = self.settings.grpc_port if port is None else port
        self._server: grpc.aio.Server | None = None
        self.bound_port: int | None = None

    @property
    def running(self) -> bool:
        return self._server is not None

    async def start(self) -> int:
        if self._server is not None:
            return self.bound_port or self.port

        server = grpc.aio.server()
        payment_pb2_grpc.add_PaymentServiceServicer_to_server(
            PaymentServicer(self.service, config=self.settings), server
        )
        bound_port = server.add_insecure_port(f"{self.host}:{self.port}")
        if bound_port == 0:
            raise RuntimeError(
                f"Could not bind the gRPC server on {self.host}:{self.port}"
            )
        await server.start()
        self._server = server
        self.bound_port = bound_port
        logger.info("gRPC server listening on %s:%s", self.host, bound_port)
        return bound_port

    async def stop(self, grace_seconds: float = 5.0) -> None:
        server, self._server = self._server, None
        if server is not None:
            await server.stop(grace=grace_seconds)
            logger.info("gRPC server stopped")
