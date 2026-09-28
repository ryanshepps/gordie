<script lang="ts">
    import SEOHead from '$lib/components/SEOHead.svelte';
</script>

<SEOHead title="Fantasy analysis" description="Gordie includes Yahoo Fantasy account access, roster analysis, trade evaluation, and sports statistics tools." canonical="/features" />

<section class="page-hero ambient-glow">
    <div class="container content">
        <h1 class="gradient-text">Fantasy analysis</h1>
        <p>Gordie includes Yahoo Fantasy account access, roster analysis, trade evaluation, and sports statistics tools.</p>
        <p>These capabilities remain in the source code. A user messaging integration is being rebuilt before they are offered through the website.</p>
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
