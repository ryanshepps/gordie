"""Pydantic schemas for LLM-based agent routing."""

from enum import Enum

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Available agent types for routing."""

    ONBOARDING = "onboarding"
    PLAYER_COMPARISON = "player_comparison"
    GENERAL = "general"


class RoutingDecision(BaseModel):
    """LLM classification result for agent routing."""

    agent: AgentType = Field(
        description="The agent that should handle this user request"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for this classification (0.0 to 1.0)",
    )
    reasoning: str = Field(
        description="Brief explanation of why this agent was selected"
    )
