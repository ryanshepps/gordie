<script lang="ts">
	import SEOHead from '$lib/components/SEOHead.svelte';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	const selectedTeam = $derived(
		data.teams.find((team) => teamContext(team) === (form?.selectedTeamContext ?? data.selectedTeamContext)) ??
			null
	);
	const hasTeams = $derived(data.teams.length > 0);
	const canAsk = $derived(Boolean(data.session.provider_connected && selectedTeam));

	function teamContext(team: PageData['teams'][number]) {
		return `Yahoo:${team.game_key}:${team.league_id}:${team.team_id}`;
	}
</script>

<SEOHead
	title="Try Gordie"
	description="Connect Yahoo Fantasy and ask Gordie one league-specific fantasy sports question in a temporary hosted trial."
	canonical="/trial"
/>

<section class="trial-shell ambient-glow">
	<div class="container trial-layout">
		<div class="trial-intro">
			<p class="label live-label"><span class="pulse-dot"></span> Hosted trial</p>
			<h1 class="gradient-text">Try Gordie with your Yahoo league</h1>
			<p class="trial-copy">
				Start a temporary 7-day session, connect Yahoo Fantasy, pick a team, and ask a league-specific question.
			</p>
			<div class="trial-stats" aria-label="Trial status">
				<div>
					<span>{data.session.remaining_questions}</span>
					<p>Questions left</p>
				</div>
				<div>
					<span>{data.session.provider_connected ? 'ON' : 'OFF'}</span>
					<p>Yahoo link</p>
				</div>
			</div>
		</div>

		<div class="trial-panel">
			<section class="trial-step">
				<div class="step-heading">
					<span>01</span>
					<h2>Connect Yahoo</h2>
				</div>
				{#if data.session.provider_connected}
					<p class="connected">Connected{data.session.provider_email ? ` as ${data.session.provider_email}` : ''}</p>
				{:else}
					<form method="POST" action="?/connectYahoo">
						<button class="btn btn-primary" type="submit">Connect Yahoo Fantasy</button>
					</form>
				{/if}
			</section>

			<section class="trial-step">
				<div class="step-heading">
					<span>02</span>
					<h2>Select Team</h2>
				</div>
				{#if hasTeams}
					<div class="team-list">
						{#each data.teams as team}
							<form method="POST" action="?/selectTeam" class:selected={teamContext(team) === (form?.selectedTeamContext ?? data.selectedTeamContext)}>
								<input type="hidden" name="sport" value={team.sport} />
								<input type="hidden" name="season" value={team.season} />
								<input type="hidden" name="game_key" value={team.game_key} />
								<input type="hidden" name="league_id" value={team.league_id} />
								<input type="hidden" name="team_id" value={team.team_id} />
								<input type="hidden" name="team_name" value={team.team_name} />
								<input type="hidden" name="is_active" value={team.is_active ? 'true' : 'false'} />
								<button class="team-button" type="submit" aria-pressed={teamContext(team) === (form?.selectedTeamContext ?? data.selectedTeamContext)}>
									<span>{team.team_name}</span>
									<small>{team.sport.toUpperCase()} · League {team.league_id}</small>
								</button>
							</form>
						{/each}
					</div>
				{:else if data.session.provider_connected}
					<p class="muted">No supported Yahoo teams were found for this account.</p>
				{:else}
					<p class="muted">Connect Yahoo first.</p>
				{/if}
			</section>

			<section class="trial-step">
				<div class="step-heading">
					<span>03</span>
					<h2>Ask Gordie</h2>
				</div>
				<form method="POST" action="?/ask" class="ask-form">
					<input type="hidden" name="team_context" value={selectedTeam ? teamContext(selectedTeam) : ''} />
					<label for="question" class="sr-only">Question</label>
					<textarea
						id="question"
						name="question"
						rows="4"
						placeholder="Who should I start this week?"
						disabled={!canAsk}
					></textarea>
					<button class="btn btn-primary" type="submit" disabled={!canAsk}>Ask Gordie</button>
				</form>
			</section>

			{#if form?.error}
				<p class="error" role="alert">{form.error}</p>
			{/if}

			{#if form?.answer}
				<article class="answer-card">
					<p class="label">Gordie</p>
					<p>{form.answer}</p>
					{#if form.remainingQuestions !== undefined}
						<small>{form.remainingQuestions} trial questions left</small>
					{/if}
				</article>
			{/if}

			<section class="save-panel">
				<div>
					<p class="label">Temporary chat</p>
					<p>Save by email to continue this session later.</p>
				</div>
				<form method="POST" action="?/save" class="save-form">
					<label for="save-email" class="sr-only">Email</label>
					<input id="save-email" name="email" type="email" placeholder="you@example.com" autocomplete="email" />
					<button class="btn btn-outline" type="submit">Send Link</button>
				</form>
				{#if data.saved}
					<p class="success">Session saved.</p>
				{/if}
				{#if form?.saveSent}
					<p class="success">Check your email for the continue link.</p>
				{/if}
				{#if form?.saveError}
					<p class="error" role="alert">{form.saveError}</p>
				{/if}
			</section>
		</div>
	</div>
</section>

<style>
	.trial-shell {
		min-height: calc(100vh - var(--header-height));
		padding: 5rem 0;
	}

	.trial-layout {
		display: grid;
		grid-template-columns: minmax(0, 0.85fr) minmax(360px, 1.15fr);
		gap: 2rem;
		align-items: start;
	}

	.trial-intro {
		position: sticky;
		top: calc(var(--header-height) + 2rem);
	}

	.live-label {
		color: var(--color-primary);
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}

	.pulse-dot {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		background: var(--color-success);
		box-shadow: 0 0 14px rgba(0, 255, 136, 0.6);
		animation: pulse 2s ease-in-out infinite;
	}

	.trial-intro h1 {
		max-width: 640px;
		margin-bottom: 1.25rem;
	}

	.trial-copy {
		color: var(--color-text-muted);
		font-size: 1.08rem;
		max-width: 560px;
		margin-bottom: 1.5rem;
	}

	.trial-stats {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 150px));
		gap: 0.75rem;
	}

	.trial-stats div {
		background: var(--color-bg-card);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 1rem;
	}

	.trial-stats span {
		display: block;
		font-size: 2rem;
		line-height: 1;
		font-weight: 800;
		color: var(--color-primary);
		font-variant-numeric: tabular-nums;
	}

	.trial-stats p {
		color: var(--color-text-muted);
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		margin-top: 0.35rem;
	}

	.trial-panel {
		background: var(--color-bg-card);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		overflow: hidden;
	}

	.trial-step {
		padding: 1.25rem;
		border-bottom: 1px solid var(--color-border);
	}

	.trial-step:last-of-type {
		border-bottom: 0;
	}

	.step-heading {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	.step-heading span {
		color: var(--color-primary);
		font-weight: 800;
		font-variant-numeric: tabular-nums;
	}

	.step-heading h2 {
		font-size: 1.35rem;
	}

	.connected {
		color: var(--color-success);
		font-weight: 700;
	}

	.team-list {
		display: grid;
		gap: 0.75rem;
	}

	.team-list form.selected .team-button {
		border-color: var(--color-success);
	}

	.team-button {
		width: 100%;
		text-align: left;
		background: var(--color-bg-elevated);
		color: var(--color-text);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.9rem 1rem;
		cursor: pointer;
		transition: border-color 0.2s ease-out, transform 0.1s ease-out;
	}

	.team-button:hover {
		border-color: var(--color-primary);
	}

	.team-button:active {
		transform: scale(0.99);
	}

	.team-button span,
	.team-button small {
		display: block;
	}

	.team-button span {
		font-weight: 800;
	}

	.team-button small,
	.muted {
		color: var(--color-text-muted);
	}

	.ask-form {
		display: grid;
		gap: 0.75rem;
	}

	textarea {
		width: 100%;
		resize: vertical;
		min-height: 130px;
		background: var(--color-bg-elevated);
		color: var(--color-text);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 1rem;
		font: inherit;
	}

	textarea:focus {
		outline: 2px solid rgba(255, 184, 0, 0.35);
		border-color: var(--color-primary);
	}

	textarea:disabled,
	button:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	.error {
		margin: 1rem 1.25rem;
		color: var(--color-error);
	}

	.answer-card {
		margin: 1.25rem;
		padding: 1.25rem;
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
	}

	.answer-card p:not(.label) {
		white-space: pre-wrap;
	}

	.answer-card small {
		display: block;
		color: var(--color-text-muted);
		margin-top: 1rem;
	}

	.save-panel {
		margin: 1.25rem;
		padding: 1.25rem;
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		display: grid;
		gap: 1rem;
	}

	.save-panel p:not(.label) {
		color: var(--color-text-muted);
	}

	.save-form {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 0.75rem;
	}

	input[type='email'] {
		width: 100%;
		background: var(--color-bg-card);
		color: var(--color-text);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.85rem 1rem;
		font: inherit;
	}

	input[type='email']:focus {
		outline: 2px solid rgba(255, 184, 0, 0.35);
		border-color: var(--color-primary);
	}

	.success {
		color: var(--color-success);
		font-weight: 700;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.45;
		}
	}

	@media (max-width: 860px) {
		.trial-layout {
			grid-template-columns: 1fr;
		}

		.trial-intro {
			position: static;
		}
	}

	@media (max-width: 520px) {
		.trial-shell {
			padding: 3rem 0;
		}

		.trial-stats {
			grid-template-columns: 1fr;
		}

		.save-form {
			grid-template-columns: 1fr;
		}
	}
</style>
