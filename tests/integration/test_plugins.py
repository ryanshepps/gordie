import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from unittest.mock import Mock

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from langchain_core.embeddings.fake import DeterministicFakeEmbedding
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from pytest import MonkeyPatch
from quart import Quart, request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from gordie import (
    AccessDecision,
    AccessRequest,
    Action,
    IncomingMessage,
    MessageContext,
    MessageHandler,
    OutgoingMessage,
    Plugins,
    create_agent,
    create_app,
)
from gordie.agent.agent_state import AgentState
from gordie.agent.memory_store import get_memory_store
from gordie.module.llm import make_llm
from gordie.module.model_provider import OpenRouterModels
from gordie.module.paths import data_path
from gordie.runtime import current_runtime


class FixtureStorage:
    def __init__(self, owner: str) -> None:
        self.events: list[str] = []
        self._engine = create_engine(
            "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        self._sessions = sessionmaker(bind=self._engine)
        self._checkpoint = InMemorySaver()
        with self._engine.begin() as connection:
            connection.execute(text("CREATE TABLE owner (value VARCHAR)"))
            connection.execute(text("INSERT INTO owner VALUES (:owner)"), {"owner": owner})

    def session(self) -> Session:
        return self._sessions()

    def checkpoint(self) -> InMemorySaver:
        return self._checkpoint

    def prepare(self) -> None:
        self.events.append("prepare")

    def close(self) -> None:
        self._engine.dispose()
        self.events.append("close")


@pytest.fixture(autouse=True)
def embedded_services(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GORDIE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("gordie.application.register_application_jobs", lambda scheduler: None)


def register_probe(app: Quart) -> None:
    @app.get("/probe")
    async def probe() -> dict[str, str]:
        storage = current_runtime().plugins.storage
        with storage.session() as session:
            owner = str(session.execute(text("SELECT value FROM owner")).scalar_one())
        store = get_memory_store()
        store.put(("probe",), "owner", {"owner": owner})
        await asyncio.sleep(0)
        saved = store.get(("probe",), "owner")
        assert saved is not None
        return {
            "database": owner,
            "memory": str(saved.value["owner"]),
            "model": str(make_llm().invoke("hello").content),
        }


async def test_http_apps_use_isolated_storage_and_embedded_resources(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    first_storage = FixtureStorage("first")
    second_storage = FixtureStorage("second")
    calls: list[str] = []

    def chat(
        provider: OpenRouterModels, *, temperature: float = 0, model: str | None = None
    ) -> BaseChatModel:
        calls.append(provider.model)
        return FakeMessagesListChatModel(responses=[AIMessage(content=provider.model)])

    monkeypatch.setattr(OpenRouterModels, "chat", chat)
    monkeypatch.setattr(
        OpenRouterModels, "embeddings", lambda self: DeterministicFakeEmbedding(size=1536)
    )
    first = create_app(Plugins(first_storage), openrouter_api_key="first-key", model="first")
    second = create_app(Plugins(second_storage), openrouter_api_key="second-key", model="second")
    register_probe(first)
    register_probe(second)
    assert first_storage.events == second_storage.events == []

    async with first.test_app(), second.test_app():
        clients = (first.test_client(), second.test_client())
        for _ in range(2):
            responses = await asyncio.gather(*(client.get("/probe") for client in clients))
            assert [await response.get_json() for response in responses] == [
                {"database": "first", "memory": "first", "model": "first"},
                {"database": "second", "memory": "second", "model": "second"},
            ]

    assert calls == ["first", "second"]
    assert first_storage.events == second_storage.events == ["prepare", "close"]


@dataclass
class DeniedAccess:
    requests: list[AccessRequest] = field(default_factory=list)
    response: str = "Upgrade using https://billing.example/checkout"

    def evaluate(self, request: AccessRequest) -> AccessDecision:
        self.requests.append(request)
        return AccessDecision(False, self.response)


async def test_public_agent_enforces_access_before_models_or_account_queries(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    policy = DeniedAccess()
    model_factory = Mock(side_effect=AssertionError("Denied access must not invoke a model"))
    monkeypatch.setattr(OpenRouterModels, "chat", model_factory)
    agent = create_agent(
        Plugins(FixtureStorage("denied"), access=policy),
        openrouter_api_key="test-key",
        model="openai/gpt-4o-mini",
    )
    state: AgentState = {
        "user_id": "user-1",
        "messages": [HumanMessage(content="Who should I trade?")],
    }
    result = await agent.ainvoke(state, {"configurable": {"thread_id": "thread-1"}})
    assert result.get("response") == "Upgrade using https://billing.example/checkout"

    policy.response = "Your plan is being updated."
    follow_up: AgentState = {
        "user_id": "user-1",
        "messages": [HumanMessage(content="Can I ask now?")],
    }
    result = await agent.ainvoke(follow_up, {"configurable": {"thread_id": "thread-1"}})
    agent.close()

    assert result.get("response") == "Your plan is being updated."
    model_factory.assert_not_called()
    assert policy.requests == [
        AccessRequest("user-1", Action.QUESTION, "Who should I trade?"),
        AccessRequest("user-1", Action.QUESTION, "Can I ask now?"),
    ]


class ToolModel(FakeMessagesListChatModel):
    def bind_tools(
        self, tools: Sequence[object], *, tool_choice: str | None = None, **kwargs: object
    ) -> BaseChatModel:
        return self


def tool_model() -> BaseChatModel:
    return ToolModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "hosted_feature", "args": {}, "id": "call-1", "type": "tool_call"}
                ],
            ),
            AIMessage(content="Hosted feature completed"),
        ]
    )


async def test_injected_tool_executes_with_the_application_runtime(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    @tool(description="Return the hosted integration's storage location.")
    def hosted_feature() -> str:
        return str(data_path("feature"))

    def register_ask(app: Quart) -> None:
        @app.get("/ask")
        async def ask() -> dict[str, str]:
            from gordie.agent.supervisor import create_supervisor_agent

            supervisor = create_supervisor_agent("Use hosted_feature to answer.")
            result = await asyncio.to_thread(
                supervisor.invoke,
                {"messages": [HumanMessage(content="Run the hosted feature")]},
                {"configurable": {"thread_id": "tool-thread"}},
            )
            outputs = [
                str(message.content) for message in result["messages"] if message.type == "tool"
            ]
            return {"tool_output": outputs[0]}

    monkeypatch.setattr(OpenRouterModels, "chat", lambda self, **kwargs: tool_model())
    app = create_app(
        Plugins(FixtureStorage("tools"), extra_tools=(hosted_feature,)),
        openrouter_api_key="test-key",
        model="openai/gpt-4o-mini",
    )
    register_ask(app)
    async with app.test_app():
        response = await app.test_client().get("/ask")
        assert response.status_code == 200
        assert await response.get_json() == {"tool_output": str(tmp_path / "feature")}


async def test_embedded_jobs_run_with_their_runtime_and_stop_before_storage(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    storage = FixtureStorage("jobs")
    finished = Event()
    observed: list[Path] = []

    def job(filename: str) -> None:
        observed.append(data_path(filename))
        finished.set()

    def register_jobs(scheduler: BackgroundScheduler) -> None:
        scheduler.add_job(job, "date", run_date=datetime.now(UTC), args=("job",))

    monkeypatch.setattr("gordie.application.register_application_jobs", register_jobs)
    app = create_app(Plugins(storage), openrouter_api_key="test-key", model="openai/gpt-4o-mini")
    async with app.test_app():
        assert await asyncio.to_thread(finished.wait, 5)
    assert observed == [tmp_path / "job"]
    assert storage.events == ["prepare", "close"]


def test_team_access_policy_stops_onboarding_before_yahoo_or_database_calls(tmp_path: Path) -> None:
    from gordie.runtime import Runtime
    from gordie.tools.yahoo.onboard_user_team import onboard_user_team

    policy = DeniedAccess()
    runtime = Runtime(
        Plugins(FixtureStorage("teams"), access=policy),
        openrouter_api_key="test-key",
        model="z-ai/glm-5.3-flash",
    )
    with runtime.activate():
        result = onboard_user_team.invoke(
            {
                "game_key": "423",
                "game_code": "nhl",
                "league_id": 1,
                "team_name": "Team",
                "team_id": 1,
                "state": {"user_id": "user-1"},
            }
        )
    runtime.close()
    assert result == "Upgrade using https://billing.example/checkout"
    assert policy.requests == [AccessRequest("user-1", Action.CONNECT_TEAM)]


class RecordingCommunication:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.sent: list[OutgoingMessage] = []
        self.handler: MessageHandler | None = None
        self.storage_owners: list[object] = []

    def register(self, app: Quart, handle_message: MessageHandler) -> None:
        self.events.append("communication.register")
        self.handler = handle_message

        @app.post("/messages")
        async def inbound() -> dict[str, str | None]:
            payload = await request.get_json()
            message = IncomingMessage(
                context=MessageContext(
                    user_id="user-1",
                    thread_id="communication-thread",
                    external_id="user@example.com",
                    recipient="+15555550100",
                ),
                text=str(payload["text"]),
            )
            reply = await handle_message(message)
            return {"response": reply.text if reply else None}

    def start(self) -> None:
        self.events.append("communication.start")

    def send(self, message: OutgoingMessage) -> None:
        self.storage_owners.append(current_runtime().plugins.storage)
        self.sent.append(message)
        self.events.append("communication.send")

    def close(self) -> None:
        self.events.append("communication.close")


async def test_communication_routes_inbound_messages_delivers_denials_and_owns_lifecycle() -> None:
    storage = FixtureStorage("communication")
    communication = RecordingCommunication(storage.events)
    policy = DeniedAccess()
    app = create_app(
        Plugins(storage, access=policy, communication=communication),
        openrouter_api_key="test-key",
        model="openai/gpt-4o-mini",
    )
    assert storage.events == ["communication.register"]

    async with app.test_app():
        response = await app.test_client().post("/messages", json={"text": "Who should I trade?"})
        assert response.status_code == 200
        assert await response.get_json() == {"response": policy.response}

    assert communication.sent == [
        OutgoingMessage(
            MessageContext("user-1", "communication-thread", "user@example.com", "+15555550100"),
            policy.response,
        )
    ]
    assert communication.storage_owners == [storage]
    assert storage.events == [
        "communication.register",
        "prepare",
        "communication.start",
        "communication.send",
        "communication.close",
        "close",
    ]


async def test_communication_listener_callback_uses_its_owner_outside_an_http_request() -> None:
    storage = FixtureStorage("listener")
    communication = RecordingCommunication(storage.events)
    app = create_app(
        Plugins(storage, access=DeniedAccess(), communication=communication),
        openrouter_api_key="test-key",
        model="openai/gpt-4o-mini",
    )
    message = IncomingMessage(
        MessageContext("listener-user", "listener-thread", "user@example.com", "chat-42"),
        "Hello",
    )
    async with app.test_app():
        assert communication.handler is not None
        reply = await communication.handler(message)
    assert reply == OutgoingMessage(message.context, DeniedAccess().response)
    assert communication.sent == [reply]
    assert communication.storage_owners == [storage]


async def test_agent_receives_and_delivers_the_final_rewritten_response(
    monkeypatch: MonkeyPatch,
) -> None:
    storage = FixtureStorage("agent-communication")
    communication = RecordingCommunication(storage.events)
    monkeypatch.setattr("gordie.agent.context_node.check_oauth_status", lambda user_id: True)
    monkeypatch.setattr(
        "gordie.agent.context_node._fetch_onboarded_teams",
        lambda user_id: [{"league_id": "1", "team_id": "2", "sport": "nhl"}],
    )

    def chat(
        provider: OpenRouterModels, *, temperature: float = 0, model: str | None = None
    ) -> BaseChatModel:
        responses: list[BaseMessage] = (
            [AIMessage(content="Final rewritten advice")]
            if temperature == 0.5
            else [AIMessage(content="Draft advice"), AIMessage(content='{"passed": true}')]
        )
        return ToolModel(responses=responses)

    monkeypatch.setattr(OpenRouterModels, "chat", chat)
    agent = create_agent(
        Plugins(storage, communication=communication),
        openrouter_api_key="test-key",
        model="openai/gpt-4o-mini",
    )
    message = IncomingMessage(
        MessageContext("user-1", "final-response-thread", "user@example.com", "chat-42"),
        "Help with my team",
    )
    try:
        reply = await agent.areceive(message)
    finally:
        agent.close()
    assert reply == OutgoingMessage(message.context, "Final rewritten advice")
    assert communication.sent == [reply]


def test_communication_delivery_failure_reaches_the_caller(monkeypatch: MonkeyPatch) -> None:
    storage = FixtureStorage("failed-delivery")
    communication = RecordingCommunication(storage.events)

    def fail_send(message: OutgoingMessage) -> None:
        raise RuntimeError("Provider unavailable")

    monkeypatch.setattr(communication, "send", fail_send)
    agent = create_agent(
        Plugins(storage, access=DeniedAccess(), communication=communication),
        openrouter_api_key="test-key",
        model="openai/gpt-4o-mini",
    )
    message = IncomingMessage(
        MessageContext("user-1", "failed-delivery-thread", "user@example.com", "chat-42"),
        "Hello",
    )
    try:
        with pytest.raises(RuntimeError, match="Provider unavailable"):
            agent.receive(message)
    finally:
        agent.close()
