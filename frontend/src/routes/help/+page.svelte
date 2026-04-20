<script lang="ts">
	let { data } = $props();
</script>

<svelte:head>
	<title>{data.help.title} - Elemes LMS</title>
</svelte:head>

<div class="help-container">
	<header class="help-header">
		<h1>{data.help.title}</h1>
	</header>

	<section class="help-content prose">
		{@html data.help.content}
	</section>
</div>

<style>
	.help-container {
		max-width: 900px;
		margin: 0 auto;
		padding: 2rem 1rem;
	}
	.help-header {
		margin-bottom: 2rem;
		border-bottom: 2px solid var(--color-border);
		padding-bottom: 1rem;
	}
	.help-header h1 {
		font-size: 2.5rem;
		margin: 0;
	}
	.help-content {
		background: var(--color-bg-secondary);
		padding: 2rem;
		border-radius: var(--radius);
		box-shadow: var(--shadow);
	}

	@media (max-width: 768px) {
		.help-header h1 {
			font-size: 1.75rem;
		}
		.help-content {
			padding: 1rem;
		}
	}
</style>
