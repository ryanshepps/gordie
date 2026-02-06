<script lang="ts">
	import SEOHead from '$lib/components/SEOHead.svelte';
	import { formatDate } from '$lib/utils/blog';
	import type { PageData } from './$types';

	const { data }: { data: PageData } = $props();
</script>

<SEOHead
	title="Blog"
	description="Fantasy sports tips, waiver wire advice, trade analysis, and strategy guides from Gordie — your AI fantasy sports assistant."
	canonical="/blog"
/>

<section class="page-hero ambient-glow">
	<div class="container">
		<h1>Blog</h1>
		<p class="page-sub">Fantasy sports insights, strategy, and analysis.</p>
	</div>
</section>

<section class="blog-list">
	<div class="container">
		{#if data.posts.length === 0}
			<p class="no-posts">No posts yet. Check back soon!</p>
		{:else}
			<div class="posts-grid">
				{#each data.posts as post}
					<article class="post-card card card-animate">
						<a href="/blog/{post.slug}" class="post-link">
							<span class="post-category">{post.category}</span>
							<h2>{post.title}</h2>
							<p class="post-description">{post.description}</p>
							<time class="post-date" datetime={post.date}>{formatDate(post.date)}</time>
						</a>
					</article>
				{/each}
			</div>
		{/if}
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
	}

	.blog-list {
		padding: 2rem 0 4rem;
	}

	.no-posts {
		color: var(--color-text-muted);
		font-size: 1.1rem;
	}

	.posts-grid {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		max-width: 720px;
	}

	.post-link {
		display: block;
		padding: 1.5rem;
		color: inherit;
	}

	.post-link:hover {
		text-decoration: none;
	}

	.post-category {
		display: inline-block;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--color-accent);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		margin-bottom: 0.5rem;
	}

	.post-card h2 {
		font-family: var(--font-sans);
		text-transform: none;
		letter-spacing: normal;
		font-size: 1.25rem;
		margin-bottom: 0.5rem;
	}

	.post-description {
		color: var(--color-text-muted);
		font-size: 0.95rem;
		margin-bottom: 0.75rem;
	}

	.post-date {
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}
</style>
