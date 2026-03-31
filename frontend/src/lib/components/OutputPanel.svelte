<script lang="ts">
	interface OutputSection {
		output?: string;
		error?: string;
		loading?: boolean;
		success?: boolean | null;
	}

	interface Props {
		code?: OutputSection;
		circuit?: OutputSection;
		hasCode?: boolean;
		hasCircuit?: boolean;
	}

	let {
		code = { output: '', error: '', loading: false, success: null },
		circuit = { output: '', error: '', loading: false, success: null },
		hasCode = true,
		hasCircuit = false,
	}: Props = $props();

	// Determine overall loading state for header badge
	let anyLoading = $derived(code.loading || circuit.loading);

	// Determine overall success state: null if idle, true if all ran successfully, false if any error
	let overallSuccess = $derived.by(() => {
		const codeRan = code.success !== null && code.success !== undefined;
		const circuitRan = circuit.success !== null && circuit.success !== undefined;
		if (!codeRan && !circuitRan) return null;
		if ((codeRan && code.success === false) || (circuitRan && circuit.success === false)) return false;
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
		<!-- Code output section -->
		{#if hasCode}
		<div class="output-section" class:has-error={!!code.error} class:has-success={code.success === true}>
			<div class="section-label">
				<span class="section-icon">&#x1F4BB;</span> Code
				{#if code.loading}
					<span class="section-badge running">Compiling...</span>
				{:else if code.success === true}
					<span class="section-badge success">OK</span>
				{:else if code.success === false}
					<span class="section-badge error">Error</span>
				{/if}
			</div>
			<pre class="output-body">{#if code.loading}Mengompilasi dan menjalankan kode...{:else if code.error}{code.error}{:else if code.output}{code.output}{:else}<span class="placeholder">Klik "Run" untuk menjalankan kode</span>{/if}</pre>
		</div>
		{/if}

		<!-- Circuit output section -->
		{#if hasCircuit}
		<div class="output-section" class:has-error={!!circuit.error} class:has-success={circuit.success === true}>
			<div class="section-label">
				<span class="section-icon">&#x26A1;</span> Circuit
				{#if circuit.loading}
					<span class="section-badge running">Evaluating...</span>
				{:else if circuit.success === true}
					<span class="section-badge success">OK</span>
				{:else if circuit.success === false}
					<span class="section-badge error">Error</span>
				{/if}
			</div>
			<pre class="output-body">{#if circuit.loading}Mengevaluasi rangkaian...{:else if circuit.error}{circuit.error}{:else if circuit.output}{circuit.output}{:else}<span class="placeholder">Klik "Cek Rangkaian" untuk mengevaluasi</span>{/if}</pre>
		</div>
		{/if}

		<!-- Fallback when neither section has run -->
		{#if !hasCode && !hasCircuit}
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
</style>
