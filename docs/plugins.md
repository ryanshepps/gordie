# Configuring Gordie integrations

`create_app(plugins)` builds a Quart application. `create_agent(plugins)` builds
an agent for callers that manage their own messaging service. Both accept the
same immutable configuration with four extension points.

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
| `communication` | `Communication`: inbound registration, startup, reply delivery, shutdown | Caller owns delivery |

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

### Communication

`Communication` owns inbound transport handling and outgoing delivery:

| Method | Responsibility |
| --- | --- |
| `register(app, handle_message)` | Register communication endpoints or retain the callback for a listener |
| `start()` | Start provider clients or listeners after storage is prepared |
| `send(OutgoingMessage)` | Deliver a final reply to its transport recipient |
| `close()` | Stop listeners and finish outstanding delivery before storage closes |

Pass an implementation as `Plugins(storage=storage, communication=communication)`.
Provider SDKs, webhook authentication, and transport configuration belong in that
implementation. The callback accepts `IncomingMessage(context, text)`, runs Gordie
in its owning runtime, sends the final reply once, and returns an `OutgoingMessage`
or `None` when there is no response. A returned message is the delivery result.
Delivery errors propagate to the caller so the adapter controls acknowledgements
and retries.

`MessageContext` carries the routing and identity information:

| Attribute | Meaning |
| --- | --- |
| `user_id` | Canonical Gordie user identifier resolved by the adapter |
| `thread_id` | Stable conversation/checkpoint identifier |
| `external_id` | Account identity used by Gordie's OAuth flow |
| `recipient` | Transport-native reply address, such as a phone number or chat ID |
| `channel` | Core identity medium; currently `Medium.EMAIL` |

Adapters authenticate inbound events and resolve their canonical account and
conversation before invoking the callback. A transport's reply address is separate
from the account identity; adding communication does not expand the existing
email-based identity/OAuth model. Both message types expose their content as `text`.

Registration happens during application construction. The synchronous `start`,
`send`, and `close` methods run in worker threads, so adapters can use synchronous
provider clients. Callbacks also work outside HTTP requests, for polling listeners.
Create a fresh communication implementation for each application.

For a standalone agent, use `agent.receive(message)` or
`await agent.areceive(message)` to generate and deliver a reply. The caller prepares
storage and starts the communication implementation before receiving messages;
`agent.close()` closes communication and storage. `agent.invoke` and `agent.ainvoke`
remain the lower-level graph API that returns state for caller-owned delivery.
With `communication=None`, receive methods return a reply for the caller to deliver;
the existing CLI continues printing its response.

## Embedded behavior

Model selection, conversation memory and embeddings, statistics files and DuckDB
connections, application HTTP routes, and scheduled jobs are built into Gordie.
Communication adapters can register their own transport endpoints through the
communication contract. There is no general route or job plugin interface.
Existing environment configuration still applies:
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
while storage owns database sessions and checkpoints and communication owns its
transport clients/listeners. Create fresh implementations for each app.

HTTP requests, agent invocations, and embedded scheduled jobs run within their
owner's runtime. Startup prepares storage, starts communication, then starts jobs.
Shutdown waits for jobs, closes communication, then closes Gordie's resources and
storage. Communication shutdown must finish outstanding callbacks before returning.

A standalone agent assumes storage has already been prepared. Invoke it with
`agent.invoke(state, config)` or `await agent.ainvoke(state, config)`, then call
`agent.close()` after outstanding invocations finish. Async invocation runs the
existing synchronous agent pipeline in a worker thread.

Work launched using `asyncio.to_thread` inherits the runtime context. For other
threads, use `app.runtime.run(callable)` to run work within the owning context.
