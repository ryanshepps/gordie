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
				description: 'Limited questions and 1 league'
			},
			{
				'@type': 'Offer',
				name: 'Standard',
				price: '10',
				priceCurrency: 'USD',
				description: 'Unlimited questions, 3 leagues, weekly digests and alerts'
			},
			{
				'@type': 'Offer',
				name: 'Contact',
				description: 'Custom support for larger fantasy setups'
			},
			{
				'@type': 'Offer',
				name: 'Self-hosted',
				price: '0',
				priceCurrency: 'USD',
				url: 'https://github.com/ryanshepps/gordie',
				description: 'Run Gordie from the open-source GitHub repository'
			}
		]
	};

	const githubUrl = 'https://github.com/ryanshepps/gordie';

	type Tier = {
		name: string;
		monthlyPrice: number | null;
		annualPrice: number | null;
		priceLabel?: string;
		periodLabel?: string;
		highlight: boolean;
		badge: string | null;
		ctaLabel: string;
		ctaHref: string;
		external?: boolean;
		features: FeatureValue[];
	};

	type FeatureValue = {
		label: string;
		value: string;
		included: boolean;
	};

	let annual = $state(false);

	const tiers: Tier[] = [
		{
			name: 'Free',
			monthlyPrice: 0,
			annualPrice: 0,
			highlight: false,
			badge: null,
			ctaLabel: 'Get Started',
			ctaHref: '/#signup',
			features: [
				{ label: 'Questions per week', value: '3', included: true },
				{ label: 'Leagues', value: '1', included: true },
				{ label: 'Weekly digests', value: '—', included: false },
				{ label: 'News alerts', value: '—', included: false },
				{ label: 'Conversation history', value: '7 days', included: true },
				{ label: 'Priority support', value: '—', included: false }
			]
		},
		{
			name: 'Standard',
			monthlyPrice: 10,
			annualPrice: 80,
			highlight: true,
			badge: 'Most Popular',
			ctaLabel: 'Start Free Trial',
			ctaHref: '/#signup',
			features: [
				{ label: 'Questions per week', value: 'Unlimited', included: true },
				{ label: 'Leagues', value: '3', included: true },
				{ label: 'Weekly digests', value: '✓', included: true },
				{ label: 'News alerts', value: '✓', included: true },
				{ label: 'Conversation history', value: 'Full', included: true },
				{ label: 'Priority support', value: '—', included: false }
			]
		},
		{
			name: 'Contact',
			monthlyPrice: null,
			annualPrice: null,
			priceLabel: 'Custom',
			highlight: false,
			badge: null,
			ctaLabel: 'Contact',
			ctaHref: 'mailto:support@lastingsoftware.ca?subject=Gordie%20custom%20support',
			features: [
				{ label: 'Questions per week', value: 'Unlimited', included: true },
				{ label: 'Leagues', value: 'Unlimited', included: true },
				{ label: 'Weekly digests', value: '✓', included: true },
				{ label: 'News alerts', value: '✓', included: true },
				{ label: 'Conversation history', value: 'Full', included: true },
				{ label: 'Priority support', value: 'By request', included: true }
			]
		},
		{
			name: 'Self-hosted',
			monthlyPrice: 0,
			annualPrice: 0,
			priceLabel: '$0',
			periodLabel: 'run it yourself',
			highlight: false,
			badge: 'Open Source',
			ctaLabel: 'View on GitHub',
			ctaHref: githubUrl,
			external: true,
			features: [
				{ label: 'Questions per week', value: 'Your limits', included: true },
				{ label: 'Leagues', value: 'Configurable', included: true },
				{ label: 'Weekly digests', value: '✓', included: true },
				{ label: 'News alerts', value: '✓', included: true },
				{ label: 'Conversation history', value: 'Self-managed', included: true },
				{ label: 'Priority support', value: '—', included: false }
			]
		}
	];

	function displayPrice(tier: Tier): string {
		if (tier.priceLabel) return tier.priceLabel;
		if (tier.monthlyPrice === 0) return '$0';
		if (tier.monthlyPrice === null) return 'Contact';
		if (tier.annualPrice === null) return `$${tier.monthlyPrice}`;
		return annual ? `$${Math.round(tier.annualPrice / 12)}` : `$${tier.monthlyPrice}`;
	}

	function billingLabel(tier: Tier): string {
		if (tier.periodLabel) return tier.periodLabel;
		if (tier.monthlyPrice === 0) return 'Free forever';
		if (tier.monthlyPrice === null) return '';
		if (tier.annualPrice === null) return '/month';
		return annual ? `$${tier.annualPrice}/year` : '/month';
	}

	function annualSavings(tier: Tier): number {
		if (tier.monthlyPrice === null || tier.annualPrice === null) return 0;
		return tier.monthlyPrice * 12 - tier.annualPrice;
	}
</script>

<SEOHead
	title="Pricing"
	description="Start free, upgrade when you're ready. Gordie offers flexible plans for every fantasy manager — from casual to all-in."
	canonical="/pricing"
/>
<StructuredData data={structuredData} />

<section class="page-hero ambient-glow">
	<div class="container">
		<h1 class="gradient-text">Plans & Pricing</h1>
		<p class="page-sub">
			Start with a 14-day free trial of all features. No credit card required.
		</p>
	</div>
</section>

<section class="pricing-section" aria-labelledby="pricing-heading">
	<div class="container">
		<div class="billing-toggle" role="radiogroup" aria-label="Billing period">
			<button
				class="toggle-option"
				class:active={!annual}
				role="radio"
				aria-checked={!annual}
				onclick={() => (annual = false)}
			>
				Monthly
			</button>
			<button
				class="toggle-option"
				class:active={annual}
				role="radio"
				aria-checked={annual}
				onclick={() => (annual = true)}
			>
				Annual
				<span class="save-badge">Save 33%</span>
			</button>
		</div>

		<div class="pricing-grid">
			{#each tiers as tier}
				<div class="pricing-card" class:highlighted={tier.highlight}>
					{#if tier.badge}
						<span class="tier-badge">{tier.badge}</span>
					{/if}
					<h3 class="tier-name">{tier.name}</h3>
					<div class="price-block">
						<span class="price">{displayPrice(tier)}</span>
						{#if billingLabel(tier)}
							<span class="price-period">{billingLabel(tier)}</span>
						{/if}
					</div>
					{#if annual && tier.monthlyPrice !== null && tier.monthlyPrice > 0}
						<p class="annual-savings">Save ${annualSavings(tier)}/year</p>
					{/if}
					<a
						href={tier.ctaHref}
						class="btn"
						class:btn-primary={tier.highlight}
						class:btn-secondary={!tier.highlight}
						target={tier.external ? '_blank' : undefined}
						rel={tier.external ? 'noopener noreferrer' : undefined}
					>
						{tier.ctaLabel}
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

<section class="trial-section">
	<div class="container trial-inner">
		<h2>Every account starts with 14 days free</h2>
		<p>
			Full access to all Standard features during your trial. No credit card required.
			When your trial ends, you keep the free tier — or upgrade to keep going.
		</p>
		<div class="trial-steps">
			<div class="trial-step">
				<span class="step-number">1</span>
				<h3>Sign up</h3>
				<p>Enter your email and connect your league.</p>
			</div>
			<div class="trial-step">
				<span class="step-number">2</span>
				<h3>Full access for 14 days</h3>
				<p>Unlimited questions, digests, and alerts.</p>
			</div>
			<div class="trial-step">
				<span class="step-number">3</span>
				<h3>Choose your plan</h3>
				<p>Upgrade anytime — just ask Gordie.</p>
			</div>
		</div>
	</div>
</section>

<section class="cta-section">
	<div class="container cta-inner">
		<h2>Ready to win your league?</h2>
		<p>Sign up and start your 14-day free trial.</p>
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

	.billing-toggle {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0;
		margin-bottom: 3rem;
		background: var(--color-bg-card);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.25rem;
		width: fit-content;
		margin-inline: auto;
	}

	.toggle-option {
		padding: 0.5rem 1.25rem;
		border: none;
		background: transparent;
		color: var(--color-text-muted);
		font-weight: 600;
		font-size: 0.9rem;
		cursor: pointer;
		border-radius: 0.375rem;
		transition: all 0.15s ease-out;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.toggle-option.active {
		background: var(--color-bg-elevated);
		color: var(--color-text);
	}

	.save-badge {
		font-size: 0.65rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		background: rgba(0, 255, 136, 0.15);
		color: var(--color-success);
		padding: 0.15rem 0.4rem;
		border-radius: 0.25rem;
	}

	.pricing-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 1.5rem;
		max-width: 1180px;
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
		box-shadow: 0 0 24px rgba(255, 184, 0, 0.08);
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

	.annual-savings {
		color: var(--color-success);
		font-size: 0.8rem;
		font-weight: 600;
		margin-bottom: 0.25rem;
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
		align-items: flex-start;
		gap: 1rem;
		font-size: 0.9rem;
	}

	.feature-label {
		color: var(--color-text-muted);
		text-align: left;
	}

	.feature-value {
		font-weight: 600;
		text-align: right;
	}

	li.included .feature-value {
		color: var(--color-text);
	}

	li.excluded .feature-value {
		color: var(--color-text-muted);
		opacity: 0.5;
	}

	.trial-section {
		padding: 4rem 0;
		background: var(--color-bg-secondary);
	}

	.trial-inner {
		text-align: center;
		max-width: 800px;
		margin-inline: auto;
	}

	.trial-inner > h2 {
		margin-bottom: 0.75rem;
	}

	.trial-inner > p {
		color: var(--color-text-muted);
		font-size: 1.05rem;
		margin-bottom: 2.5rem;
		max-width: 560px;
		margin-inline: auto;
	}

	.trial-steps {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 2rem;
	}

	.trial-step {
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

	.trial-step h3 {
		font-size: 1rem;
		margin-bottom: 0.35rem;
	}

	.trial-step p {
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

	@media (max-width: 1024px) {
		.pricing-grid {
			grid-template-columns: repeat(2, 1fr);
			max-width: 720px;
		}
	}

	@media (max-width: 768px) {
		.pricing-grid {
			grid-template-columns: 1fr;
			max-width: 400px;
		}

		.pricing-card.highlighted {
			order: -1;
		}

		.trial-steps {
			grid-template-columns: 1fr;
			gap: 1.5rem;
		}
	}
</style>
