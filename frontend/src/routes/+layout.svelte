<script>
	import Header from '$lib/components/Header.svelte';
	import Footer from '$lib/components/Footer.svelte';
	import '../app.css';

	const { children } = $props();
</script>

<Header />
<main>{@render children()}</main>
<Footer />

<style>
	main {
		min-height: calc(100vh - var(--header-height));
	}
</style>
