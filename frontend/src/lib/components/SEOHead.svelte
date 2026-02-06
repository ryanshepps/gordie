<script lang="ts">
	interface Props {
		title: string;
		description: string;
		canonical?: string;
		ogImage?: string;
		ogType?: string;
		noindex?: boolean;
	}

	const {
		title,
		description,
		canonical = '',
		ogImage = '/og-image.jpg',
		ogType = 'website',
		noindex = false
	}: Props = $props();

	const siteUrl = 'https://gordie.lastingsoftware.ca';
	const fullTitle = $derived(`Gordie — ${title}`);
	const canonicalUrl = $derived(canonical ? `${siteUrl}${canonical}` : '');
</script>

<svelte:head>
	<title>{fullTitle}</title>
	<meta name="description" content={description} />
	{#if noindex}
		<meta name="robots" content="noindex, nofollow" />
	{/if}
	{#if canonicalUrl}
		<link rel="canonical" href={canonicalUrl} />
	{/if}

	<!-- Open Graph -->
	<meta property="og:title" content={fullTitle} />
	<meta property="og:description" content={description} />
	<meta property="og:type" content={ogType} />
	{#if canonicalUrl}
		<meta property="og:url" content={canonicalUrl} />
	{/if}
	<meta property="og:image" content="{siteUrl}{ogImage}" />
	<meta property="og:site_name" content="Gordie" />

	<!-- Twitter -->
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:title" content={fullTitle} />
	<meta name="twitter:description" content={description} />
	<meta name="twitter:image" content="{siteUrl}{ogImage}" />
</svelte:head>
