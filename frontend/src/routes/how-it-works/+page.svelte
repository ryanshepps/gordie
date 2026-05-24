<script lang="ts">
	import SEOHead from '$lib/components/SEOHead.svelte';
	import StructuredData from '$lib/components/StructuredData.svelte';
	import SignupForm from '$lib/components/SignupForm.svelte';

	const howToData = {
		'@context': 'https://schema.org',
		'@type': 'HowTo',
		name: 'How to get started with Gordie',
		description: 'Set up your AI fantasy sports assistant in 3 simple steps.',
		step: [
			{
				'@type': 'HowToStep',
				position: 1,
				name: 'Sign up with your email',
				text: 'Enter your email address and Gordie will send you a welcome message with next steps.'
			},
			{
				'@type': 'HowToStep',
				position: 2,
				name: 'Connect your Yahoo Fantasy account',
				text: 'Click the secure link in Gordie\'s email to authorize read access to your fantasy teams. Gordie never makes changes to your roster.'
			},
			{
				'@type': 'HowToStep',
				position: 3,
				name: 'Start emailing Gordie',
				text: 'Ask Gordie anything about your fantasy team. Get lineup advice, trade analysis, waiver wire picks, and more — all by email.'
			}
		]
	};

	const steps = [
		{
			number: '1',
			title: 'Sign up with your email',
			description: 'Enter your email below. Gordie will send you a welcome message within a minute.',
			detail: 'No app to install, no password to remember. Gordie lives in your inbox.'
		},
		{
			number: '2',
			title: 'Connect your Yahoo Fantasy account',
			description: 'Gordie\'s welcome email includes a secure link to connect your Yahoo Fantasy account.',
			detail: 'Gordie only requests read access — it will never modify your roster, make trades, or drop players on your behalf.'
		},
		{
			number: '3',
			title: 'Email Gordie anytime',
			description: 'Just reply to any of Gordie\'s emails, or start a new thread. Ask whatever\'s on your mind.',
			detail: 'Gordie remembers your previous conversations, so you can pick up right where you left off.'
		}
	];

	const examples = [
		{ question: 'I have two guys at the same position — who do I start?', context: 'Matchup-based lineup advice' },
		{ question: 'Someone dropped a top prospect — is he worth a pickup?', context: 'Waiver wire evaluation' },
		{ question: 'I got offered a 2-for-1 trade. Is it worth it?', context: 'Trade analysis' },
		{ question: 'Who are the best streamers for this week?', context: 'Schedule-based strategy' }
	];
</script>

<SEOHead
	title="How It Works"
	description="Get set up with Gordie in under 2 minutes. Sign up, connect your Yahoo Fantasy account, and start getting AI-powered fantasy advice by email."
	canonical="/how-it-works"
/>
<StructuredData data={howToData} />

<section class="page-hero ambient-glow">
	<div class="container">
		<h1>How It Works</h1>
		<p class="page-sub">Get your AI fantasy sports assistant up and running in under 2 minutes.</p>
	</div>
</section>

<section class="steps-section" aria-labelledby="steps-heading">
	<div class="container">
		<h2 id="steps-heading" class="sr-only">Setup steps</h2>
		<div class="steps-list">
			{#each steps as { number, title, description, detail }}
				<div class="step">
					<div class="step-indicator">
						<span class="step-number">{number}</span>
						<div class="step-line"></div>
					</div>
					<div class="step-content">
						<h3>{title}</h3>
						<p>{description}</p>
						<p class="step-detail">{detail}</p>
					</div>
				</div>
			{/each}
		</div>
	</div>
</section>

<section class="examples-section" aria-labelledby="examples-heading">
	<div class="container">
		<h2 id="examples-heading">Things you can ask Gordie</h2>
		<div class="examples-grid">
			{#each examples as { question, context }}
				<div class="example-card card card-animate">
					<p class="example-question">"{question}"</p>
					<p class="example-context">{context}</p>
				</div>
			{/each}
		</div>
	</div>
</section>

<section class="cta-section">
	<div class="container cta-inner">
		<h2>Ready to get started?</h2>
		<p>Sign up now and Gordie will email you in under a minute.</p>
		<SignupForm />
	</div>
</section>

<style>
	.page-hero {
		padding: 5rem 0 3rem;
		position: relative;
		z-index: 1;
	}

	.page-sub {
		color: var(--color-text-muted);
		font-size: 1.15rem;
		margin-top: 0.75rem;
		max-width: 600px;
	}

	.steps-section {
		padding: 2rem 0 4rem;
	}

	.steps-list {
		max-width: 640px;
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	.step {
		display: flex;
		gap: 1.5rem;
	}

	.step-indicator {
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.step-number {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 44px;
		height: 44px;
		border-radius: 50%;
		background: var(--color-primary);
		color: #05091D;
		font-weight: 700;
		font-size: 1.1rem;
		flex-shrink: 0;
	}

	.step-line {
		width: 2px;
		flex: 1;
		background: var(--color-border);
		min-height: 2rem;
	}

	.step:last-child .step-line {
		display: none;
	}

	.step-content {
		padding-bottom: 2.5rem;
	}

	.step-content h3 {
		font-size: 1.2rem;
		margin-bottom: 0.5rem;
	}

	.step-content p {
		color: var(--color-text-muted);
		font-size: 1rem;
	}

	.step-detail {
		margin-top: 0.5rem;
		font-size: 0.9rem !important;
		font-style: italic;
	}

	.examples-section {
		padding: 4rem 0;
		background: var(--color-bg-secondary);
		clip-path: polygon(0 0, 100% 2%, 100% 100%, 0 98%);
	}

	.examples-section h2 {
		margin-bottom: 2rem;
	}

	.examples-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
		gap: 1rem;
	}

	.example-card {
		padding: 1.25rem;
	}

	.example-question {
		font-size: 1rem;
		font-weight: 500;
		margin-bottom: 0.5rem;
	}

	.example-context {
		color: var(--color-text-muted);
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-weight: 600;
	}

	.cta-section {
		padding: 4rem 0;
	}

	.cta-inner {
		max-width: 640px;
		text-align: center;
	}

	.cta-inner h2 {
		margin-bottom: 0.75rem;
	}

	.cta-inner p {
		color: var(--color-text-muted);
		margin-bottom: 2rem;
		font-size: 1.1rem;
	}

	.cta-inner :global(.signup-form-wrapper) {
		margin: 0 auto;
	}
</style>
