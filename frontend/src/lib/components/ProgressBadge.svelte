<script lang="ts">
	let { completed = false }: { completed: boolean } = $props();
</script>

{#if completed}
	<span class="badge done" title="Selesai">&#10003; Selesai</span>
{:else}
	<span class="badge pending">Belum selesai</span>
{/if}

<style>
	.badge {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.2rem 0.6rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: 600;
	}
	.done {
		background: var(--color-success);
		color: #fff;
	}
	.pending {
		background: var(--color-bg-secondary);
		color: var(--color-text-muted);
		border: 1px solid var(--color-border);
	}
</style>
