<script lang="ts">
	import SEOHead from '$lib/components/SEOHead.svelte';
</script>

<SEOHead
	title="Privacy Policy"
	description="How Gordie collects, uses, and protects your data. Read our privacy policy."
	canonical="/privacy"
	noindex={true}
/>

<article class="legal-page">
	<div class="container legal-container">
		<h1>Privacy Policy</h1>
		<p class="last-updated">Last updated: February 5, 2025</p>

		<section>
			<h2>Overview</h2>
			<p>Gordie ("we", "us", "our") is a product of Lasting Software. This policy explains how we collect, use, and protect your information when you use Gordie, our AI fantasy sports assistant.</p>
		</section>

		<section>
			<h2>Information We Collect</h2>

			<h3>Information you provide</h3>
			<ul>
				<li><strong>Email address</strong> — required to create your account and communicate with Gordie.</li>
				<li><strong>Email content</strong> — the messages you send to Gordie, used to provide advice and maintain conversation context.</li>
			</ul>

			<h3>Information from third parties</h3>
			<ul>
				<li><strong>Yahoo Fantasy data</strong> — when you connect your Yahoo Fantasy account, we access your team rosters, league settings, standings, and related fantasy data via the Yahoo Fantasy API. We request <strong>read-only access</strong> and never modify your roster or make transactions on your behalf.</li>
			</ul>

			<h3>Information collected automatically</h3>
			<ul>
				<li><strong>Usage data</strong> — we track which features you use (e.g., lineup advice, trade analysis) to improve the service. We do not track browsing activity across other websites.</li>
			</ul>
		</section>

		<section>
			<h2>How We Use Your Information</h2>
			<ul>
				<li>To provide personalized fantasy advice based on your roster and league.</li>
				<li>To send you weekly digests and alerts you've opted into.</li>
				<li>To maintain conversation history so Gordie can provide contextual advice.</li>
				<li>To improve the quality and accuracy of Gordie's recommendations.</li>
			</ul>
		</section>

		<section>
			<h2>Data Sharing</h2>
			<p>We do not sell your personal information. We share data only in these limited cases:</p>
			<ul>
				<li><strong>AI model providers</strong> — your messages are processed by large language model APIs to generate responses. Messages are not used to train third-party models.</li>
				<li><strong>Email delivery</strong> — we use Mailgun to send and receive emails on Gordie's behalf.</li>
				<li><strong>Infrastructure</strong> — our website is hosted on Cloudflare and our backend runs on standard cloud infrastructure.</li>
				<li><strong>Legal requirements</strong> — we may disclose information if required by law.</li>
			</ul>
		</section>

		<section>
			<h2>Data Retention</h2>
			<p>We retain your conversation history and fantasy data for as long as your account is active. If you request account deletion, we will delete your data within 30 days.</p>
		</section>

		<section>
			<h2>Security</h2>
			<p>We use industry-standard security measures including encrypted connections (TLS), secure OAuth 2.0 for third-party authentication, and access controls on our infrastructure. No system is perfectly secure, but we take reasonable steps to protect your data.</p>
		</section>

		<section>
			<h2>Your Rights</h2>
			<p>You can:</p>
			<ul>
				<li>Request a copy of the data we hold about you.</li>
				<li>Request deletion of your account and associated data.</li>
				<li>Disconnect your Yahoo Fantasy account at any time through Yahoo's account settings.</li>
			</ul>
			<p>To exercise these rights, email us at <a href="mailto:support@lastingsoftware.ca">support@lastingsoftware.ca</a>.</p>
		</section>

		<section>
			<h2>Changes to This Policy</h2>
			<p>We may update this policy from time to time. If we make significant changes, we'll notify you by email.</p>
		</section>

		<section>
			<h2>Contact</h2>
			<p>Questions about this policy? Email <a href="mailto:support@lastingsoftware.ca">support@lastingsoftware.ca</a>.</p>
		</section>
	</div>
</article>

<style>
	.legal-page {
		padding: 4rem 0;
	}

	.legal-container {
		max-width: 720px;
	}

	.legal-container h1 {
		font-family: var(--font-sans);
		text-transform: none;
		letter-spacing: normal;
		margin-bottom: 0.5rem;
	}

	.last-updated {
		color: var(--color-text-muted);
		font-size: 0.9rem;
		margin-bottom: 2.5rem;
	}

	section {
		margin-bottom: 2rem;
	}

	section h2 {
		font-family: var(--font-sans);
		text-transform: none;
		letter-spacing: normal;
		font-size: 1.35rem;
		margin-bottom: 0.75rem;
	}

	section h3 {
		font-family: var(--font-sans);
		text-transform: none;
		letter-spacing: normal;
		font-size: 1.1rem;
		margin-top: 1rem;
		margin-bottom: 0.5rem;
	}

	section p {
		color: var(--color-text-muted);
		margin-bottom: 0.75rem;
		line-height: 1.7;
	}

	section ul {
		color: var(--color-text-muted);
		padding-left: 1.5rem;
		margin-bottom: 0.75rem;
	}

	section li {
		margin-bottom: 0.5rem;
		line-height: 1.7;
	}
</style>
