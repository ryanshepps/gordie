<script lang="ts">
	import SEOHead from '$lib/components/SEOHead.svelte';
	import StructuredData from '$lib/components/StructuredData.svelte';
	import SignupForm from '$lib/components/SignupForm.svelte';

	const structuredData = {
		'@context': 'https://schema.org',
		'@type': 'SoftwareApplication',
		name: 'Gordie',
		applicationCategory: 'SportsApplication',
		operatingSystem: 'Web',
		description: 'AI-powered fantasy sports assistant that helps you make smarter lineup decisions, waiver wire pickups, and trade evaluations.',
		offers: {
			'@type': 'Offer',
			price: '0',
			priceCurrency: 'USD',
			description: 'Free digest updates for one team'
		}
	};

	const features = [
		{
			title: 'Lineup Optimization',
			description: 'Upgrade to ask Gordie for lineup recommendations based on matchups, recent performance, and rest schedules.',
		},
		{
			title: 'Waiver Wire Alerts',
			description: 'Be the first to know when a breakout player hits waivers, with analysis on why they matter.',
		},
		{
			title: 'Trade Evaluation',
			description: 'Hosted users can ask Gordie about trades and get an honest breakdown of value for both sides.',
		},
		{
			title: 'Weekly Digests',
			description: 'Start every week with a personalized report on your team, upcoming matchups, and key storylines.',
		}
	];

	const platforms = [
		{ name: 'Yahoo Fantasy', status: 'supported' },
		{ name: 'ESPN', status: 'coming-soon' },
		{ name: 'Fantrax', status: 'coming-soon' }
	];

	const sports = [
		{ name: 'Hockey', status: 'supported' },
		{ name: 'Football', status: 'coming-soon' },
		{ name: 'Basketball', status: 'coming-soon' },
		{ name: 'Soccer', status: 'coming-soon' }
	];

	const steps = [
		{ step: '1', title: 'Sign up with your email', description: 'Enter your email below and Gordie will reach out.' },
		{ step: '2', title: 'Connect your league', description: 'Link your Yahoo Fantasy account so Gordie can see your roster.' },
		{ step: '3', title: 'Get updates or upgrade', description: 'Stay free for one-team digests, or upgrade to ask Gordie questions and connect up to three teams.' }
	];
</script>

<SEOHead
	title="AI Fantasy Sports Assistant"
	description="Gordie is your AI-powered fantasy sports assistant. Get lineup advice, waiver wire alerts, trade evaluations, and weekly digests — all through email."
	canonical="/"
/>
<StructuredData data={structuredData} />

<section class="hero ambient-glow">
	<div class="container hero-inner">
		<h1 class="gradient-text">Your AI fantasy sports assistant</h1>
		<p class="hero-sub">
			Gordie sends free digest updates for one fantasy team. Upgrade to ask questions and connect up to three teams.
		</p>
		<div class="hero-actions">
			<a class="btn btn-primary" href="/trial">Try Gordie now</a>
			<a class="btn btn-outline" href="#signup">Join by email</a>
		</div>
		<SignupForm />
	</div>
</section>

<section class="features-section" aria-labelledby="features-heading">
	<div class="container">
		<h2 id="features-heading">What Gordie does for you</h2>
		<div class="features-grid">
			{#each features as { title, description }}
				<article class="feature-card card card-animate">
					<h3>{title}</h3>
					<p>{description}</p>
				</article>
			{/each}
		</div>
	</div>
</section>

<section class="compat-section" aria-labelledby="compat-heading">
	<div class="container">
		<h2 id="compat-heading">Platforms & Sports</h2>
		<div class="compat-grid">
			<div class="compat-column">
				<h3 class="compat-column-title">Platforms</h3>
				{#each platforms as { name, status }}
					<div class="compat-item" class:compat-supported={status === 'supported'}>
						<span class="compat-name">{name}</span>
						<span class="compat-badge" class:badge-supported={status === 'supported'} class:badge-soon={status === 'coming-soon'}>
							{status === 'supported' ? 'Supported' : 'Coming Soon'}
						</span>
					</div>
				{/each}
			</div>
			<div class="compat-column">
				<h3 class="compat-column-title">Sports</h3>
				{#each sports as { name, status }}
					<div class="compat-item" class:compat-supported={status === 'supported'}>
						<span class="compat-name">{name}</span>
						<span class="compat-badge" class:badge-supported={status === 'supported'} class:badge-soon={status === 'coming-soon'}>
							{status === 'supported' ? 'Supported' : 'Coming Soon'}
						</span>
					</div>
				{/each}
			</div>
		</div>
	</div>
</section>

<section class="how-section" aria-labelledby="how-heading">
	<div class="container">
		<h2 id="how-heading">Get started in 3 steps</h2>
		<div class="steps-grid">
			{#each steps as { step, title, description }}
				<div class="step-card">
					<span class="step-number">{step}</span>
					<h3>{title}</h3>
					<p>{description}</p>
				</div>
			{/each}
		</div>
	</div>
</section>

<section class="cta-section" aria-labelledby="cta-heading">
	<div class="container cta-inner">
		<h2 id="cta-heading">Ready to win your league?</h2>
		<p>Join the beta and let Gordie handle the research.</p>
		<SignupForm id="signup" />
	</div>
</section>

<style>
	.hero {
		padding: 8rem 0 5rem;
		position: relative;
	}

	.hero-inner {
		max-width: 640px;
	}

	.hero h1 {
		margin-bottom: 1.5rem;
	}

	.hero-sub {
		font-size: 1.2rem;
		color: var(--color-text-muted);
		margin-bottom: 1.25rem;
		line-height: 1.7;
	}

	.hero-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		margin-bottom: 2rem;
	}

	.features-section {
		padding: 4rem 0;
		background: var(--color-bg-secondary);
	}

	.features-section h2 {
		margin-bottom: 2.5rem;
	}

	.features-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
		gap: 1.5rem;
	}

	.feature-card {
		padding: 1.5rem;
	}

	.feature-card h3 {
		margin-bottom: 0.5rem;
		font-size: 1.15rem;
	}

	.feature-card p {
		color: var(--color-text-muted);
		font-size: 0.95rem;
	}

	.compat-section {
		padding: 4rem 0;
	}

	.compat-section h2 {
		margin-bottom: 2rem;
	}

	.compat-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 2rem;
		max-width: 700px;
	}

	.compat-column-title {
		font-family: var(--font-sans);
		text-transform: uppercase;
		font-size: 0.75rem;
		letter-spacing: 0.06em;
		font-weight: 600;
		color: var(--color-text-muted);
		margin-bottom: 0.75rem;
	}

	.compat-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.75rem 1rem;
		background: var(--color-bg-card);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.compat-item.compat-supported {
		border-color: rgba(0, 255, 136, 0.25);
	}

	.compat-name {
		font-weight: 500;
		font-size: 0.95rem;
	}

	.compat-badge {
		font-size: 0.7rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		padding: 0.2rem 0.5rem;
		border-radius: 0.25rem;
	}

	.badge-supported {
		background: rgba(0, 255, 136, 0.12);
		color: var(--color-success);
	}

	.badge-soon {
		background: rgba(156, 148, 134, 0.12);
		color: var(--color-text-muted);
	}

	@media (max-width: 560px) {
		.compat-grid {
			grid-template-columns: 1fr;
		}
	}

	.how-section {
		padding: 4rem 0;
	}

	.how-section h2 {
		margin-bottom: 2.5rem;
	}

	.steps-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 2rem;
	}

	.step-card {
		text-align: center;
	}

	.step-number {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 48px;
		height: 48px;
		border-radius: 50%;
		background: var(--color-primary);
		color: #0F0D09;
		font-weight: 700;
		font-size: 1.25rem;
		margin-bottom: 1rem;
	}

	.step-card h3 {
		margin-bottom: 0.5rem;
		font-size: 1.1rem;
	}

	.step-card p {
		color: var(--color-text-muted);
		font-size: 0.95rem;
	}

	.cta-section {
		padding: 4rem 0;
		position: relative;
	}

	.cta-section::before {
		content: '';
		position: absolute;
		inset: 0;
		background: radial-gradient(ellipse at 50% 50%, rgba(255, 184, 0, 0.05) 0%, transparent 60%);
		pointer-events: none;
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
