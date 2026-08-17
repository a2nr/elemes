<script lang="ts">
	import { renderMath } from '$lib/actions/renderMath';

	export let data: {
		doc: import('$types/docs').DocContent
	};
</script>

<svelte:head>
	<title>{data.doc.title} - Dokumentasi Elemes LMS</title>
</svelte:head>

<div class="docs-detail">
	<article class="prose" use:renderMath>
		<h1>{data.doc.title}</h1>
		{@html data.doc.html}
	</article>
</div>

<style>
	.docs-detail {
		max-width: 800px;
		margin: 0 auto;
		padding: 2rem 1rem;
	}

	.docs-detail h1 {
		font-size: 2rem;
		margin-bottom: 1.5rem;
		border-bottom: 1px solid var(--color-border);
		padding-bottom: 0.5rem;
	}

	.docs-detail :global(.prose pre) {
		overflow-x: auto;
	}

	@media (max-width: 768px) {
		.docs-detail {
			padding: 1rem;
		}
	}
</style>
