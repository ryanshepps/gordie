<script lang="ts">
	import { enhance } from '$app/forms';
	import { fade } from 'svelte/transition';

	interface Props {
		id?: string;
	}

	const { id = 'signup' }: Props = $props();

	let email = $state('');
	let status = $state<'idle' | 'submitting' | 'success' | 'error'>('idle');
	let errorMessage = $state('');

	function handleSubmit() {
		status = 'submitting';
		return async ({ result }: { result: { type: string; data?: { error?: string } } }) => {
			if (result.type === 'success') {
				status = 'success';
				email = '';
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
			<p>Check your inbox — Gordie's sending you a message. Look for <strong>gordie@gordie.lastingsoftware.ca</strong>.</p>
		</div>
	{:else}
		<div out:fade={{ duration: 250 }}>
			<form method="POST" action="/signup" use:enhance={handleSubmit} class="signup-form">
				<div class="input-group">
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

	.signup-form {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.input-group {
		display: flex;
		gap: 0.5rem;
	}

	input[type='email'] {
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

	input[type='email']:focus {
		border-color: var(--color-primary);
		box-shadow: 0 0 0 3px rgba(255, 184, 0, 0.15);
	}

	input[type='email']::placeholder {
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
