import { fail, redirect, type Cookies } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';

const API_URL = import.meta.env.VITE_API_URL || 'https://gordie-api.lastingsoftware.ca';
const TRIAL_COOKIE = 'gordie_trial';
const TEAM_CONTEXT_COOKIE = 'gordie_trial_team_context';

type SessionStatus = {
	status: string;
	session_id: string | null;
	expires_at: string | null;
	question_count: number;
	question_limit: number;
	remaining_questions: number;
	provider_connected: boolean;
	provider_email: string | null;
};

type TrialTeam = {
	sport: string;
	season: string;
	game_key: string;
	league_id: string;
	team_id: string;
	team_name: string;
	is_active: boolean;
};

type ApiResult = {
	ok: boolean;
	status: number;
	body: Record<string, unknown>;
};

const defaultSession: SessionStatus = {
	status: 'missing',
	session_id: null,
	expires_at: null,
	question_count: 0,
	question_limit: 5,
	remaining_questions: 0,
	provider_connected: false,
	provider_email: null
};

export const load: PageServerLoad = async ({ cookies, fetch, url }) => {
	const saveToken = url.searchParams.get('save_token');
	if (saveToken) {
		const result = await apiRequest(fetch, undefined, '/api/trial/save/confirm', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ token: saveToken })
		});
		if (result.ok) {
			const sessionToken = extractString(result.body.session_token, '');
			if (sessionToken) {
				setCookie(cookies, TRIAL_COOKIE, sessionToken, url);
			}
			throw redirect(303, '/trial?saved=1');
		}
	}

	const session = await ensureSession(fetch, cookies, url);
	const teams = session.provider_connected ? await loadTeams(fetch, cookies) : [];
	return {
		session,
		teams,
		selectedTeamContext: cookies.get(TEAM_CONTEXT_COOKIE) ?? null,
		saved: url.searchParams.get('saved') === '1'
	};
};

export const actions: Actions = {
	connectYahoo: async ({ cookies, fetch, url }) => {
		await ensureSession(fetch, cookies, url);
		const result = await apiRequest(fetch, cookies.get(TRIAL_COOKIE), '/api/trial/yahoo/start', {
			method: 'POST'
		});
		if (!result.ok) {
			return fail(result.status, { error: extractString(result.body.error, 'Unable to start Yahoo OAuth.') });
		}

		const authUrl = extractString(result.body.auth_url, '');
		if (!authUrl) {
			return fail(500, { error: 'Yahoo OAuth did not return an authorization URL.' });
		}
		throw redirect(303, authUrl);
	},

	selectTeam: async ({ cookies, fetch, request, url }) => {
		await ensureSession(fetch, cookies, url);
		const data = await request.formData();
		const team = {
			sport: formValue(data, 'sport'),
			season: formValue(data, 'season'),
			game_key: formValue(data, 'game_key'),
			league_id: formValue(data, 'league_id'),
			team_id: formValue(data, 'team_id'),
			team_name: formValue(data, 'team_name'),
			is_active: formValue(data, 'is_active') === 'true'
		} satisfies TrialTeam;

		const result = await apiRequest(fetch, cookies.get(TRIAL_COOKIE), '/api/trial/team', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(team)
		});
		if (!result.ok) {
			return fail(result.status, { error: extractString(result.body.error, 'Unable to save that team.') });
		}

		const teamContext = `Yahoo:${team.game_key}:${team.league_id}:${team.team_id}`;
		setCookie(cookies, TEAM_CONTEXT_COOKIE, teamContext, url);
		return { selectedTeamContext: teamContext, selectedTeamName: team.team_name };
	},

	ask: async ({ cookies, fetch, request, url }) => {
		await ensureSession(fetch, cookies, url);
		const data = await request.formData();
		const question = formValue(data, 'question').trim();
		const teamContext = formValue(data, 'team_context') || cookies.get(TEAM_CONTEXT_COOKIE) || null;
		if (!question) {
			return fail(400, { error: 'Ask a fantasy question first.' });
		}

		const result = await apiRequest(fetch, cookies.get(TRIAL_COOKIE), '/api/trial/question', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ question, team_context: teamContext })
		});
		if (!result.ok) {
			return fail(result.status, { error: extractString(result.body.error, 'Gordie could not answer that.') });
		}

		return {
			answer: extractString(result.body.answer, ''),
			remainingQuestions: Number(result.body.remaining_questions ?? 0)
		};
	},

	save: async ({ cookies, fetch, request, url }) => {
		await ensureSession(fetch, cookies, url);
		const data = await request.formData();
		const email = formValue(data, 'email').trim().toLowerCase();
		if (!email.includes('@')) {
			return fail(400, { saveError: 'Enter a valid email address.' });
		}

		const result = await apiRequest(fetch, cookies.get(TRIAL_COOKIE), '/api/trial/save', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ email })
		});
		if (!result.ok) {
			return fail(result.status, { saveError: extractString(result.body.error, 'Unable to send save link.') });
		}

		return { saveSent: true };
	}
};

async function ensureSession(
	fetcher: typeof fetch,
	cookies: Cookies,
	url: URL
): Promise<SessionStatus> {
	const token = cookies.get(TRIAL_COOKIE);
	const method = token ? 'GET' : 'POST';
	const result = await apiRequest(fetcher, token, '/api/trial/session', { method });
	if (!result.ok) {
		return defaultSession;
	}

	const sessionToken = extractString(result.body.session_token, '');
	if (sessionToken) {
		setCookie(cookies, TRIAL_COOKIE, sessionToken, url);
	}
	return sessionFromBody(result.body);
}

async function loadTeams(fetcher: typeof fetch, cookies: Cookies): Promise<TrialTeam[]> {
	const result = await apiRequest(fetcher, cookies.get(TRIAL_COOKIE), '/api/trial/teams');
	if (!result.ok) {
		return [];
	}
	const teams = result.body.teams;
	if (!Array.isArray(teams)) {
		return [];
	}
	return teams.filter(isRecord).map(teamFromBody);
}

async function apiRequest(
	fetcher: typeof fetch,
	token: string | undefined,
	path: string,
	init: RequestInit = {}
): Promise<ApiResult> {
	const headers = new Headers(init.headers);
	if (token) {
		headers.set('X-Gordie-Trial-Token', token);
	}
	const response = await fetcher(`${API_URL}${path}`, { ...init, headers });
	const rawBody: unknown = await response.json().catch(() => null);
	return {
		ok: response.ok,
		status: response.status,
		body: isRecord(rawBody) ? rawBody : {}
	};
}

function sessionFromBody(body: Record<string, unknown>): SessionStatus {
	return {
		status: extractString(body.status, 'active'),
		session_id: nullableString(body.session_id),
		expires_at: nullableString(body.expires_at),
		question_count: Number(body.question_count ?? 0),
		question_limit: Number(body.question_limit ?? 5),
		remaining_questions: Number(body.remaining_questions ?? 0),
		provider_connected: Boolean(body.provider_connected),
		provider_email: nullableString(body.provider_email)
	};
}

function teamFromBody(body: Record<string, unknown>): TrialTeam {
	return {
		sport: extractString(body.sport, 'nhl'),
		season: extractString(body.season, 'Unknown'),
		game_key: extractString(body.game_key, ''),
		league_id: extractString(body.league_id, ''),
		team_id: extractString(body.team_id, ''),
		team_name: extractString(body.team_name, 'Yahoo Team'),
		is_active: Boolean(body.is_active)
	};
}

function formValue(data: FormData, key: string): string {
	return data.get(key)?.toString() ?? '';
}

function extractString(value: unknown, fallback: string): string {
	return typeof value === 'string' ? value : fallback;
}

function nullableString(value: unknown): string | null {
	return typeof value === 'string' ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function setCookie(cookies: Cookies, name: string, value: string, url: URL): void {
	cookies.set(name, value, {
		httpOnly: true,
		sameSite: 'lax',
		secure: url.protocol === 'https:',
		path: '/',
		maxAge: 7 * 24 * 60 * 60
	});
}
