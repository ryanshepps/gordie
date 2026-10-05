# Configuring Gordie integrations

`create_app(plugins)` builds a Quart application. `create_agent(plugins)` builds
an agent for callers that manage their own HTTP or messaging service. Both accept
the same immutable `Plugins` configuration, and neither opens connections or
starts jobs during construction.

```python
from pathlib import Path

from gordie import Plugins, create_app
from gordie.integrations.models import EnvironmentModels
from gordie.integrations.postgres import PostgresStorage

plugins = Plugins(
    storage=PostgresStorage(
        database_url="postgresql://localhost/gordie",
        data_directory=Path("/var/lib/gordie/stats"),
    ),
    models=EnvironmentModels(provider="openai", model="gpt-4o-mini"),
)
app = create_app(plugins)
```

## Extension points

| Field | Contract | Default behavior |
| --- | --- | --- |
| `storage` | `Storage`: sessions, checkpoints, memory, statistics files/connections, preparation, shutdown | Required |
| `models` | `Models.chat(temperature=..., model=...)` returns a LangChain chat model | Required |
| `access` | `AccessPolicy.evaluate(AccessRequest)` returns `AccessDecision` | Allow all actions |
| `tools` | Tuple of LangChain tools added to the supervisor | No extra tools |
| `routes` | Tuple of callables that register routes on the Quart app | Yahoo callback and health only |
| `jobs` | Tuple of callables that register synchronous APScheduler jobs | No background jobs |

Storage owns resource creation and cleanup. The existing repositories use
PostgreSQL SQL through SQLAlchemy sessions, and statistics tools use DuckDB.
`Storage` lets deployments replace connection configuration, checkpoint and
memory implementations, file locations, and lifecycle management. Changing the
database engine or SQL dialect would also require adapting the repositories.

`ConversationMemory(store, search_enabled=False)` accepts a LangGraph `BaseStore`.
The built-in implementation uses optional OpenAI embeddings. A deployment can
provide its own store and embedding implementation without changing agent code.

An access request identifies the canonical user and either `Action.QUESTION` or
`Action.CONNECT_TEAM`. Question requests include the user's message. A denied
decision supplies the final response directly; Gordie does not call the model,
Yahoo, or billing code to explain the denial. Team connection tools consult the
same policy before making account changes.

## Existing integrations

`gordie.integrations.defaults.default_plugins()` assembles PostgreSQL storage, environment-selected
OpenAI or Anthropic models, maintenance/statistics jobs, and optional Creem billing.
The CLI uses this assembly to preserve environment-based setup.

Creem can also be selected explicitly:

```python
from gordie import create_app
from gordie.integrations.creem.plugin import with_creem

app = create_app(with_creem(plugins))
```

For explicit assembly, pass a `Plugins` object without Creem to `with_creem`.
The helper returns a new configuration with a subscription access policy, checkout
and portal tools, and the Creem webhook. Existing environment credentials configure
the Creem implementation. Do not apply it twice to a configuration that already
includes Creem.

All current implementations remain in `gordie.integrations`. A future private
package can implement these protocols and supply tools/routes/jobs, then depend
on the public Gordie package. Core agent code imports the contracts and active
runtime rather than payment or infrastructure implementations.

## Runtime ownership

Each application or agent owns its own runtime. Model, subagent, and graph caches
are scoped to that runtime; storage owns checkpoints, memory, database sessions,
and statistics connections. Create fresh plugin implementations for each app.

HTTP requests, registered routes, agent invocations, and scheduled jobs run within
their owner's runtime. Jobs retain their configured arguments. Application startup
calls `storage.prepare()` before starting jobs; shutdown waits for jobs before
calling `storage.close()`.

The standalone agent assumes storage has already been prepared. Invoke it with
`agent.invoke(state, config)` or `await agent.ainvoke(state, config)`, and call
`agent.close()` after outstanding invocations finish. Async invocation runs the
existing synchronous agent pipeline in a worker thread.

For integration route handlers, `app.runtime.run(callable)` runs synchronous
work in the application's context. Work launched using `asyncio.to_thread`
inherits that context. Do not start an unmanaged thread that relies on Gordie's
runtime; use a registered job or explicitly call `app.runtime.run` in that thread.
