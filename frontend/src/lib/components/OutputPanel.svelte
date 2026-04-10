<script lang="ts">
	export interface OutputSection {
		output?: string;
		error?: string;
		loading?: boolean;
		success?: boolean | null;
		debug?: string[];
	}

	export interface OutputEntry {
		key: string;
		label: string;
		icon: string;
		data: OutputSection;
		placeholder: string;
		loadingText: string;
	}

	interface Props {
		sections?: OutputEntry[];
	}

	let { sections = [] }: Props = $props();

	let showDebug = $state<Record<string, boolean>>({});

	let anyLoading = $derived(sections.some(s => s.data.loading));

	let overallSuccess = $derived.by(() => {
		const ran = sections.filter(s => s.data.success !== null && s.data.success !== undefined);
		if (ran.length === 0) return null;
		if (ran.some(s => s.data.success === false)) return false;
		return true;
	});
</script>

<div class="output-panel">
	<div class="output-header">
		<span class="output-title">Output</span>
		{#if anyLoading}
			<span class="status-badge running">Compiling...</span>
		{:else if overallSuccess === true}
			<span class="status-badge success">Berhasil</span>
		{:else if overallSuccess === false}
			<span class="status-badge error">Error</span>
		{/if}
	</div>

	<div class="output-sections">
		{#each sections as sec (sec.key)}
		<div class="output-section" class:has-error={!!sec.data.error} class:has-success={sec.data.success === true}>
			<div class="section-label">
				<span class="section-icon">{sec.icon}</span> {sec.label}
				{#if sec.data.loading}
					<span class="section-badge running">{sec.loadingText}</span>
				{:else if sec.data.success === true}
					<span class="section-badge success">OK</span>
				{:else if sec.data.success === false}
					<span class="section-badge error">Error</span>
				{/if}
				{#if sec.data.debug && sec.data.debug.length > 0}
					<label class="debug-toggle">
						<input type="checkbox" bind:checked={showDebug[sec.key]} /> Debug
					</label>
				{/if}
			</div>
			<pre class="output-body">{#if sec.data.loading}{sec.loadingText}{:else if sec.data.error}{sec.data.error}{:else if sec.data.output}{sec.data.output}{:else}<span class="placeholder">{sec.placeholder}</span>{/if}{#if sec.data.debug && showDebug[sec.key]}

── Debug ──
{sec.data.debug.join('\n')}{/if}</pre>
		</div>
		{/each}

		{#if sections.length === 0}
		<pre class="output-body"><span class="placeholder">Tidak ada output</span></pre>
		{/if}
	</div>
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
	.status-badge, .section-badge {
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
		font-size: 0.65rem;
		font-weight: 600;
	}
	.status-badge.running, .section-badge.running {
		background: var(--color-warning);
		color: #000;
	}
	.status-badge.success, .section-badge.success {
		background: var(--color-success);
		color: #fff;
	}
	.status-badge.error, .section-badge.error {
		background: var(--color-danger);
		color: #fff;
	}

	/* ── Output sections ───────────────────────────────── */
	.output-sections {
		display: flex;
		flex-direction: column;
	}
	.output-section {
		border-bottom: 1px solid var(--color-border);
	}
	.output-section:last-child {
		border-bottom: none;
	}
	.section-label {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.35rem 0.75rem;
		background: var(--color-bg-secondary);
		font-size: 0.75rem;
		font-weight: 600;
		font-family: system-ui, sans-serif;
		color: var(--color-text-muted);
		border-bottom: 1px solid var(--color-border);
	}
	.section-icon {
		font-size: 0.85rem;
	}
	.output-body {
		padding: 0.75rem;
		margin: 0;
		min-height: 60px;
		max-height: 200px;
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
	.debug-toggle {
		margin-left: auto;
		display: flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 0.7rem;
		font-weight: normal;
		cursor: pointer;
	}
</style>
