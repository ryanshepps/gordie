<script lang="ts">
	import SEOHead from '$lib/components/SEOHead.svelte';
	import StructuredData from '$lib/components/StructuredData.svelte';
	import SignupForm from '$lib/components/SignupForm.svelte';

	const faqData = {
		'@context': 'https://schema.org',
		'@type': 'FAQPage',
		mainEntity: [
			{
				'@type': 'Question',
				name: 'What fantasy platforms does Gordie support?',
				acceptedAnswer: {
					'@type': 'Answer',
					text: 'Gordie currently supports Yahoo Fantasy, with more platforms like ESPN and Fantrax coming soon.'
				}
			},
			{
				'@type': 'Question',
				name: 'How does Gordie communicate?',
				acceptedAnswer: {
					'@type': 'Answer',
					text: 'Gordie works entirely through email. Send a question, get a detailed reply — no app to install.'
				}
			},
			{
				'@type': 'Question',
				name: 'Is Gordie free?',
				acceptedAnswer: {
					'@type': 'Answer',
					text: 'Gordie is free for digest updates on one team. The hosted upgrade is $10/month for questions and up to three teams.'
				}
			},
			{
				'@type': 'Question',
				name: 'What kind of advice does Gordie give?',
				acceptedAnswer: {
					'@type': 'Answer',
					text: 'Gordie can help with lineup decisions, waiver wire pickups, trade evaluations, injury impact analysis, and weekly strategy. It uses real stats and matchup data.'
				}
			}
		]
	};

	const features = [
		{
			title: 'Lineup Optimization',
			description: 'Hosted users can ask Gordie to analyze matchups, recent performance, and rest days for lineup recommendations.',
			details: [
				'Accounts for back-to-back games and rest schedules',
				'Weights recent hot/cold streaks',
				'Considers opponent strength and favorable matchups'
			]
		},
		{
			title: 'Waiver Wire Intelligence',
			description: 'Get alerts when high-upside players hit waivers, with clear reasoning on whether they fit your roster.',
			details: [
				'Monitors player performance trends across the league',
				'Evaluates fit with your specific roster needs',
				'Prioritizes pickups by positional scarcity'
			]
		},
		{
			title: 'Trade Evaluation',
			description: 'Hosted users can describe a trade they\'re considering and Gordie breaks down the value on both sides, factoring in schedule, category impact, and playoff outlook.',
			details: [
				'Category-by-category impact analysis',
				'Rest-of-season projections for players involved',
				'Considers your league\'s scoring settings'
			]
		},
		{
			title: 'Weekly Digests',
			description: 'Every week, Gordie sends you a personalized briefing with your team outlook, key matchups, and action items.',
			details: [
				'Personalized to your roster and league standings',
				'Highlights schedule-based advantages',
				'Flags underperforming players to consider benching or dropping'
			]
		},
		{
			title: 'Injury & News Monitoring',
			description: 'Gordie tracks injuries, callups, and roster changes so you can react fast when something affects your roster.',
			details: [
				'Real-time injury impact analysis',
				'Suggests replacement options from waivers',
				'Tracks roster and lineup changes'
			]
		},
		{
			title: 'Email-First Experience',
			description: 'No app to install, no dashboard to check. Just email Gordie like you\'d text a friend who\'s really into fantasy stats.',
			details: [
				'Works from any email client on any device',
				'Conversational — ask follow-up questions naturally',
				'Your conversation history is preserved across threads'
			]
		}
	];
</script>

<SEOHead
	title="Features"
	description="Lineup optimization, waiver wire alerts, trade evaluations, weekly digests, and more. See everything Gordie can do for your fantasy team."
	canonical="/features"
/>
<StructuredData data={faqData} />

<section class="page-hero ambient-glow">
	<div class="container">
		<h1>Features</h1>
		<p class="page-sub">Everything you need to manage your fantasy team — delivered to your inbox.</p>
	</div>
</section>

<section class="features-detail">
	<div class="container">
		{#each features as { title, description, details }}
			<article class="feature-block">
				<div class="feature-text">
					<h2>{title}</h2>
					<p>{description}</p>
					<ul>
						{#each details as detail}
							<li>{detail}</li>
						{/each}
					</ul>
				</div>
			</article>
		{/each}
	</div>
</section>

<section class="faq-section" aria-labelledby="faq-heading">
	<div class="container">
		<h2 id="faq-heading">Frequently Asked Questions</h2>
		<div class="faq-list">
			{#each faqData.mainEntity as { name, acceptedAnswer }}
				<details class="faq-item">
					<summary>{name}</summary>
					<p>{acceptedAnswer.text}</p>
				</details>
			{/each}
		</div>
	</div>
</section>

<section class="cta-section">
	<div class="container cta-inner">
		<h2>Try Gordie for free</h2>
		<p>Sign up and get your first weekly digest within minutes.</p>
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

	.features-detail {
		padding: 2rem 0;
	}

	.feature-block {
		padding: 2.5rem 0;
		border-bottom: 1px solid var(--color-border);
	}

	.feature-block:last-child {
		border-bottom: none;
	}

	.feature-text h2 {
		font-size: 1.5rem;
		margin-bottom: 0.75rem;
	}

	.feature-text p {
		color: var(--color-text-muted);
		font-size: 1.05rem;
		margin-bottom: 1rem;
		max-width: 640px;
	}

	.feature-text ul {
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.feature-text li {
		color: var(--color-text-muted);
		font-size: 0.95rem;
		padding-left: 1.5rem;
		position: relative;
	}

	.feature-text li::before {
		content: '→';
		position: absolute;
		left: 0;
		color: var(--color-accent);
	}

	.faq-section {
		padding: 4rem 0;
	}

	.faq-section h2 {
		margin-bottom: 2rem;
	}

	.faq-list {
		max-width: 700px;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.faq-item {
		background: var(--color-bg-card);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 1rem 1.25rem;
		cursor: pointer;
	}

	.faq-item summary {
		font-family: var(--font-sans);
		text-transform: none;
		letter-spacing: normal;
		font-weight: 600;
		font-size: 1rem;
		list-style: none;
	}

	.faq-item summary::-webkit-details-marker {
		display: none;
	}

	.faq-item p {
		color: var(--color-text-muted);
		margin-top: 0.75rem;
		font-size: 0.95rem;
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
