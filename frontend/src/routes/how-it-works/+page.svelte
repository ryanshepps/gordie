<script lang="ts">
    import SEOHead from '$lib/components/SEOHead.svelte';
</script>

<SEOHead title="How Gordie works" description="Gordie connects Yahoo Fantasy account data to an AI assistant for fantasy sports analysis." canonical="/how-it-works" />

<section class="page-hero ambient-glow">
    <div class="container content">
        <h1 class="gradient-text">How Gordie works</h1>
        <p>Gordie connects Yahoo Fantasy account data to an AI assistant for fantasy sports analysis.</p>
        <p>The current website has no signup or messaging flow. Follow the open source project for future integration work.</p>
        <a class="btn btn-primary" href="https://github.com/ryanshepps/gordie">View the source code</a>
    </div>
</section>

<style>
    .page-hero {
        padding: 6rem 0;
        min-height: 60vh;
    }

    .content {
        max-width: 760px;
    }

    h1 {
        margin-bottom: 1.5rem;
    }

    p {
        color: var(--color-text-muted);
        font-size: 1.1rem;
        line-height: 1.6;
        margin-bottom: 1.5rem;
    }
</style>
