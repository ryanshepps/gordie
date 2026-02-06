<script lang="ts">
	import { enhance } from '$app/forms';

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
		<div class="success-message">
			<h3>Check your inbox!</h3>
			<p>Gordie will send you an email to get started. Look for a message from <strong>gordie@lastingsoftware.ca</strong>.</p>
		</div>
	{:else}
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
		padding: 1.5rem;
		background: var(--color-bg-card);
		border: 1px solid var(--color-success);
		border-radius: 0.5rem;
	}

	.success-message h3 {
		color: var(--color-success);
		margin-bottom: 0.5rem;
	}

	.success-message p {
		color: var(--color-text-muted);
		font-size: 0.95rem;
	}

	@media (max-width: 480px) {
		.input-group {
			flex-direction: column;
		}
	}
</style>
