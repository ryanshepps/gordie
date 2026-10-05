import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

from apscheduler.schedulers.background import BackgroundScheduler
from duckdb import DuckDBPyConnection
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from quart import Quart
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from gordie import (
    AccessDecision,
    AccessRequest,
    Action,
    ConversationMemory,
    Plugins,
    create_agent,
    create_app,
)
from gordie.agent.agent_state import AgentState
from gordie.integrations.statistics import StatisticsFiles
from gordie.module.llm import make_llm
from gordie.runtime import current_runtime


class FixtureStorage:
    def __init__(self, directory: Path, owner: str) -> None:
        self.owner = owner
        self.directory = directory
        self.events: list[str] = []
        self._engine = create_engine("sqlite+pysqlite:///:memory:")
        self._sessions = sessionmaker(bind=self._engine)
        self._checkpoint = InMemorySaver()
        self._memory = ConversationMemory(InMemoryStore())
        self._statistics = StatisticsFiles(directory)

    def session(self) -> Session:
        return self._sessions()

    def checkpoint(self) -> InMemorySaver:
        return self._checkpoint

    def memory(self) -> ConversationMemory:
        return self._memory

    def data_path(self, filename: str) -> Path:
        return self.directory / filename

    def stats_connection(self, filename: str) -> DuckDBPyConnection:
        return self._statistics.connection(filename)

    def reset_stats(self, filename: str) -> None:
        self._statistics.reset(filename)

    def prepare(self) -> None:
        self.events.append("prepare")

    def close(self) -> None:
        self._statistics.close()
        self._engine.dispose()
        self.events.append("close")


@dataclass
class FixtureModels:
    response: str
    calls: int = 0

    def chat(self, *, temperature: float = 0, model: str | None = None) -> BaseChatModel:
        self.calls += 1
        return FakeMessagesListChatModel(responses=[AIMessage(content=self.response)])


def register_probe(app: Quart) -> None:
    @app.get("/probe")
    async def probe() -> dict[str, str]:
        storage = current_runtime().plugins.storage
        with storage.session() as session:
            owner = str(
                session.execute(
                    text("SELECT :owner"), {"owner": storage.data_path("x").parent.name}
                ).scalar_one()
            )
        store = storage.memory().store
        store.put(("probe",), "owner", {"owner": owner})
        await asyncio.sleep(0)
        saved = store.get(("probe",), "owner")
        assert saved is not None
        return {
            "database": owner,
            "memory": str(saved.value["owner"]),
            "model": str(make_llm().invoke("hello").content),
        }


async def test_http_plugins_use_isolated_storage_memory_and_model_caches(tmp_path: Path) -> None:
    first_storage = FixtureStorage(tmp_path / "first", "first")
    second_storage = FixtureStorage(tmp_path / "second", "second")
    first_models = FixtureModels("first")
    second_models = FixtureModels("second")
    first = create_app(Plugins(first_storage, first_models, routes=(register_probe,)))
    second = create_app(Plugins(second_storage, second_models, routes=(register_probe,)))
    assert first_storage.events == second_storage.events == []

    async with first.test_app(), second.test_app():
        clients = (first.test_client(), second.test_client())
        for _ in range(2):
            responses = await asyncio.gather(*(client.get("/probe") for client in clients))
            assert [await response.get_json() for response in responses] == [
                {"database": "first", "memory": "first", "model": "first"},
                {"database": "second", "memory": "second", "model": "second"},
            ]

    assert first_models.calls == second_models.calls == 1
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
) -> None:
    policy = DeniedAccess()
    models = FixtureModels("should not be used")
    agent = create_agent(Plugins(FixtureStorage(tmp_path, "denied"), models, access=policy))
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
    assert models.calls == 0
    assert policy.requests == [
        AccessRequest("user-1", Action.QUESTION, "Who should I trade?"),
        AccessRequest("user-1", Action.QUESTION, "Can I ask now?"),
    ]


class ToolModel(FakeMessagesListChatModel):
    def bind_tools(
        self, tools: Sequence[object], *, tool_choice: str | None = None, **kwargs: object
    ) -> BaseChatModel:
        return self


@dataclass
class ToolModels:
    def chat(self, *, temperature: float = 0, model: str | None = None) -> BaseChatModel:
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


async def test_injected_tool_executes_with_the_application_runtime(tmp_path: Path) -> None:
    @tool(description="Return the hosted integration's storage location.")
    def hosted_feature() -> str:
        return str(current_runtime().plugins.storage.data_path("feature"))

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

    app = create_app(
        Plugins(
            FixtureStorage(tmp_path, "tools"),
            ToolModels(),
            tools=(hosted_feature,),
            routes=(register_ask,),
        )
    )
    async with app.test_app():
        response = await app.test_client().get("/ask")
        assert response.status_code == 200
        assert await response.get_json() == {"tool_output": str(tmp_path / "feature")}


async def test_scheduled_plugin_runs_with_its_runtime_and_stops_before_storage(
    tmp_path: Path,
) -> None:
    storage = FixtureStorage(tmp_path, "jobs")
    finished = Event()
    observed: list[Path] = []

    def job(filename: str) -> None:
        observed.append(current_runtime().plugins.storage.data_path(filename))
        finished.set()

    def register_jobs(scheduler: BackgroundScheduler) -> None:
        scheduler.add_job(job, "date", run_date=datetime.now(UTC), args=("job",))

    app = create_app(Plugins(storage, FixtureModels("jobs"), jobs=(register_jobs,)))
    async with app.test_app():
        assert await asyncio.to_thread(finished.wait, 5)
    assert observed == [tmp_path / "job"]
    assert storage.events == ["prepare", "close"]


def test_team_access_policy_stops_onboarding_before_yahoo_or_database_calls(tmp_path: Path) -> None:
    from gordie.runtime import Runtime
    from gordie.tools.yahoo.onboard_user_team import onboard_user_team

    policy = DeniedAccess()
    runtime = Runtime(
        Plugins(FixtureStorage(tmp_path, "teams"), FixtureModels("unused"), access=policy)
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


async def test_creem_extension_adds_its_routes_and_tools_only_when_selected(tmp_path: Path) -> None:
    from gordie.integrations.creem.plugin import with_creem

    plugins = Plugins(FixtureStorage(tmp_path, "creem"), FixtureModels("unused"))
    hosted = with_creem(plugins)
    assert {tool.name for tool in hosted.tools} == {
        "get_subscription_status",
        "generate_checkout_link",
        "generate_portal_link",
    }
    assert plugins.tools == plugins.routes == ()
    app = create_app(hosted)
    response = await app.test_client().post("/webhooks/creem", data=b"{}")
    assert response.status_code == 403
    app.runtime.close()
