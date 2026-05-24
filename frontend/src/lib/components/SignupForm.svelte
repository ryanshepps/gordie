<script lang="ts">
	import { enhance } from '$app/forms';
	import { fade } from 'svelte/transition';

	interface Props {
		id?: string;
	}

	const { id = 'signup' }: Props = $props();

	let contactInfo = $state('');
	let status = $state<'idle' | 'submitting' | 'success' | 'error' | 'oss'>('idle');
	let successMode = $state<'email' | 'phone'>('email');
	let errorMessage = $state('');
	let ossMessage = $state('');
	let ossGithubUrl = $state('');

	function isPhone(value: string): boolean {
		const trimmed = value.trim();
		if (trimmed.startsWith('+')) return true;
		const digitsOnly = trimmed.replace(/\D/g, '');
		return digitsOnly.length >= 7;
	}

	function normalizePhone(value: string): string {
		const trimmed = value.trim();
		if (trimmed.startsWith('+')) {
			return '+' + trimmed.slice(1).replace(/\D/g, '');
		}
		return '+1' + trimmed.replace(/\D/g, '');
	}

	let detectedMode = $derived<'email' | 'phone'>(isPhone(contactInfo) ? 'phone' : 'email');

	type FormResult = {
		type: string;
		data?: {
			error?: string;
			mode?: string;
			oss?: boolean;
			message?: string;
			github_url?: string | null;
		};
	};

	function handleSubmit() {
		status = 'submitting';
		return async ({ result }: { result: FormResult }) => {
			if (result.type === 'success') {
				successMode = (result.data?.mode as 'email' | 'phone') ?? detectedMode;
				status = 'success';
				contactInfo = '';
			} else if (result.type === 'failure' && result.data?.oss) {
				ossMessage = result.data.message ?? '';
				ossGithubUrl = result.data.github_url ?? '';
				status = 'oss';
				contactInfo = '';
			} else if (result.type === 'failure') {
				status = 'error';
				errorMessage = result.data?.error ?? 'Something went wrong. Please try again.';
			} else {
				status = 'error';
				errorMessage = 'Something went wrong. Please try again.';
			}
		};
	}
</script>

<div {id} class="signup-form-wrapper">
	{#if status === 'success'}
		<div class="success-message" in:fade={{ duration: 400, delay: 250 }}>
			<div class="trophy">🏆</div>
			<h3>YOU'RE IN!</h3>
			{#if successMode === 'phone'}
				<p>Check your texts — Gordie's sending you a link to connect your Yahoo league.</p>
			{:else}
				<p>Check your inbox — Gordie's sending you a message. Look for <strong>gordie@gordie.lastingsoftware.ca</strong>.</p>
			{/if}
		</div>
	{:else if status === 'oss'}
		<div class="oss-message" in:fade={{ duration: 400, delay: 100 }}>
			<div class="oss-tag">OPEN SOURCE</div>
			<h3>GORDIE IS NOW OPEN SOURCE</h3>
			<p>{ossMessage}</p>
			{#if ossGithubUrl}
				<a class="btn btn-primary oss-cta" href={ossGithubUrl} target="_blank" rel="noopener noreferrer">
					View on GitHub
				</a>
			{/if}
		</div>
	{:else}
		<div out:fade={{ duration: 250 }}>
			<form method="POST" action="/signup" use:enhance={handleSubmit} class="signup-form">
				{#if detectedMode === 'phone'}
					<input type="hidden" name="phone_number" value={normalizePhone(contactInfo)} />
				{:else}
					<input type="hidden" name="email" value={contactInfo.trim().toLowerCase()} />
				{/if}
				<div class="input-group">
					<label for="signup-contact" class="sr-only">Email or phone number</label>
					<input
						id="signup-contact"
						type="text"
						bind:value={contactInfo}
						placeholder="Email or phone number"
						required
						disabled={status === 'submitting'}
					/>
					<button type="submit" class="btn btn-primary" disabled={status === 'submitting'}>
						{status === 'submitting' ? 'Signing up...' : 'Get Started Free'}
					</button>
				</div>
				{#if status === 'error'}
					<p class="error-message">{errorMessage}</p>
				{/if}
				<p class="signup-note">Free digest updates for one team. No credit card required.</p>
			</form>
		</div>
	{/if}
</div>

<style>
	.signup-form-wrapper {
		max-width: 480px;
	}

	.signup-form {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.input-group {
		display: flex;
		gap: 0.5rem;
	}

	input[type='text'] {
		flex: 1;
		padding: 0.75rem 1rem;
		border-radius: 0.375rem;
		border: 1px solid var(--color-border);
		background: var(--color-bg-secondary);
		color: var(--color-text);
		font-size: 1rem;
		outline: none;
		transition: border-color 0.2s, box-shadow 0.2s;
	}

	input[type='text']:focus {
		border-color: var(--color-primary);
		box-shadow: 0 0 0 3px rgba(0, 229, 255, 0.15);
	}

	input[type='text']::placeholder {
		color: var(--color-text-muted);
	}

	.signup-note {
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.error-message {
		color: var(--color-error);
		font-size: 0.9rem;
	}

	.success-message {
		padding: 2rem 1.5rem;
		background: linear-gradient(135deg, rgba(0, 229, 255, 0.12) 0%, rgba(0, 229, 255, 0.04) 50%, rgba(0, 229, 255, 0.08) 100%);
		border: 1px solid rgba(0, 229, 255, 0.4);
		border-radius: 0.5rem;
		text-align: center;
		position: relative;
		overflow: hidden;
	}

	.success-message::before {
		content: '';
		position: absolute;
		inset: 0;
		background: radial-gradient(ellipse at 50% 0%, rgba(0, 229, 255, 0.1) 0%, transparent 60%);
		pointer-events: none;
	}

	.trophy {
		font-size: 2.5rem;
		margin-bottom: 0.5rem;
		animation: trophy-enter 0.5s ease-out 0.4s both;
	}

	@keyframes trophy-enter {
		0% {
			opacity: 0;
			transform: scale(0.5) translateY(10px);
		}
		60% {
			transform: scale(1.15) translateY(0);
		}
		100% {
			opacity: 1;
			transform: scale(1) translateY(0);
		}
	}

	.success-message h3 {
		font-family: 'Barlow Condensed', 'Inter Tight', sans-serif;
		font-weight: 700;
		letter-spacing: 0.06em;
		background: linear-gradient(135deg, #00E5FF 0%, #E8EDF5 100%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
		font-size: 1.35rem;
		margin-bottom: 0.5rem;
	}

	.success-message p {
		color: var(--color-text-muted);
		font-size: 0.95rem;
		position: relative;
	}

	.oss-message {
		padding: 2rem 1.5rem;
		background: linear-gradient(135deg, rgba(0, 229, 255, 0.10) 0%, rgba(0, 229, 255, 0.03) 100%);
		border: 1px solid rgba(0, 229, 255, 0.4);
		border-radius: 0.5rem;
		text-align: center;
		position: relative;
		overflow: hidden;
	}

	.oss-message::before {
		content: '';
		position: absolute;
		inset: 0;
		background: radial-gradient(ellipse at 50% 0%, rgba(0, 229, 255, 0.12) 0%, transparent 60%);
		pointer-events: none;
	}

	.oss-tag {
		display: inline-block;
		padding: 0.25rem 0.625rem;
		margin-bottom: 0.875rem;
		font-size: 0.7rem;
		font-weight: 600;
		letter-spacing: 0.08em;
		color: #00E5FF;
		background: rgba(0, 229, 255, 0.15);
		border: 1px solid rgba(0, 229, 255, 0.4);
		border-radius: 0.25rem;
	}

	.oss-message h3 {
		font-family: 'Barlow Condensed', 'Inter Tight', sans-serif;
		font-weight: 700;
		letter-spacing: 0.04em;
		background: linear-gradient(135deg, #00E5FF 0%, #E8EDF5 60%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
		font-size: 1.5rem;
		margin: 0 0 0.75rem;
	}

	.oss-message p {
		color: var(--color-text-muted);
		font-size: 0.95rem;
		margin: 0 0 1.25rem;
		position: relative;
		line-height: 1.6;
	}

	.oss-cta {
		display: inline-block;
		position: relative;
	}

	@media (max-width: 480px) {
		.input-group {
			flex-direction: column;
		}
	}
</style>
