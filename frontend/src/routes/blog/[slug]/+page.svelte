<script lang="ts">
	import SEOHead from '$lib/components/SEOHead.svelte';
	import StructuredData from '$lib/components/StructuredData.svelte';
	import { formatDate } from '$lib/utils/blog';
	import type { PageData } from './$types';

	const { data }: { data: PageData } = $props();
	const post = $derived(data.post);

	const blogPostingData = $derived({
		'@context': 'https://schema.org',
		'@type': 'BlogPosting',
		headline: post.title,
		description: post.description,
		datePublished: post.date,
		author: {
			'@type': 'Person',
			name: post.author
		},
		publisher: {
			'@type': 'Organization',
			name: 'Gordie'
		}
	});
</script>

<SEOHead
	title={post.title}
	description={post.description}
	canonical="/blog/{post.slug}"
	ogType="article"
/>
<StructuredData data={blogPostingData} />

<article class="blog-post">
	<div class="container post-container">
		<header class="post-header">
			<span class="post-category">{post.category}</span>
			<h1>{post.title}</h1>
			<div class="post-meta">
				<span>{post.author}</span>
				<span class="meta-sep" aria-hidden="true">&middot;</span>
				<time datetime={post.date}>{formatDate(post.date)}</time>
			</div>
			{#if post.tags.length > 0}
				<div class="post-tags">
					{#each post.tags as tag}
						<span class="tag">{tag}</span>
					{/each}
				</div>
			{/if}
		</header>

		<div class="post-content prose">
			<post.content />
		</div>

		<footer class="post-footer">
			<a href="/blog">&larr; Back to all posts</a>
		</footer>
	</div>
</article>

<style>
	.post-container {
		max-width: 720px;
	}

	.post-header {
		padding: 4rem 0 2rem;
		border-bottom: 1px solid var(--color-border);
		margin-bottom: 2rem;
	}

	.post-category {
		display: inline-block;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--color-accent);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		margin-bottom: 0.75rem;
	}

	.post-header h1 {
		font-family: var(--font-sans);
		text-transform: none;
		letter-spacing: normal;
		font-size: 2.25rem;
		margin-bottom: 1rem;
	}

	.post-meta {
		color: var(--color-text-muted);
		font-size: 0.95rem;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.post-tags {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-top: 1rem;
	}

	.tag {
		font-size: 0.8rem;
		padding: 0.2rem 0.6rem;
		background: var(--color-bg-secondary);
		border: 1px solid var(--color-border);
		border-radius: 0.25rem;
		color: var(--color-text-muted);
	}

	.post-content {
		padding-bottom: 3rem;
	}

	/* Prose styles for markdown content */
	.prose :global(h2) {
		font-family: var(--font-sans);
		text-transform: none;
		letter-spacing: normal;
		font-size: 1.5rem;
		margin-top: 2rem;
		margin-bottom: 0.75rem;
	}

	.prose :global(h3) {
		font-family: var(--font-sans);
		text-transform: none;
		letter-spacing: normal;
		font-size: 1.25rem;
		margin-top: 1.5rem;
		margin-bottom: 0.5rem;
	}

	.prose :global(p) {
		color: var(--color-text-muted);
		margin-bottom: 1rem;
		line-height: 1.8;
	}

	.prose :global(ul),
	.prose :global(ol) {
		color: var(--color-text-muted);
		margin-bottom: 1rem;
		padding-left: 1.5rem;
	}

	.prose :global(li) {
		margin-bottom: 0.5rem;
	}

	.prose :global(strong) {
		color: var(--color-text);
	}

	.prose :global(code) {
		background: var(--color-bg-secondary);
		padding: 0.15rem 0.4rem;
		border-radius: 0.25rem;
		font-family: var(--font-mono);
		font-size: 0.9rem;
	}

	.prose :global(blockquote) {
		border-left: 3px solid var(--color-primary);
		padding-left: 1rem;
		margin: 1.5rem 0;
		color: var(--color-text-muted);
		font-style: italic;
	}

	.post-footer {
		border-top: 1px solid var(--color-border);
		padding-top: 2rem;
	}

	.post-footer a {
		color: var(--color-text-muted);
		font-size: 0.95rem;
	}

	.post-footer a:hover {
		color: var(--color-primary);
	}
</style>
