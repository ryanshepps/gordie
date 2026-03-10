"""Prometheus metrics for the fantasy-agent application."""

import os
import sys

import psutil
from prometheus_client import Counter, Gauge, Histogram, Info

# Tool Execution Metrics (PRIMARY REQUIREMENT)
tool_calls_total = Counter(
    "fantasy_agent_tool_calls_total",
    "Total number of tool calls",
    ["tool_name", "status"],
)

tool_errors_total = Counter(
    "fantasy_agent_tool_errors_total",
    "Total number of failed tool executions",
    ["tool_name", "error_type"],
)

tool_execution_duration_seconds = Histogram(
    "fantasy_agent_tool_execution_duration_seconds",
    "Tool execution duration in seconds",
    ["tool_name"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

# HTTP Request Metrics
http_requests_total = Counter(
    "fantasy_agent_http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)

http_request_duration_seconds = Histogram(
    "fantasy_agent_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
)

webhook_requests_total = Counter(
    "fantasy_agent_webhook_requests_total",
    "Total webhook requests received",
    ["webhook_type", "status"],
)

# Agent Execution Metrics
agent_invocations_total = Counter(
    "fantasy_agent_invocations_total", "Total agent invocations", ["agent_name", "status"]
)

agent_execution_duration_seconds = Histogram(
    "fantasy_agent_execution_duration_seconds",
    "Agent execution duration in seconds",
    ["agent_name"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

agent_state_transitions_total = Counter(
    "fantasy_agent_state_transitions_total",
    "Total state transitions in agent graph",
    ["from_node", "to_node"],
)

llm_api_calls_total = Counter(
    "fantasy_agent_llm_api_calls_total", "Total LLM API calls", ["model", "status"]
)

llm_tokens_used_total = Counter(
    "fantasy_agent_llm_tokens_total", "Total tokens used in LLM calls", ["model", "token_type"]
)

# System Resource Metrics
system_cpu_usage_percent = Gauge("fantasy_agent_cpu_usage_percent", "Current CPU usage percentage")

system_memory_usage_bytes = Gauge(
    "fantasy_agent_memory_usage_bytes", "Current memory usage in bytes"
)

system_disk_usage_bytes = Gauge(
    "fantasy_agent_disk_usage_bytes", "Current disk usage in bytes", ["path"]
)

# Business Metrics
active_users_total = Gauge("fantasy_agent_active_users_total", "Total number of active users")

active_leagues_total = Gauge("fantasy_agent_active_leagues_total", "Total number of active leagues")

emails_sent_total = Counter(
    "fantasy_agent_emails_sent_total", "Total emails sent to users", ["status"]
)

sms_sent_total = Counter(
    "fantasy_agent_sms_sent_total", "Total SMS messages sent to users", ["status"]
)

sms_webhook_requests_total = Counter(
    "fantasy_agent_sms_webhook_requests_total", "Total SMS webhook requests received", ["status"]
)

sms_rate_limited_total = Counter(
    "fantasy_agent_sms_rate_limited_total",
    "Total SMS messages dropped due to rate limiting",
    ["phone_number"],
)

trades_analyzed_total = Counter(
    "fantasy_agent_trades_analyzed_total", "Total trades analyzed", ["user_email"]
)

player_comparisons_total = Counter(
    "fantasy_agent_player_comparisons_total", "Total player comparisons performed"
)

# Stats DB Refresh Metrics
stats_db_refresh_total = Counter(
    "fantasy_agent_stats_db_refresh_total",
    "Total stats DB refresh attempts",
    ["status"],
)

stats_db_last_refresh_timestamp = Gauge(
    "fantasy_agent_stats_db_last_refresh_timestamp",
    "Unix timestamp of last successful stats DB refresh",
)

# Database Metrics
database_queries_total = Counter(
    "fantasy_agent_database_queries_total",
    "Total database queries",
    ["database", "operation"],
)

database_query_duration_seconds = Histogram(
    "fantasy_agent_database_query_duration_seconds",
    "Database query duration in seconds",
    ["database", "operation"],
    buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0),
)

# Application Info
app_info = Info("fantasy_agent_app", "Fantasy agent application information")

app_info.info(
    {
        "version": "0.1.0",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }
)


def update_system_metrics():
    """Update system resource metrics. Call this periodically."""
    try:
        system_cpu_usage_percent.set(psutil.cpu_percent(interval=0.1))

        memory = psutil.virtual_memory()
        system_memory_usage_bytes.set(memory.used)

        project_root = os.path.dirname(os.path.dirname(__file__))
        disk = psutil.disk_usage(project_root)
        system_disk_usage_bytes.labels(path=project_root).set(disk.used)

    except Exception as e:
        print(f"Error updating system metrics: {e}")


def update_business_metrics():
    """Update business metrics from database. Call this periodically."""
    try:
        from data.user_repository import UserRepository

        user_repo = UserRepository()
        user_repo.close()

    except Exception as e:
        print(f"Error updating business metrics: {e}")
