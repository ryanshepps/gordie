import type { Actions } from './$types';
import { fail } from '@sveltejs/kit';

const API_URL = import.meta.env.VITE_API_URL || 'https://gordie.lastingsoftware.ca';

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_REGEX = /^\+[1-9]\d{9,14}$/;

export const actions: Actions = {
	default: async ({ request, fetch }) => {
		const data = await request.formData();
		const email = data.get('email')?.toString().trim().toLowerCase() || null;
		const phoneNumber = data.get('phone_number')?.toString().trim() || null;

		if (!email && !phoneNumber) {
			return fail(400, { error: 'Please provide an email address or phone number.' });
		}

		if (email && !EMAIL_REGEX.test(email)) {
			return fail(400, { error: 'Please enter a valid email address.' });
		}

		if (phoneNumber && !PHONE_REGEX.test(phoneNumber)) {
			return fail(400, { error: 'Please enter a valid phone number (e.g. +12025551234).' });
		}

		const body: Record<string, string> = {};
		if (email) body.email = email;
		if (phoneNumber) body.phone_number = phoneNumber;

		try {
			const response = await fetch(`${API_URL}/api/signup`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});

			if (!response.ok) {
				const responseBody = await response.json().catch(() => null);
				const message = responseBody?.error || 'Something went wrong. Please try again.';
				return fail(response.status, { error: message });
			}

			return { success: true, mode: phoneNumber ? 'phone' : 'email' };
		} catch {
			return fail(500, { error: 'Unable to reach our servers. Please try again later.' });
		}
	}
};
