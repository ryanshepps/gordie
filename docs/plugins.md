# Configuring Gordie integrations

`create_app(plugins)` builds a Quart application. `create_agent(plugins)` builds
an agent for callers that manage their own messaging service. Both accept the
same immutable configuration with three extension points.

```python
from gordie import Plugins, create_app
from gordie.integrations.postgres import PostgresStorage

plugins = Plugins(
    storage=PostgresStorage(database_url="postgresql://localhost/gordie"),
)
app = create_app(plugins)
```

## Extension points

| Field | Contract | Default behavior |
| --- | --- | --- |
| `storage` | `Storage`: database sessions, checkpoints, preparation, shutdown | Required |
| `access` | `AccessPolicy.evaluate(AccessRequest)` returns `AccessDecision` | Allow all actions |
| `extra_tools` | Tuple of LangChain tools added to the supervisor | No extra tools |

### Storage

`session()` returns a SQLAlchemy session. `checkpoint()` returns a LangGraph
checkpoint saver. `prepare()` initializes the database before application startup;
`close()` releases the implementation's resources after outstanding work finishes.

The existing repositories use PostgreSQL SQL through SQLAlchemy sessions.
Supabase can provide the PostgreSQL database through its connection URL, or a
private package can supply its own implementation of `Storage`. Using Supabase's
HTTP database API or another SQL dialect would also require adapting repositories.

The bundled `PostgresStorage(database_url)` implementation remains in
`gordie.integrations`. It owns connection pooling, migrations, and the database
checkpointer. Existing migration history is retained.

### Access policy

An `AccessRequest` identifies the canonical `user_id` and either `Action.QUESTION`
or `Action.CONNECT_TEAM`. Question requests include the user's `message`.

`AccessDecision(allowed, response="")` permits or denies the action. A denied
decision supplies the final response directly; Gordie does not call the model or
Yahoo to explain the denial. The policy is reevaluated on each request, including
a conversation with a previous denial. Team connection tools consult the same
policy before making account changes.

### Extra tools

Pass a tuple of LangChain tools as `extra_tools`. Gordie adds them to the
supervisor alongside its built-in tools. Tool execution uses the owning runtime
and can access the same storage as the agent.

## Embedded behavior

Model selection, conversation memory and embeddings, statistics files and DuckDB
connections, HTTP routes, and scheduled jobs are built into Gordie. They are not
plugin extension points. Existing environment configuration still applies:
`LLM_PROVIDER`, `LLM_MODEL`, model API credentials, `GORDIE_DATA_DIR`, and
`ENABLED_SPORTS`.

Yahoo callbacks and health endpoints are always registered. Creem's webhook is
registered when `CREEM_API_KEY` is configured. Gordie registers its maintenance
and statistics jobs during application startup.

`gordie.integrations.defaults.default_plugins()` selects PostgreSQL storage and
optional Creem access/tools from environment configuration. The CLI uses this
assembly. Creem can also supply the two relevant extension points explicitly:

```python
from gordie.integrations.creem.plugin import with_creem

app = create_app(with_creem(plugins))
```

`with_creem(plugins)` returns a new configuration with a subscription access policy
and checkout, portal, and subscription-status tools. Existing environment
credentials configure Creem. Apply it only to a configuration without Creem.
The current implementation stays in this repository for later extraction.

## Runtime ownership

Application and agent construction do not open connections or start jobs. Each
owns its runtime and caches; Gordie owns models, memory, and statistics resources,
while the selected storage implementation owns database sessions and checkpoints.
Create fresh storage implementations for each app.

HTTP requests, agent invocations, and embedded scheduled jobs run within their
owner's runtime. Startup calls `storage.prepare()` before starting jobs; shutdown
waits for jobs before closing Gordie's resources and calling `storage.close()`.

A standalone agent assumes storage has already been prepared. Invoke it with
`agent.invoke(state, config)` or `await agent.ainvoke(state, config)`, then call
`agent.close()` after outstanding invocations finish. Async invocation runs the
existing synchronous agent pipeline in a worker thread.

Work launched using `asyncio.to_thread` inherits the runtime context. For other
threads, use `app.runtime.run(callable)` to run work within the owning context.
