<script lang="ts">
	import { page } from '$app/state';

	const navLinks = [
		{ href: '/features', label: 'Features' },
		{ href: '/how-it-works', label: 'How It Works' },
		{ href: '/blog', label: 'Blog' }
	];

	let mobileMenuOpen = $state(false);

	function toggleMenu() {
		mobileMenuOpen = !mobileMenuOpen;
	}

	function closeMenu() {
		mobileMenuOpen = false;
	}
</script>

<header class="header">
	<nav class="container header-nav" aria-label="Main navigation">
		<a href="/" class="logo" onclick={closeMenu}>
			<img src="/logo.svg" alt="" class="logo-img" />
			Gordie
		</a>

		<button
			class="mobile-toggle"
			aria-label="Toggle navigation menu"
			aria-expanded={mobileMenuOpen}
			onclick={toggleMenu}
		>
			<span class="hamburger" class:open={mobileMenuOpen}></span>
		</button>

		<div class="nav-links" class:open={mobileMenuOpen}>
			{#each navLinks as { href, label }}
				<a
					{href}
					class="nav-link"
					class:active={page.url.pathname === href}
					onclick={closeMenu}
				>
					{label}
				</a>
			{/each}
			<a href="/#signup" class="btn btn-primary nav-cta" onclick={closeMenu}>Get Started</a>
		</div>
	</nav>
</header>

<style>
	.header {
		position: sticky;
		top: 0;
		z-index: 100;
		background: rgba(15, 13, 9, 0.9);
		backdrop-filter: blur(12px);
		border-bottom: 1px solid var(--color-border);
		height: var(--header-height);
		display: flex;
		align-items: center;
	}

	.header-nav {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
	}

	.logo {
		font-family: var(--font-display);
		font-size: 1.5rem;
		font-weight: 800;
		color: var(--color-text);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.logo-img {
		height: 32px;
		width: 32px;
	}

	.logo:hover {
		text-decoration: none;
		color: var(--color-accent);
	}

	.nav-links {
		display: flex;
		align-items: center;
		gap: 2rem;
	}

	.nav-link {
		color: var(--color-text-muted);
		font-weight: 500;
		font-size: 0.95rem;
		transition: color 0.2s;
	}

	.nav-link:hover {
		color: var(--color-primary);
		text-decoration: none;
	}

	.nav-link.active {
		color: var(--color-primary);
		text-decoration: none;
		border-bottom: 2px solid var(--color-primary);
		padding-bottom: 2px;
	}

	.nav-cta {
		padding: 0.5rem 1.25rem;
		font-size: 0.9rem;
	}

	.mobile-toggle {
		display: none;
		background: none;
		border: none;
		cursor: pointer;
		padding: 0.5rem;
	}

	.hamburger,
	.hamburger::before,
	.hamburger::after {
		display: block;
		width: 24px;
		height: 2px;
		background: var(--color-text);
		transition: transform 0.3s, opacity 0.3s;
		position: relative;
	}

	.hamburger::before,
	.hamburger::after {
		content: '';
		position: absolute;
	}

	.hamburger::before { top: -7px; }
	.hamburger::after { top: 7px; }

	.hamburger.open {
		background: transparent;
	}

	.hamburger.open::before {
		top: 0;
		transform: rotate(45deg);
	}

	.hamburger.open::after {
		top: 0;
		transform: rotate(-45deg);
	}

	@media (max-width: 768px) {
		.mobile-toggle {
			display: block;
		}

		.nav-links {
			display: none;
			position: absolute;
			top: var(--header-height);
			left: 0;
			right: 0;
			background: var(--color-bg);
			border-bottom: 1px solid var(--color-border);
			flex-direction: column;
			padding: 1.5rem;
			gap: 1rem;
		}

		.nav-links.open {
			display: flex;
		}

		.nav-cta {
			width: 100%;
			text-align: center;
		}
	}
</style>
