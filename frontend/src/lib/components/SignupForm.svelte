<script lang="ts">
	import { enhance } from '$app/forms';
	import { fade } from 'svelte/transition';

	interface Props {
		id?: string;
	}

	const { id = 'signup' }: Props = $props();

	let mode = $state<'email' | 'phone'>('email');
	let email = $state('');
	let phoneNumber = $state('');
	let status = $state<'idle' | 'submitting' | 'success' | 'error'>('idle');
	let successMode = $state<'email' | 'phone'>('email');
	let errorMessage = $state('');

	function handleSubmit() {
		status = 'submitting';
		return async ({ result }: { result: { type: string; data?: { error?: string; mode?: string } } }) => {
			if (result.type === 'success') {
				successMode = (result.data?.mode as 'email' | 'phone') ?? mode;
				status = 'success';
				email = '';
				phoneNumber = '';
			} else if (result.type === 'failure') {
				status = 'error';
				errorMessage = result.data?.error ?? 'Something went wrong. Please try again.';
			} else {
				status = 'error';
				errorMessage = 'Something went wrong. Please try again.';
			}
		};
	}

	function switchMode(newMode: 'email' | 'phone') {
		mode = newMode;
		status = 'idle';
		errorMessage = '';
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
	{:else}
		<div out:fade={{ duration: 250 }}>
			<div class="mode-toggle">
				<button
					type="button"
					class="toggle-btn"
					class:active={mode === 'email'}
					onclick={() => switchMode('email')}
				>Email</button>
				<button
					type="button"
					class="toggle-btn"
					class:active={mode === 'phone'}
					onclick={() => switchMode('phone')}
				>Phone Number</button>
			</div>
			<form method="POST" action="/signup" use:enhance={handleSubmit} class="signup-form">
				<div class="input-group">
					{#if mode === 'email'}
						<label for="signup-email" class="sr-only">Email address</label>
						<input
							id="signup-email"
							type="email"
							name="email"
							bind:value={email}
							placeholder="Enter your email"
							required
							disabled={status === 'submitting'}
						/>
					{:else}
						<label for="signup-phone" class="sr-only">Phone number</label>
						<input
							id="signup-phone"
							type="tel"
							name="phone_number"
							bind:value={phoneNumber}
							placeholder="+1 (555) 123-4567"
							required
							disabled={status === 'submitting'}
						/>
					{/if}
					<button type="submit" class="btn btn-primary" disabled={status === 'submitting'}>
						{status === 'submitting' ? 'Signing up...' : 'Get Started Free'}
					</button>
				</div>
				{#if status === 'error'}
					<p class="error-message">{errorMessage}</p>
				{/if}
				<p class="signup-note">Free during beta. No credit card required.</p>
			</form>
		</div>
	{/if}
</div>

<style>
	.signup-form-wrapper {
		max-width: 480px;
	}

	.mode-toggle {
		display: flex;
		gap: 0.25rem;
		margin-bottom: 0.75rem;
		background: var(--color-bg-secondary);
		border: 1px solid var(--color-border);
		border-radius: 0.375rem;
		padding: 0.2rem;
	}

	.toggle-btn {
		flex: 1;
		padding: 0.45rem 0.75rem;
		border: none;
		border-radius: 0.25rem;
		background: transparent;
		color: var(--color-text-muted);
		font-size: 0.85rem;
		font-weight: 600;
		letter-spacing: 0.02em;
		cursor: pointer;
		transition: background 0.15s ease-out, color 0.15s ease-out;
	}

	.toggle-btn:hover {
		color: var(--color-text);
	}

	.toggle-btn.active {
		background: var(--color-border);
		color: var(--color-text);
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

	input[type='email'],
	input[type='tel'] {
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

	input[type='email']:focus,
	input[type='tel']:focus {
		border-color: var(--color-primary);
		box-shadow: 0 0 0 3px rgba(255, 184, 0, 0.15);
	}

	input[type='email']::placeholder,
	input[type='tel']::placeholder {
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
		background: linear-gradient(135deg, rgba(255, 184, 0, 0.12) 0%, rgba(255, 184, 0, 0.04) 50%, rgba(255, 184, 0, 0.08) 100%);
		border: 1px solid rgba(255, 184, 0, 0.4);
		border-radius: 0.5rem;
		text-align: center;
		position: relative;
		overflow: hidden;
	}

	.success-message::before {
		content: '';
		position: absolute;
		inset: 0;
		background: radial-gradient(ellipse at 50% 0%, rgba(255, 184, 0, 0.1) 0%, transparent 60%);
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
		background: linear-gradient(135deg, #FFB800 0%, #FFD866 100%);
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

	@media (max-width: 480px) {
		.input-group {
			flex-direction: column;
		}
	}
</style>
