<script lang="ts">
	interface Props {
		output?: string;
		error?: string;
		loading?: boolean;
		success?: boolean | null;
	}

	let { output = '', error = '', loading = false, success = null }: Props = $props();
</script>

<div class="output-panel" class:has-error={!!error} class:has-success={success === true}>
	<div class="output-header">
		<span class="output-title">Output</span>
		{#if loading}
			<span class="status-badge running">Compiling...</span>
		{:else if success === true}
			<span class="status-badge success">Berhasil</span>
		{:else if success === false}
			<span class="status-badge error">Error</span>
		{/if}
	</div>

	<pre class="output-body">{#if loading}Mengompilasi dan menjalankan kode...{:else if error}{error}{:else if output}{output}{:else}<span class="placeholder">Klik "Run" untuk menjalankan kode</span>{/if}</pre>
</div>

<style>
	.output-panel {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
		font-family: var(--font-mono);
	}
	.output-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 0.75rem;
		background: var(--color-bg-secondary);
		border-bottom: 1px solid var(--color-border);
		font-size: 0.8rem;
		font-family: system-ui, sans-serif;
	}
	.output-title {
		font-weight: 600;
	}
	.status-badge {
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
		font-size: 0.7rem;
		font-weight: 600;
	}
	.status-badge.running {
		background: var(--color-warning);
		color: #000;
	}
	.status-badge.success {
		background: var(--color-success);
		color: #fff;
	}
	.status-badge.error {
		background: var(--color-danger);
		color: #fff;
	}
	.output-body {
		padding: 0.75rem;
		margin: 0;
		min-height: 80px;
		max-height: 300px;
		overflow: auto;
		font-size: 0.85rem;
		white-space: pre-wrap;
		word-break: break-word;
		background: var(--color-bg);
		color: var(--color-text);
	}
	.has-error .output-body {
		color: var(--color-danger);
	}
	.has-success .output-body {
		color: var(--color-success);
	}
	.placeholder {
		color: var(--color-text-muted);
		font-style: italic;
	}
</style>
