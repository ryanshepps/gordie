"""Temporary hosted-trial API routes."""

import asyncio
import os
import re
from collections.abc import Mapping
from html import escape
from typing import cast
from urllib.parse import urlencode

from quart import Quart, Response, jsonify, make_response, request

from agent.context_resolvers import auto_onboard_team, fetch_supported_teams
from data.models import Medium
from data.temporary_session_repository import (
    TemporarySessionRecord,
    TemporarySessionRepository,
    TrialLimitExceededError,
    TrialProviderRequiredError,
    TrialSessionError,
    TrialSessionExpiredError,
)
from data.thread_repository import ThreadRepository
from module.logger import get_logger
from server.oauth_link_service import generate_cold_start_oauth_link

logger = get_logger(__name__)

TRIAL_COOKIE_NAME = "gordie_trial"
DEFAULT_TRIAL_TTL_DAYS = 7
DEFAULT_TRIAL_QUESTION_LIMIT = 5
EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
JsonMapping = Mapping[str, object]


def register_trial_routes(app: Quart) -> None:
    """Register temporary trial routes on the Quart app."""

    @app.route("/api/trial/session", methods=["GET", "POST"])
    async def trial_session():  # pyright: ignore[reportUnusedFunction]
        token = _read_session_token()
        repo = TemporarySessionRepository()
        try:
            session: TemporarySessionRecord | None = repo.get_by_token(token) if token else None
            created_token: str | None = None
            if session is None and request.method == "POST":
                created = repo.create_session(
                    ttl_days=_trial_ttl_days(),
                    question_limit=_trial_question_limit(),
                )
                session = created.session
                created_token = created.token

            if session is None:
                return jsonify({"status": "missing"}), 404

            connection = repo.get_provider_connection(session.id)
            body = {
                "status": "active",
                "session_id": str(session.id),
                "expires_at": session.expires_at.isoformat(),
                "question_count": session.question_count,
                "question_limit": session.question_limit,
                "remaining_questions": session.remaining_questions,
                "provider_connected": connection is not None,
                "provider_email": connection.provider_email if connection else None,
            }
            if created_token:
                body["session_token"] = created_token

            response = cast(Response, await make_response(jsonify(body)))
            if created_token:
                _set_trial_cookie(response, created_token)
            return response
        finally:
            repo.close()

    @app.route("/api/trial/yahoo/start", methods=["POST"])
    async def start_trial_yahoo_oauth():  # pyright: ignore[reportUnusedFunction]
        try:
            session, token = _load_active_session()
        except TrialSessionExpiredError as exc:
            return jsonify({"error": str(exc)}), 401
        thread_id = _resolve_web_thread_id(session)
        try:
            oauth_url = await asyncio.to_thread(
                generate_cold_start_oauth_link,
                Medium.WEB,
                str(session.id),
                thread_id,
            )
        except ValueError:
            return jsonify({"error": "Yahoo OAuth is not configured."}), 500
        if not oauth_url.startswith("https://"):
            logger.error("Failed to build trial OAuth URL: %s", oauth_url)
            return jsonify({"error": "Yahoo OAuth is not configured."}), 500

        response = cast(Response, await make_response(jsonify({"auth_url": oauth_url})))
        _set_trial_cookie(response, token)
        return response

    @app.route("/api/trial/teams", methods=["GET"])
    async def list_trial_teams():  # pyright: ignore[reportUnusedFunction]
        try:
            session, token = _load_active_session()
        except TrialSessionExpiredError as exc:
            return jsonify({"error": str(exc)}), 401
        repo = TemporarySessionRepository()
        try:
            connection = repo.get_provider_connection(session.id)
            if connection is None:
                return jsonify({"error": "Connect Yahoo Fantasy first."}), 409
            teams = await asyncio.to_thread(fetch_supported_teams, str(session.user_id))
        finally:
            repo.close()

        response = cast(Response, await make_response(jsonify({"teams": teams})))
        _set_trial_cookie(response, token)
        return response

    @app.route("/api/trial/team", methods=["POST"])
    async def select_trial_team():  # pyright: ignore[reportUnusedFunction]
        try:
            session, token = _load_active_session()
        except TrialSessionExpiredError as exc:
            return jsonify({"error": str(exc)}), 401
        payload = await _request_json()
        if payload is None:
            return jsonify({"error": "Expected JSON body."}), 400

        team = _team_from_payload(payload)
        if team is None:
            return jsonify({"error": "Select a valid Yahoo team."}), 400

        try:
            onboarded = await asyncio.to_thread(auto_onboard_team, str(session.user_id), team)
        except RuntimeError as exc:
            logger.error("Failed to onboard trial team: %s", exc)
            return jsonify({"error": "Unable to save that Yahoo team."}), 502

        response = cast(Response, await make_response(jsonify({"team": onboarded})))
        _set_trial_cookie(response, token)
        return response

    @app.route("/api/trial/question", methods=["POST"])
    async def ask_trial_question():  # pyright: ignore[reportUnusedFunction]
        try:
            session, token = _load_active_session()
        except TrialSessionExpiredError as exc:
            return jsonify({"error": str(exc)}), 401
        payload = await _request_json()
        if payload is None:
            return jsonify({"error": "Expected JSON body."}), 400

        question = _payload_str(payload, "question").strip()
        if not question:
            return jsonify({"error": "Question is required."}), 400
        team_context = payload.get("team_context")
        team_context_value = str(team_context) if team_context else None

        repo = TemporarySessionRepository()
        try:
            try:
                reservation = repo.reserve_question(session.id)
            except TrialProviderRequiredError as exc:
                return jsonify({"error": str(exc)}), 409
            except TrialLimitExceededError as exc:
                return jsonify({"error": str(exc)}), 429
            except TrialSessionExpiredError as exc:
                return jsonify({"error": str(exc)}), 401

            repo.add_chat_message(session.id, "human", question)
        finally:
            repo.close()

        from scripts.message_agent import message_agent

        answer = await asyncio.to_thread(
            message_agent,
            message=question,
            thread_id=_resolve_web_thread_id(session),
            channel=Medium.WEB,
            user_id=str(session.user_id),
            external_id=str(session.id),
            team_context=team_context_value,
        )
        if not answer:
            return jsonify({"error": "Gordie could not answer that question."}), 502

        repo = TemporarySessionRepository()
        try:
            repo.add_chat_message(session.id, "ai", answer)
        finally:
            repo.close()

        response = cast(
            Response,
            await make_response(
                jsonify(
                    {
                        "answer": answer,
                        "remaining_questions": reservation.remaining_questions,
                    }
                )
            ),
        )
        _set_trial_cookie(response, token)
        return response

    @app.route("/api/trial/save", methods=["POST"])
    async def save_trial_session():  # pyright: ignore[reportUnusedFunction]
        try:
            session, token = _load_active_session()
        except TrialSessionExpiredError as exc:
            return jsonify({"error": str(exc)}), 401

        payload = await _request_json()
        if payload is None:
            return jsonify({"error": "Expected JSON body."}), 400

        email = _payload_str(payload, "email").strip().lower()
        if not EMAIL_REGEX.match(email):
            return jsonify({"error": "Enter a valid email address."}), 400

        repo = TemporarySessionRepository()
        try:
            save_link = repo.create_save_link(session.id, email)
        finally:
            repo.close()

        link = _trial_save_url(save_link.token)
        from server.email_service import EmailService

        email_result = await asyncio.to_thread(
            EmailService().send_email,
            to_email=email,
            subject="Continue your Gordie trial",
            text_body=(
                "Open this link to save and continue your temporary Gordie session:\n\n"
                f"{link}\n\nThis link expires in 30 minutes."
            ),
            html_body=(
                "<p>Open this link to save and continue your temporary Gordie session:</p>"
                f'<p><a href="{escape(link)}">Continue your Gordie trial</a></p>'
                "<p>This link expires in 30 minutes.</p>"
            ),
            track_opens=False,
            track_clicks=False,
        )
        if not email_result.success:
            logger.error("Failed to send trial save link to %s: %s", email, email_result.error)
            return jsonify({"error": "Unable to send the save link right now."}), 503

        response = cast(Response, await make_response(jsonify({"status": "sent"})))
        _set_trial_cookie(response, token)
        return response

    @app.route("/api/trial/save/confirm", methods=["POST"])
    async def confirm_trial_save():  # pyright: ignore[reportUnusedFunction]
        payload = await _request_json()
        if payload is None:
            return jsonify({"error": "Expected JSON body."}), 400

        save_token = _payload_str(payload, "token").strip()
        if not save_token:
            return jsonify({"error": "Save token is required."}), 400

        repo = TemporarySessionRepository()
        try:
            try:
                confirmed = repo.confirm_save_link(save_token)
            except TrialSessionError as exc:
                return jsonify({"error": str(exc)}), 400
        finally:
            repo.close()

        response = cast(
            Response,
            await make_response(
                jsonify(
                    {
                        "status": "saved",
                        "session_id": str(confirmed.session.id),
                        "session_token": confirmed.token,
                    }
                )
            ),
        )
        _set_trial_cookie(response, confirmed.token)
        return response


def _load_active_session() -> tuple[TemporarySessionRecord, str]:
    token = _read_session_token()
    if not token:
        raise TrialSessionExpiredError("Start a temporary session first.")

    repo = TemporarySessionRepository()
    try:
        session = repo.get_by_token(token)
        if session is None:
            raise TrialSessionExpiredError("Temporary session is expired or missing.")
        return session, token
    finally:
        repo.close()


def _read_session_token() -> str | None:
    header_token = request.headers.get("X-Gordie-Trial-Token")
    if header_token:
        return header_token
    return request.cookies.get(TRIAL_COOKIE_NAME)


async def _request_json() -> JsonMapping | None:
    payload = cast(object, await request.get_json(silent=True))
    if isinstance(payload, Mapping):
        return cast(JsonMapping, payload)
    return None


def _payload_str(payload: JsonMapping, key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _resolve_web_thread_id(session: TemporarySessionRecord) -> str:
    repo = ThreadRepository()
    try:
        return repo.resolve(session.user_id, Medium.WEB).thread_id
    finally:
        repo.close()


def _set_trial_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        TRIAL_COOKIE_NAME,
        token,
        max_age=_trial_ttl_days() * 24 * 60 * 60,
        httponly=True,
        secure=_secure_trial_cookie(),
        samesite="Lax",
        path="/",
    )


def _secure_trial_cookie() -> bool:
    configured = os.getenv("TRIAL_COOKIE_SECURE")
    if configured is not None:
        return configured.lower() not in {"0", "false", "no"}
    oauth_base_url = os.getenv("OAUTH_BASE_URL", "")
    return oauth_base_url.startswith("https://")


def _trial_ttl_days() -> int:
    raw_value = os.getenv("TRIAL_TTL_DAYS")
    if not raw_value:
        return DEFAULT_TRIAL_TTL_DAYS
    return max(int(raw_value), 1)


def _trial_question_limit() -> int:
    raw_value = os.getenv("TRIAL_QUESTION_LIMIT")
    if not raw_value:
        return DEFAULT_TRIAL_QUESTION_LIMIT
    return max(int(raw_value), 1)


def _team_from_payload(payload: JsonMapping) -> dict[str, str] | None:
    required = ("game_key", "league_id", "team_id", "team_name")
    values: dict[str, str] = {}
    for key in required:
        value = payload.get(key)
        if value is None or str(value).strip() == "":
            return None
        values[key] = str(value)
    values["sport"] = str(payload.get("sport", payload.get("game_code", "nhl")))
    values["season"] = str(payload.get("season", "Unknown"))
    values["is_active"] = str(payload.get("is_active", "true"))
    return values


def build_trial_return_html() -> str:
    """HTML returned after a hosted trial Yahoo OAuth callback."""
    return_url = os.getenv("TRIAL_RETURN_URL", os.getenv("VITE_SITE_URL", "http://localhost:5173"))
    safe_url = return_url.rstrip("/") + "/trial"
    return f"""
    <html>
        <body>
            <h1>Yahoo Fantasy Connected</h1>
            <p>Return to Gordie to pick your league and ask a trial question.</p>
            <p><a href="{safe_url}">Return to Gordie</a></p>
        </body>
    </html>
    """


def _trial_save_url(token: str) -> str:
    return_url = os.getenv("TRIAL_RETURN_URL", os.getenv("VITE_SITE_URL", "http://localhost:5173"))
    query = urlencode({"save_token": token})
    return f"{return_url.rstrip('/')}/trial?{query}"
