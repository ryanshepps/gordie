<footer class="footer">
	<div class="container footer-inner">
		<div class="footer-brand">
			<span class="footer-logo">
				<img src="/logo.svg" alt="" class="footer-logo-img" />
				Gordie
			</span>
			<p class="footer-tagline">Your AI fantasy sports assistant.</p>
		</div>
		<nav class="footer-links" aria-label="Footer navigation">
			<a href="/features">Features</a>
			<a href="/how-it-works">How It Works</a>
			<a href="/blog">Blog</a>
		</nav>
		<nav class="footer-legal" aria-label="Legal">
			<a href="/privacy">Privacy</a>
			<a href="/terms">Terms</a>
		</nav>
		<p class="footer-copy">&copy; {new Date().getFullYear()} Lasting Software. All rights reserved.</p>
	</div>
</footer>

<style>
	.footer {
		border-top: 1px solid var(--color-border);
		padding: 3rem 0 2rem;
		margin-top: 6rem;
	}

	.footer-inner {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1.5rem;
		text-align: center;
	}

	.footer-logo {
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 800;
		color: var(--color-text);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.footer-logo-img {
		height: 28px;
		width: 28px;
	}

	.footer-tagline {
		color: var(--color-text-muted);
		font-size: 0.9rem;
		margin-top: 0.25rem;
	}

	.footer-links {
		display: flex;
		gap: 1.5rem;
	}

	.footer-links a {
		color: var(--color-text-muted);
		font-size: 0.9rem;
	}

	.footer-links a:hover {
		color: var(--color-primary);
	}

	.footer-legal {
		display: flex;
		gap: 1.5rem;
	}

	.footer-legal a {
		color: var(--color-text-muted);
		font-size: 0.8rem;
	}

	.footer-legal a:hover {
		color: var(--color-primary);
	}

	.footer-copy {
		color: var(--color-text-muted);
		font-size: 0.8rem;
	}
</style>
