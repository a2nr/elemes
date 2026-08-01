<script lang="ts">
	import { get } from 'svelte/store';
	import { playgroundStore, type ConsoleLine } from '$stores/playground';

	let outputEl: HTMLDivElement | undefined = $state();

	const consoleHistory = $derived($playgroundStore.consoleHistory);
	const consoleVisible = $derived($playgroundStore.consoleVisible);

	// Auto-scroll ke bawah saat ada output baru
	$effect(() => {
		if (consoleHistory.length > 0 && outputEl) {
			queueMicrotask(() => {
				outputEl!.scrollTop = outputEl!.scrollHeight;
			});
		}
	});

	function sendInput() {
		const text = get(playgroundStore).consoleInput.trim();
		if (!text) return;
		// Tambah ke antrean stdin (bukan hanya history)
		playgroundStore.enqueueStdin(text);
		// Tetap tampilkan di console history sebagai baris input
		const line: ConsoleLine = { type: 'input', text, timestamp: Date.now() };
		playgroundStore.appendConsole(line);
		playgroundStore.setConsoleInput('');
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') sendInput();
	}

	function getLineColor(type: ConsoleLine['type']): string {
		switch (type) {
			case 'input':
				return 'var(--color-primary)';
			case 'output':
				return 'var(--color-text)';
			case 'error':
				return 'var(--color-danger)';
			case 'info':
				return 'var(--color-success)';
			default:
				return 'var(--color-text)';
		}
	}
</script>

<div class="console-panel" class:collapsed={!consoleVisible}>
	<div class="console-header">
		<span class="console-title">Console</span>
		<div class="console-actions">
			{#if $playgroundStore.running}
				<span class="console-running">⏳ Menjalankan…</span>
			{/if}
			<button
				class="console-btn"
				onclick={() => playgroundStore.toggleConsole()}
				title={consoleVisible ? 'Tutup console' : 'Buka console'}
			>
				{#if consoleVisible}⌄{:else}▶{/if}
			</button>
			<button class="console-btn" onclick={() => playgroundStore.clearConsole()} title="Bersihkan console">
				✕
			</button>
		</div>
	</div>

	{#if consoleVisible}
		<div class="console-output" bind:this={outputEl}>
			{#if consoleHistory.length === 0}
				<div class="console-placeholder">
					Klik ▶ Run di editor untuk menjalankan program. Output dan error akan muncul di sini.
				</div>
			{:else}
				{#each consoleHistory as line (line.timestamp + '-' + line.text.length)}
					<div class="console-line" style="color: {getLineColor(line.type)}">
						{#if line.type === 'input'}
							<span class="console-prompt">&gt;</span>
						{/if}
						<span class="console-text">{line.text}</span>
					</div>
				{/each}
			{/if}
		</div>

		<div class="console-input-area">
			<span class="console-ps1">&gt;</span>
			<input
				class="console-input"
				value={$playgroundStore.consoleInput}
				oninput={(e) => playgroundStore.setConsoleInput(e.currentTarget.value)}
				onkeydown={handleKeydown}
				placeholder="Ketik input, enter/Kirim untuk antre, lalu Run…"
				/>
			<button class="console-send" onclick={sendInput}>Kirim</button>
		</div>
	{/if}
</div>

<style>
	.console-panel {
		display: flex;
		flex-direction: column;
		height: 240px;
		flex-shrink: 0;
		border-top: 1px solid var(--color-border);
		background: var(--color-bg);
		overflow: hidden;
		transition: height 0.2s;
	}

	.console-panel.collapsed {
		height: 38px;
	}

	.console-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.45rem 0.75rem;
		border-bottom: 1px solid var(--color-border);
		background: var(--color-bg-secondary);
		font-size: 0.8rem;
		flex-shrink: 0;
	}

	.console-title {
		font-weight: 600;
		color: var(--color-text);
	}

	.console-actions {
		display: flex;
		align-items: center;
		gap: 0.3rem;
	}

	.console-running {
		font-size: 0.7rem;
		color: var(--color-warning);
		font-weight: 600;
	}

	.console-btn {
		background: none;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		font-size: 0.9rem;
		padding: 0.15rem 0.3rem;
		border-radius: 4px;
		transition: background 0.15s, color 0.15s;
	}

	.console-btn:hover {
		background: var(--color-bg);
		color: var(--color-primary);
	}

	.console-output {
		flex: 1;
		padding: 0.5rem 0.75rem;
		overflow-y: auto;
		font-family: var(--font-mono);
		font-size: 0.78rem;
		min-height: 0;
	}

	.console-placeholder {
		color: var(--color-text-muted);
		font-style: italic;
		margin-top: 0.75rem;
	}

	.console-line {
		margin-bottom: 0.15rem;
		white-space: pre-wrap;
		word-break: break-word;
		line-height: 1.45;
	}

	.console-prompt {
		color: var(--color-primary);
		font-weight: 700;
		margin-right: 0.35rem;
	}

	.console-input-area {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.4rem 0.75rem;
		border-top: 1px solid var(--color-border);
		background: var(--color-bg-secondary);
		flex-shrink: 0;
	}

	.console-ps1 {
		color: var(--color-primary);
		font-family: var(--font-mono);
		font-weight: 700;
		font-size: 0.85rem;
	}

	.console-input {
		flex: 1;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		color: var(--color-text);
		padding: 0.35rem 0.55rem;
		font-family: var(--font-mono);
		font-size: 0.8rem;
		border-radius: 4px;
		min-width: 0;
	}

	.console-input:focus {
		outline: none;
		border-color: var(--color-primary);
	}

	.console-send {
		background: var(--color-primary);
		color: #fff;
		border: none;
		padding: 0.35rem 0.75rem;
		border-radius: 4px;
		cursor: pointer;
		font-size: 0.78rem;
		font-weight: 500;
		transition: opacity 0.15s;
	}

	.console-send:hover {
		opacity: 0.85;
	}

	::-webkit-scrollbar {
		width: 6px;
	}

	::-webkit-scrollbar-thumb {
		background: var(--color-border);
		border-radius: 3px;
	}
</style>
