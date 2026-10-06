import asyncio
from collections.abc import AsyncGenerator, Callable
from functools import partial

from apscheduler.schedulers.background import BackgroundScheduler
from hypercorn.typing import ASGIReceiveCallable, ASGISendCallable, Scope
from quart import Quart

from gordie.communication import receive_message
from gordie.plugins import IncomingMessage, OutgoingMessage, Plugins
from gordie.runtime import Runtime
from gordie.scheduled.jobs import register_application_jobs
from gordie.server.routes.oauth_routes import register_oauth_routes


class Application(Quart):
    def __init__(self, runtime: Runtime) -> None:
        super().__init__("gordie")
        self.runtime = runtime

    async def asgi_app(
        self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        with self.runtime.activate():
            await super().asgi_app(scope, receive, send)


def create_app(plugins: Plugins) -> Application:
    runtime = Runtime(plugins)
    app = Application(runtime)
    register_oauth_routes(app)
    communication = plugins.communication
    if communication is not None:

        async def handle_message(message: IncomingMessage) -> OutgoingMessage | None:
            return await asyncio.to_thread(runtime.run, receive_message, message)

        with runtime.activate():
            communication.register(app, handle_message)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.while_serving
    async def lifespan() -> AsyncGenerator[None]:
        scheduler = BackgroundScheduler()
        try:
            await asyncio.to_thread(runtime.run, plugins.storage.prepare)
            if communication is not None:
                await asyncio.to_thread(runtime.run, communication.start)
            with runtime.activate():
                register_application_jobs(scheduler)
            for job in scheduler.get_jobs():
                function: Callable[..., object] = job.func
                job.modify(func=partial(runtime.run, function))
            if scheduler.get_jobs():
                scheduler.start()
            yield
        finally:
            if scheduler.running:
                await asyncio.to_thread(scheduler.shutdown, wait=True)
            await asyncio.to_thread(runtime.close)

    return app
