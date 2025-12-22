"""Pydantic schemas for LLM-based agent routing."""

from enum import Enum

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Available agent types for routing."""

    ONBOARDING = "onboarding"
    PLAYER_COMPARISON = "player_comparison"


class RoutingDecision(BaseModel):
    """LLM classification result for agent routing."""

    agent: AgentType = Field(description="The agent that should handle this user request")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for this classification (0.0 to 1.0)",
    )
    reasoning: str = Field(description="Brief explanation of why this agent was selected")


class AgentFlowDecision(BaseModel):
    """LLM flow determination result."""

    agent_flow: list[AgentType] = Field(description="Ordered sequence of agents to execute")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for this flow decision (0.0 to 1.0)",
    )
    reasoning: str = Field(description="Brief explanation of why this flow was selected")


# Maximum flow length to prevent infinite loops
MAX_FLOW_LENGTH = 10
