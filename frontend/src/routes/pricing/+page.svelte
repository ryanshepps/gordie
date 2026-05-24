<script lang="ts">
	import SEOHead from '$lib/components/SEOHead.svelte';
	import StructuredData from '$lib/components/StructuredData.svelte';
	import SignupForm from '$lib/components/SignupForm.svelte';

	const structuredData = {
		'@context': 'https://schema.org',
		'@type': 'Product',
		name: 'Gordie',
		description:
			'AI-powered fantasy sports assistant with lineup optimization, trade analysis, and weekly digests.',
		offers: [
			{
				'@type': 'Offer',
				name: 'Free',
				price: '0',
				priceCurrency: 'USD',
				description: 'Digest updates for one team'
			},
			{
				'@type': 'Offer',
				name: 'Hosted',
				price: '10',
				priceCurrency: 'USD',
				description: 'Ask Gordie questions and connect up to three teams'
			}
		]
	};

	type Tier = {
		name: string;
		monthlyPrice: number;
		highlight: boolean;
		badge: string | null;
		description: string;
		cta: string;
		features: FeatureValue[];
	};

	type FeatureValue = {
		label: string;
		value: string;
		included: boolean;
	};

	const tiers: Tier[] = [
		{
			name: 'Free',
			monthlyPrice: 0,
			highlight: false,
			badge: null,
			description: 'For one team when you just want Gordie to keep you updated.',
			cta: 'Get Started',
			features: [
				{ label: 'Teams connected', value: '1', included: true },
				{ label: 'Injury digests', value: 'Included', included: true },
				{ label: 'Sit/start updates', value: 'Included', included: true },
				{ label: 'Ask Gordie questions', value: 'Upgrade', included: false }
			]
		},
		{
			name: 'Hosted',
			monthlyPrice: 10,
			highlight: true,
			badge: 'Hosted plan',
			description: 'For managers who want Gordie to answer league questions and cover more teams.',
			cta: 'Upgrade to Hosted',
			features: [
				{ label: 'Teams connected', value: 'Up to 3', included: true },
				{ label: 'Injury digests', value: 'Included', included: true },
				{ label: 'Sit/start updates', value: 'Included', included: true },
				{ label: 'Ask Gordie questions', value: 'Included', included: true }
			]
		}
	];
</script>

<SEOHead
	title="Pricing"
	description="Start free with digest updates for one team. Upgrade to Gordie Hosted for $10/month to ask questions and connect up to three teams."
	canonical="/pricing"
/>
<StructuredData data={structuredData} />

<section class="page-hero ambient-glow">
	<div class="container">
		<h1 class="gradient-text">Plans & Pricing</h1>
		<p class="page-sub">
			Self-hosting is open source. Hosted billing only covers the cost of running Gordie for you.
		</p>
	</div>
</section>

<section class="pricing-section" aria-labelledby="pricing-heading">
	<div class="container">
		<div class="pricing-grid">
			{#each tiers as tier}
				<div class="pricing-card" class:highlighted={tier.highlight}>
					{#if tier.badge}
						<span class="tier-badge">{tier.badge}</span>
					{/if}
					<h3 class="tier-name">{tier.name}</h3>
					<div class="price-block">
						<span class="price">${tier.monthlyPrice}</span>
						<span class="price-period">{tier.monthlyPrice === 0 ? 'free' : '/month'}</span>
					</div>
					<p class="tier-description">{tier.description}</p>
					<a href="/#signup" class="btn" class:btn-primary={tier.highlight} class:btn-secondary={!tier.highlight}>
						{tier.cta}
					</a>
					<ul class="feature-list">
						{#each tier.features as feature}
							<li class:included={feature.included} class:excluded={!feature.included}>
								<span class="feature-label">{feature.label}</span>
								<span class="feature-value">{feature.value}</span>
							</li>
						{/each}
					</ul>
				</div>
			{/each}
		</div>
	</div>
</section>

<section class="self-host-section">
	<div class="container self-host-inner">
		<h2>Prefer to run it yourself?</h2>
		<p>
			Gordie is open source. Self-hosted deployments can run without Creem keys and skip hosted billing entirely.
		</p>
		<div class="self-host-steps">
			<div class="self-host-step">
				<span class="step-number">1</span>
				<h3>Hosted free</h3>
				<p>One team with injury digests and sit/start updates.</p>
			</div>
			<div class="self-host-step">
				<span class="step-number">2</span>
				<h3>Hosted paid</h3>
				<p>$10/month for questions and up to three teams.</p>
			</div>
			<div class="self-host-step">
				<span class="step-number">3</span>
				<h3>Self-hosted</h3>
				<p>Run your own instance with no hosted billing surface.</p>
			</div>
		</div>
	</div>
</section>

<section class="cta-section">
	<div class="container cta-inner">
		<h2>Ready to connect a team?</h2>
		<p>Start free and let Gordie handle the updates.</p>
		<SignupForm />
	</div>
</section>

<style>
	.page-hero {
		padding: 5rem 0 3rem;
		position: relative;
		z-index: 1;
		text-align: center;
	}

	.page-sub {
		color: var(--color-text-muted);
		font-size: 1.15rem;
		margin-top: 0.75rem;
		max-width: 500px;
		margin-inline: auto;
	}

	.pricing-section {
		padding: 2rem 0 4rem;
	}

	.pricing-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1.5rem;
		max-width: 760px;
		margin-inline: auto;
	}

	.pricing-card {
		background: var(--color-bg-card);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 2rem 1.5rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		position: relative;
		transition: border-color 0.2s, transform 0.2s;
	}

	.pricing-card:hover {
		border-color: var(--color-border);
		transform: translateY(-2px);
	}

	.pricing-card.highlighted {
		border-color: var(--color-primary);
		box-shadow: 0 0 24px rgba(0, 229, 255, 0.08);
	}

	.pricing-card.highlighted:hover {
		border-color: var(--color-primary);
	}

	.tier-badge {
		position: absolute;
		top: -0.75rem;
		font-size: 0.65rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		background: var(--color-primary);
		color: #0f0d09;
		padding: 0.25rem 0.75rem;
		border-radius: 0.25rem;
	}

	.tier-name {
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		margin-bottom: 1rem;
	}

	.price-block {
		display: flex;
		align-items: baseline;
		gap: 0.25rem;
		margin-bottom: 0.25rem;
	}

	.price {
		font-size: 3rem;
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		line-height: 1;
	}

	.price-period {
		color: var(--color-text-muted);
		font-size: 0.9rem;
	}

	.tier-description {
		color: var(--color-text-muted);
		font-size: 0.95rem;
		min-height: 4.5rem;
	}

	.pricing-card .btn {
		margin-top: 1.25rem;
		width: 100%;
		text-align: center;
		display: inline-block;
		padding: 0.65rem 1.5rem;
		font-weight: 700;
		font-size: 0.9rem;
		border-radius: 0.375rem;
		transition: all 0.15s ease-out;
		text-decoration: none;
	}

	.pricing-card .btn:hover {
		text-decoration: none;
	}

	.btn-secondary {
		border: 1px solid var(--color-border);
		background: transparent;
		color: var(--color-text);
	}

	.btn-secondary:hover {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}

	.feature-list {
		list-style: none;
		width: 100%;
		margin-top: 1.5rem;
		padding-top: 1.5rem;
		border-top: 1px solid var(--color-border);
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.feature-list li {
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-size: 0.9rem;
	}

	.feature-label {
		color: var(--color-text-muted);
	}

	.feature-value {
		font-weight: 600;
	}

	li.included .feature-value {
		color: var(--color-text);
	}

	li.excluded .feature-value {
		color: var(--color-text-muted);
		opacity: 0.5;
	}

	.self-host-section {
		padding: 4rem 0;
		background: var(--color-bg-secondary);
	}

	.self-host-inner {
		text-align: center;
		max-width: 800px;
		margin-inline: auto;
	}

	.self-host-inner > h2 {
		margin-bottom: 0.75rem;
	}

	.self-host-inner > p {
		color: var(--color-text-muted);
		font-size: 1.05rem;
		margin-bottom: 2.5rem;
		max-width: 560px;
		margin-inline: auto;
	}

	.self-host-steps {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 2rem;
	}

	.self-host-step {
		text-align: center;
	}

	.step-number {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 40px;
		height: 40px;
		border-radius: 50%;
		background: var(--color-primary);
		color: #0f0d09;
		font-weight: 700;
		font-size: 1.1rem;
		margin-bottom: 0.75rem;
	}

	.self-host-step h3 {
		font-size: 1rem;
		margin-bottom: 0.35rem;
	}

	.self-host-step p {
		color: var(--color-text-muted);
		font-size: 0.9rem;
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

	@media (max-width: 768px) {
		.pricing-grid {
			grid-template-columns: 1fr;
			max-width: 400px;
		}

		.self-host-steps {
			grid-template-columns: 1fr;
			gap: 1.5rem;
		}
	}
</style>
