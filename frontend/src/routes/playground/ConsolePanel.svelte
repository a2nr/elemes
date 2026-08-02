<script lang="ts">
	import { get } from 'svelte/store';
	import { playgroundStore, type ConsoleLine } from '$stores/playground';

	interface Props {
		/** Kirim input ke sesi aktif; throw bila gagal (input tidak di-commit). */
		onSendInput?: (text: string) => Promise<void>;
		/** Stop sesi aktif (DELETE). */
		onStop?: () => Promise<void>;
	}

	let { onSendInput, onStop }: Props = $props();

	let outputEl: HTMLDivElement | undefined = $state();
	let sending = $state(false);

	const consoleHistory = $derived($playgroundStore.consoleHistory);
	const consoleVisible = $derived($playgroundStore.consoleVisible);
	const runStatus = $derived($playgroundStore.runStatus);
	const isActive = $derived(
		runStatus === 'queued' || runStatus === 'compiling' || runStatus === 'running'
	);
	const isStopping = $derived(runStatus === 'stopping');

	// Auto-scroll ke bawah saat ada output baru
	$effect(() => {
		if (consoleHistory.length > 0 && outputEl) {
			queueMicrotask(() => {
				outputEl!.scrollTop = outputEl!.scrollHeight;
			});
		}
	});

	async function sendInput() {
		if (sending) return;
		const text = get(playgroundStore).consoleInput;
		if (!text) return;

		if (!isActive || !onSendInput) {
			// Mode antrean (idle/terminal): simpan ke stdinQueue utk Run berikutnya
			playgroundStore.enqueueStdin(text);
			const line: ConsoleLine = { type: 'input', text: text.trim(), timestamp: Date.now() };
			playgroundStore.appendConsole(line);
			playgroundStore.setConsoleInput('');
			return;
		}

		// Mode aktif: kirim ke sesi — history hanya setelah POST berhasil
		sending = true;
		try {
			await onSendInput(text);
			const line: ConsoleLine = { type: 'input', text, timestamp: Date.now() };
			playgroundStore.appendConsole(line);
			playgroundStore.setConsoleInput('');
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			playgroundStore.appendConsole(consoleErrorLine(`Input gagal dikirim: ${msg}`));
		} finally {
			sending = false;
		}
	}

	function consoleErrorLine(text: string): ConsoleLine {
		return { type: 'error', text, timestamp: Date.now() };
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			void sendInput();
		}
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

	function statusLabel(): string | null {
		if (isStopping) return '⏹ Menghentikan…';
		if (isActive) return '⏳ Menjalankan…';
		return null;
	}
</script>

<div class="console-panel" class:collapsed={!consoleVisible}>
	<div class="console-header">
		<span class="console-title">Console</span>
		<div class="console-actions">
			{#if statusLabel()}
				<span class="console-running">{statusLabel()}</span>
			{/if}
			{#if isActive && !isStopping}
				<button
					class="console-btn console-stop"
					onclick={() => void onStop?.()}
					title="Hentikan program"
				>
					⏹ Stop
				</button>
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
				placeholder={
					isActive
						? 'Ketik jawaban, Enter untuk mengirim…'
						: 'Ketik input, Enter untuk mengantre, lalu Run…'
				}
			/>
			{#if isActive && !isStopping}
				<button class="console-send" onclick={() => void sendInput()} disabled={sending}>
					{sending ? '…' : 'Kirim'}
				</button>
			{:else}
				<button
					class="console-send"
					onclick={() => void sendInput()}
					disabled={isStopping}
					title="Antrekan sebagai input untuk Run berikutnya"
				>
					Antrekan
				</button>
			{/if}
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

	.console-stop {
		color: var(--color-danger);
		font-size: 0.75rem;
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

	.console-send:hover:not(:disabled) {
		opacity: 0.85;
	}

	.console-send:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.console-panel ::-webkit-scrollbar {
		width: 6px;
	}

	.console-panel ::-webkit-scrollbar-thumb {
		background: var(--color-border);
		border-radius: 3px;
	}
</style>
