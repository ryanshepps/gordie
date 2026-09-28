<script lang="ts">
    import SEOHead from '$lib/components/SEOHead.svelte';
</script>

<SEOHead title="Availability" description="Hosted signup and billing are unavailable while Gordie’s messaging integration is being rebuilt." canonical="/pricing" />

<section class="page-hero ambient-glow">
    <div class="container content">
        <h1 class="gradient-text">Availability</h1>
        <p>Hosted signup and billing are unavailable while Gordie’s messaging integration is being rebuilt.</p>
        <p>The open source code remains available. No plan can be purchased through this website right now.</p>
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
