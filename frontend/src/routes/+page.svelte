<script lang="ts">
    import SEOHead from '$lib/components/SEOHead.svelte';
</script>

<SEOHead title="Gordie" description="Gordie is an open source fantasy sports assistant built around Yahoo Fantasy data." canonical="/" />

<section class="page-hero ambient-glow">
    <div class="container content">
        <h1 class="gradient-text">Gordie</h1>
        <p>Gordie is an open source fantasy sports assistant built around Yahoo Fantasy data.</p>
        <p>The user messaging integration is being rebuilt. Signup and automated updates are unavailable while that work is in progress.</p>
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
