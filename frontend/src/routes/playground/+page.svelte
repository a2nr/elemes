<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { auth } from '$stores/auth';
	import { playgroundStore, type ConsoleLine } from '$stores/playground';
	import { compileCode } from '$services/api';
	import DeployFAB from '$components/DeployFAB.svelte';
	import CircuitEditor from '$components/CircuitEditor.svelte';
	import CodeEditor from '$components/CodeEditor.svelte';
	import FlowchartTab from '../lesson/[slug]/FlowchartTab.svelte';
	import FileTree from './FileTree.svelte';
	import ConsolePanel from './ConsolePanel.svelte';

	type PlaygroundTab = 'velxio' | 'flowchart' | 'circuit' | 'code';

	let activeTab = $state<PlaygroundTab>('velxio');
	let codeEditor = $state<CodeEditor | null>(null);

	// ── File tree (C/Python) ──
	const activeFile = $derived(
		$playgroundStore.files.find((f) => f.id === $playgroundStore.activeFileId) ?? null
	);
	const codeLanguage = $derived(
		activeFile?.name.toLowerCase().endsWith('.py') ? 'python' : 'c'
	);

	function selectCodeLanguage(lang: 'c' | 'python') {
		const ext = lang === 'python' ? '.py' : '.c';
		const file = $playgroundStore.files.find((f) => f.name.toLowerCase().endsWith(ext));
		if (file) {
			playgroundStore.setActiveFile(file.id);
		} else {
			playgroundStore.addFile(lang === 'python' ? 'main.py' : 'main.c');
		}
		activeTab = 'code';
	}

	function consoleLine(type: ConsoleLine['type'], text: string): ConsoleLine {
		return { type, text, timestamp: Date.now() };
	}

	// ── Run (console output/input via /api/compile) ──
	async function runActiveFile() {
		const file = activeFile;
		if (!file || $playgroundStore.running) return;

		const stdin = $playgroundStore.consoleInput;
		playgroundStore.setConsoleInput('');
		playgroundStore.setRunning(true);
		playgroundStore.appendConsole(
			consoleLine('info', `$ run ${file.name} [${codeLanguage}]`)
		);

		try {
			const res = await compileCode({
				code: file.content,
				language: codeLanguage,
				token: auth.token || undefined,
				stdin
			});

			if (res.success) {
				if (res.output) {
					playgroundStore.appendConsole(consoleLine('output', res.output));
				}
				if (res.error) {
					playgroundStore.appendConsole(consoleLine('error', res.error));
				}
				if (!res.output && !res.error) {
					playgroundStore.appendConsole(consoleLine('info', '(selesai, tanpa output)'));
				}
			} else {
				playgroundStore.appendConsole(
					consoleLine('error', res.error || res.output || 'Gagal menjalankan program')
				);
			}
		} catch (err) {
			playgroundStore.appendConsole(
				consoleLine('error', `Error: ${err instanceof Error ? err.message : String(err)}`)
			);
		} finally {
			playgroundStore.setRunning(false);
		}
	}

	// ── Velxio + DeployFAB ──
	let velxioIframe = $state<HTMLIFrameElement | null>(null);
	type DeployFABHandle = { setHex: (hex: string | null) => void };
	let fabComponent = $state<DeployFABHandle | null>(null);

	const velxioSrc = '/velxio/editor?embed=true&desktopLayout=true';

	function handleMessage(e: MessageEvent) {
		if (!e.data?.type) return;
		if (e.data.type === 'velxio:hex_ready') {
			fabComponent?.setHex(e.data.hex);
		}
	}

	function pushSerialToIframe(text: string) {
		if (!velxioIframe?.contentWindow) return;
		velxioIframe.contentWindow.postMessage({
			type: 'elemes:push_serial',
			text,
			boardId: null
		}, window.location.origin);
	}

	function notifySerialStart() {
		velxioIframe?.contentWindow?.postMessage({ type: 'elemes:start_hardware_serial' }, window.location.origin);
	}

	function notifySerialStop() {
		velxioIframe?.contentWindow?.postMessage({ type: 'elemes:stop_hardware_serial' }, window.location.origin);
	}

	// ── Storage keys (flowchart & circuit) ──
	const FLOWCHART_KEY = 'playground_flowchart_draft';
	const CIRCUIT_KEY = 'playground_circuit_draft';

	onMount(() => {
		window.addEventListener('message', handleMessage);
	});

	onDestroy(() => {
		window.removeEventListener('message', handleMessage);
	});
</script>

<svelte:head>
	<title>Developer Playground — Elemes</title>
	<style>
		/* Override root container constrainer — playground is full viewport */
		main.container {
			max-width: none !important;
			padding-inline: 0 !important;
		}
	</style>
</svelte:head>

<div class="playground-page">
	<!-- Tab bar -->
	<div class="pg-tabs">
		<button class="pg-tab" class:active={activeTab === 'velxio'} onclick={() => activeTab = 'velxio'}>
			Arduino
		</button>
		<button class="pg-tab" class:active={activeTab === 'flowchart'} onclick={() => activeTab = 'flowchart'}>
			Flowchart
		</button>
		<button class="pg-tab" class:active={activeTab === 'circuit'} onclick={() => activeTab = 'circuit'}>
			Circuit
		</button>
		<div class="pg-tab-group">
			<button
				class="pg-tab pg-tab-sub"
				class:active={activeTab === 'code' && codeLanguage === 'c'}
				onclick={() => selectCodeLanguage('c')}
			>
				C
			</button>
			<button
				class="pg-tab pg-tab-sub"
				class:active={activeTab === 'code' && codeLanguage === 'python'}
				onclick={() => selectCodeLanguage('python')}
			>
				Python
			</button>
		</div>
	</div>

	<!-- Content area -->
	<div class="pg-content">
		{#if activeTab === 'velxio'}
			<iframe
				bind:this={velxioIframe}
				src={velxioSrc}
				title="Velxio Editor"
				allow="bluetooth; clipboard-read; clipboard-write; fullscreen"
				class="pg-iframe"
				allowfullscreen
			></iframe>
		{:else if activeTab === 'flowchart'}
			<FlowchartTab
				storageKey={FLOWCHART_KEY}
			/>
		{:else if activeTab === 'circuit'}
			<div class="pg-circuit-wrap">
				<CircuitEditor
					storageKey={CIRCUIT_KEY}
				/>
			</div>
		{:else if activeTab === 'code'}
			<div class="pg-code-wrap">
				<FileTree onselect={() => activeTab = 'code'} />

				<div class="pg-code-main">
					<div class="pg-code-toolbar">
						<span class="pg-file-name" title={activeFile?.name}>{activeFile?.name ?? '—'}</span>
						<span class="pg-file-lang">{codeLanguage}</span>
						<div class="pg-toolbar-spacer"></div>
						<button
							class="pg-run-btn"
							onclick={runActiveFile}
							disabled={$playgroundStore.running || !activeFile}
						>
							{#if $playgroundStore.running}
								⏳ Menjalankan…
							{:else}
								▶ Run
							{/if}
						</button>
					</div>

					<div class="pg-editor-holder">
						{#key (activeFile?.id ?? 'none') + '-' + codeLanguage}
							<CodeEditor
								bind:this={codeEditor}
								code={activeFile?.content ?? ''}
								language={codeLanguage}
								storageKey={activeFile ? 'pg_file_' + activeFile.id : undefined}
								onchange={(val) => {
									if (activeFile) playgroundStore.updateFile(activeFile.id, val);
								}}
							/>
						{/key}
					</div>
				</div>
			</div>
		{/if}
	</div>

	<!-- Console (C/Python tab) -->
	{#if activeTab === 'code'}
		<ConsolePanel />
	{/if}

	<!-- DeployFAB only on Velxio tab -->
	{#if activeTab === 'velxio'}
		<DeployFAB
			bind:this={fabComponent}
			{velxioIframe}
			onPushSerial={pushSerialToIframe}
			onSerialStart={notifySerialStart}
			onStopSerial={notifySerialStop}
		/>
	{/if}
</div>

<style>
	.playground-page {
		width: 100%;
		height: 100%;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	/* ── Tab bar ── */
	.pg-tabs {
		display: flex;
		align-items: flex-end;
		gap: 2px;
		padding: 0 8px;
		background: var(--color-bg-secondary);
		border-bottom: 1px solid var(--color-border);
		min-height: 36px;
		flex-shrink: 0;
	}

	.pg-tab {
		padding: 5px 16px;
		border: 1px solid transparent;
		border-bottom: none;
		border-radius: 8px 8px 0 0;
		background: transparent;
		color: var(--color-text-muted);
		font-size: 0.78rem;
		font-weight: 500;
		cursor: pointer;
		white-space: nowrap;
		flex-shrink: 0;
		margin-bottom: -1px;
		z-index: 0;
		transition: background 0.15s, color 0.15s;
	}

	.pg-tab:hover:not(.active) {
		background: var(--color-border);
		color: var(--color-text);
	}

	.pg-tab.active {
		background: var(--color-bg);
		color: var(--color-text);
		font-weight: 600;
		border-color: var(--color-border);
		z-index: 1;
	}

	.pg-tab-group {
		display: flex;
		gap: 0;
		align-items: flex-end;
	}

	.pg-tab-sub {
		padding: 5px 12px;
	}

	/* ── Content area ── */
	.pg-content {
		flex: 1;
		min-height: 0;
		overflow: hidden;
		display: flex;
	}

	.pg-iframe {
		width: 100%;
		flex: 1;
		border: none;
		display: block;
		min-height: 0;
	}

	.pg-circuit-wrap {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
		padding: 8px;
		overflow: hidden;
	}

	/* Override CircuitEditor agar fill flex area */
	.pg-content :global(.circuit-container) {
		flex: 1;
		min-height: 0;
	}

	.pg-content :global(.circuit-wrapper) {
		flex: 1;
		height: auto;
		min-height: 0;
	}

	/* ── Code tab: file tree + editor + console ── */
	.pg-code-wrap {
		flex: 1;
		min-width: 0;
		min-height: 0;
		display: flex;
	}

	.pg-code-main {
		flex: 1;
		min-width: 0;
		min-height: 0;
		display: flex;
		flex-direction: column;
	}

	.pg-code-toolbar {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.35rem 0.75rem;
		background: var(--color-bg-secondary);
		border-bottom: 1px solid var(--color-border);
		flex-shrink: 0;
	}

	.pg-file-name {
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--color-text);
		max-width: 220px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.pg-file-lang {
		font-size: 0.68rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		padding: 0.1rem 0.45rem;
		border-radius: 999px;
		background: var(--color-primary);
		color: #fff;
		flex-shrink: 0;
	}

	.pg-toolbar-spacer {
		flex: 1;
	}

	.pg-run-btn {
		background: var(--color-success, #198754);
		color: #fff;
		border: none;
		padding: 0.35rem 1rem;
		border-radius: 6px;
		font-size: 0.8rem;
		font-weight: 600;
		cursor: pointer;
		flex-shrink: 0;
		transition: opacity 0.15s, transform 0.05s;
	}

	.pg-run-btn:hover:not(:disabled) {
		opacity: 0.9;
	}

	.pg-run-btn:active:not(:disabled) {
		transform: translateY(1px);
	}

	.pg-run-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.pg-editor-holder {
		flex: 1;
		min-height: 0;
		overflow: hidden;
		display: flex;
	}

	.pg-editor-holder > :global(*) {
		flex: 1;
		min-height: 0;
	}

	/* ── FlowchartTab fill ── */
	.pg-content :global(.flowchart-container) {
		flex: 1;
		min-height: 0;
	}

	/* ── Mobile ── */
	@media (max-width: 768px) {
		.playground-page {
			overflow-y: auto;
			height: auto;
			min-height: 100dvh;
		}
		.pg-content {
			min-height: 400px;
		}
		.pg-iframe {
			min-height: 400px;
		}
	}
</style>
