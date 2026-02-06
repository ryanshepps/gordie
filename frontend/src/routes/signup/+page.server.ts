import type { Actions } from './$types';
import { fail } from '@sveltejs/kit';

const API_URL = import.meta.env.VITE_API_URL || 'https://gordie.lastingsoftware.ca';

export const actions: Actions = {
	default: async ({ request, fetch }) => {
		const data = await request.formData();
		const email = data.get('email')?.toString().trim().toLowerCase();

		if (!email) {
			return fail(400, { error: 'Email is required.' });
		}

		const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
		if (!emailRegex.test(email)) {
			return fail(400, { error: 'Please enter a valid email address.' });
		}

		try {
			const response = await fetch(`${API_URL}/api/signup`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email })
			});

			if (!response.ok) {
				const body = await response.json().catch(() => null);
				const message = body?.error || 'Something went wrong. Please try again.';
				return fail(response.status, { error: message });
			}

			return { success: true };
		} catch {
			return fail(500, { error: 'Unable to reach our servers. Please try again later.' });
		}
	}
};
