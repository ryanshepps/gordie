from gordie.agent.agent_state import AgentState
from gordie.plugins import IncomingMessage, OutgoingMessage
from gordie.runtime import current_runtime


def receive_message(message: IncomingMessage) -> OutgoingMessage | None:
    from gordie.agent.graph_builder import get_agent

    context = message.context
    state: AgentState = {
        "user_id": context.user_id,
        "thread_id": context.thread_id,
        "external_id": context.external_id,
        "channel": context.channel,
        "messages": [{"role": "user", "content": message.text}],
        "response": None,
        "access_context": None,
    }
    result = get_agent().invoke(state, {"configurable": {"thread_id": context.thread_id}})
    response = result.get("response")
    if not response:
        return None
    reply = OutgoingMessage(context=context, text=str(response))
    communication = current_runtime().plugins.communication
    if communication is not None:
        communication.send(reply)
    return reply
