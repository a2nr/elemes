<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { auth } from '$stores/auth';
	import { playgroundStore, type ConsoleLine } from '$stores/playground';
	import {
		startCompileSession,
		readCompileSession,
		sendCompileInput,
		stopCompileSession
	} from '$services/api';
	import type { InteractiveRunStatus } from '$types/compiler';
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
	const codeLanguage = $derived<'c' | 'python'>(
		activeFile?.name.toLowerCase().endsWith('.py') ? 'python' : 'c'
	);

	// ── Interactive session state (lokal; lifecycle di store) ──
	let pollTimer: ReturnType<typeof setTimeout> | null = null;
	let generation = 0;
	const TERMINAL_STATUSES = new Set<InteractiveRunStatus>([
		'exited',
		'error',
		'stopped',
		'expired'
	]);

	function consoleLine(type: ConsoleLine['type'], text: string): ConsoleLine {
		return { type, text, timestamp: Date.now() };
	}

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

	// ── Session lifecycle ─────────────────────────────────────────────

	function clearPollTimer() {
		if (pollTimer) {
			clearTimeout(pollTimer);
			pollTimer = null;
		}
	}

	function schedulePoll(delayMs: number) {
		clearPollTimer();
		pollTimer = setTimeout(() => void pollOnce(), delayMs);
	}

	function projectFiles(): { files: { name: string; content: string }[]; active_file: string } {
		const lang = codeLanguage;
		const visible = lang === 'python' ? /\.py$/i : /\.(c|h)$/i;
		const files = $playgroundStore.files
			.filter((f) => visible.test(f.name))
			.map((f) => ({ name: f.name, content: f.content }));
		const activeName = activeFile?.name ?? files[0]?.name ?? '';
		return { files, active_file: activeName };
	}

	async function startRun() {
		const s = $playgroundStore;
		// Abaikan bila masih ada sesi berjalan/berhenti
		if (s.runStatus !== 'idle' && !TERMINAL_STATUSES.has(s.runStatus as InteractiveRunStatus)) {
			return;
		}
		const { files, active_file } = projectFiles();
		if (files.length === 0 || !active_file) return;

		// Konsumsi stdin yang diantrekan (prefilled) utk Run ini
		const stdin = playgroundStore.consumeStdin();
		const lang = codeLanguage;
		playgroundStore.appendConsole(
			consoleLine('info', `$ run project [${lang}]${stdin ? ' (dengan stdin antrean)' : ''}`)
		);

		generation += 1;
		const myGen = generation;
		clearPollTimer();

		try {
			const res = await startCompileSession({
				language: lang,
				files,
				active_file,
				stdin: stdin || undefined,
				token: auth.token || undefined
			});
			if (myGen !== generation) return; // sesi baru / unmount
			if (!res.session_id) {
				playgroundStore.appendConsole(
					consoleLine('error', res.error || 'Gagal memulai sesi program')
				);
				playgroundStore.resetRunSession();
				return;
			}
			playgroundStore.startRunSession(res.session_id, res.status);
			handlePollResponse(res);
		} catch (err) {
			if (myGen !== generation) return;
			playgroundStore.appendConsole(
				consoleLine('error', `Error: ${err instanceof Error ? err.message : String(err)}`)
			);
			playgroundStore.resetRunSession();
		}
	}

	async function pollOnce() {
		const s = $playgroundStore;
		const sid = s.runSessionId;
		if (!sid || TERMINAL_STATUSES.has(s.runStatus as InteractiveRunStatus)) return;

		const myGen = generation;
		try {
			const res = await readCompileSession(sid, s.outputCursor);
			if (myGen !== generation) return;
			handlePollResponse(res);
		} catch (err) {
			if (myGen !== generation) return;
			// Network hiccup — coba lagi dengan delay lebih panjang, jangan mati diam-diam
			schedulePoll(1000);
		}
	}

	function handlePollResponse(res: {
		status: InteractiveRunStatus;
		output: string;
		cursor: number;
		truncated?: boolean;
		exit_code?: number | null;
		error?: string | null;
	}) {
		const s = $playgroundStore;
		if (res.output) {
			playgroundStore.appendConsole(consoleLine('output', res.output));
		}
		if (res.truncated) {
			playgroundStore.appendConsole(
				consoleLine('info', '(⚠ output dipotong — batas 256 KiB)')
			);
		}
		playgroundStore.advanceOutputCursor(res.cursor);

		if (TERMINAL_STATUSES.has(res.status)) {
			// Terminal — tampilkan sisa error bila ada
			if (res.error) {
				playgroundStore.appendConsole(consoleLine('error', res.error));
			} else if (res.exit_code != null && res.exit_code !== 0) {
				playgroundStore.appendConsole(
					consoleLine('error', `(program keluar dengan kode ${res.exit_code})`)
				);
			} else if (res.status === 'exited' && !res.output) {
				playgroundStore.appendConsole(consoleLine('info', '(selesai, tanpa output)'));
			}
			playgroundStore.finishRun(res.status, res.error ?? null);
			// Terminal — release session di worker (best effort)
			const terminalSid = $playgroundStore.runSessionId;
			if (terminalSid) void stopCompileSession(terminalSid);
			return;
		}

		playgroundStore.updateRunStatus(res.status);

		// Polling adaptif: cepat di awal/berubah, melambat setelah stabil
		const changed = res.status === 'queued' || res.status === 'compiling';
		schedulePoll(changed ? 250 : 750);
	}

	async function sendInputToSession(text: string) {
		const s = $playgroundStore;
		if (!s.runSessionId || s.runStatus !== 'running') {
			// Jatuh ke mode antrean — ConsolePanel menangani sendiri saat idle;
			// di sini hanya mencegah kirim ke sesi yang tidak aktif.
			throw new Error('tidak ada sesi aktif');
		}
		await sendCompileInput(s.runSessionId, text);
	}

	async function stopRun() {
		const sid = $playgroundStore.runSessionId;
		if (!sid) return;
		clearPollTimer();
		playgroundStore.updateRunStatus('stopping');
		try {
			await stopCompileSession(sid);
		} catch {
			// best effort — sesi worker akan di-sweep sendiri
		}
		const s = $playgroundStore;
		if (s.runSessionId === sid) {
			playgroundStore.finishRun('stopped', 'program dihentikan oleh pengguna');
			playgroundStore.resetRunSession();
		}
	}

	function switchTab(tab: PlaygroundTab) {
		if (tab !== 'code' && $playgroundStore.runStatus !== 'idle') {
			// Stop sesi aktif saat pindah tab
			void stopRun();
		}
		activeTab = tab;
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
		generation += 1; // invalidasi polling yang sedang berjalan
		clearPollTimer();
		const sid = $playgroundStore.runSessionId;
		if (sid) {
			// Best-effort cleanup sesi (keepalive agar tak ter-blokir navigasi)
			void stopCompileSession(sid);
			playgroundStore.resetRunSession();
		}
	});
</script>

<svelte:head>
	<title>Developer Playground — Elemes</title>
	<style>
		/* Override root container constrainer — playground is full viewport.
		   main.container default-nya display:block + height auto, jadi anak
		   .playground-page{height:100%} cuma ngisi tinggi intrinsic-nya.
		   Jadikan flex-column agar playground memenuhi ruang sisa setelah navbar. */
		main.container {
			display: flex;
			flex-direction: column;
			max-width: none !important;
			padding-inline: 0 !important;
			min-height: 0;
		}
	</style>
</svelte:head>

<div class="playground-page">
	<!-- Tab bar -->
	<div class="pg-tabs">
		<button class="pg-tab" class:active={activeTab === 'velxio'} onclick={() => switchTab('velxio')}>
			Arduino
		</button>
		<button class="pg-tab" class:active={activeTab === 'flowchart'} onclick={() => switchTab('flowchart')}>
			Flowchart
		</button>
		<button class="pg-tab" class:active={activeTab === 'circuit'} onclick={() => switchTab('circuit')}>
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
				<!-- File tree shell: tree dilepas dari DOM saat collapsed agar flexbox menghitung ulang -->
				<div
					class="pg-file-tree-shell"
					class:collapsed={!$playgroundStore.fileTreeVisible}
				>
					{#if $playgroundStore.fileTreeVisible}
						<FileTree language={codeLanguage} onselect={() => activeTab = 'code'} />
					{/if}
					<button
						class="pg-file-tree-handle"
						aria-expanded={$playgroundStore.fileTreeVisible}
						aria-label={$playgroundStore.fileTreeVisible ? 'Sembunyikan file' : 'Tampilkan file'}
						title={$playgroundStore.fileTreeVisible ? 'Sembunyikan file' : 'Tampilkan file'}
						onclick={() => playgroundStore.toggleFileTree()}
					>
						{#if $playgroundStore.fileTreeVisible}⟨{:else}⟩{/if}
					</button>
				</div>

				<div class="pg-code-main">
					<div class="pg-code-toolbar">
						<span class="pg-file-name" title={activeFile?.name}>{activeFile?.name ?? '—'}</span>
						<span class="pg-file-lang">{codeLanguage}</span>
						<div class="pg-toolbar-spacer"></div>
						<button
							class="pg-run-btn"
							onclick={() => void startRun()}
							disabled={($playgroundStore.runStatus !== 'idle' &&
								!['exited', 'error', 'stopped', 'expired'].includes($playgroundStore.runStatus)) ||
								!activeFile}
						>
							{#if $playgroundStore.runStatus === 'stopping'}
								⏹ Menghentikan…
							{:else if ['queued', 'compiling', 'running'].includes($playgroundStore.runStatus)}
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
		<ConsolePanel
			onSendInput={sendInputToSession}
			onStop={stopRun}
		/>
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
		flex: 1;
		min-height: 0;
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
		flex-direction: column;
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

	/* Override CircuitEditor agar fill ruang kosong di desktop */
	.pg-content :global(.circuit-container) {
		flex: 1;
		min-height: 0;
		height: 100%;
	}

	.pg-content :global(.circuit-wrapper) {
		flex: 1 1 auto;
		height: 100%;
		min-height: 0;
	}

	/* ── Code tab: file tree + editor + console ── */
	.pg-code-wrap {
		flex: 1;
		min-width: 0;
		min-height: 0;
		display: flex;
	}

	.pg-file-tree-shell {
		display: flex;
		flex-shrink: 0;
		min-height: 0;
		width: 230px;
		transition: width 0.18s ease;
	}

	.pg-file-tree-shell > :global(.file-tree) {
		flex: 1;
		min-width: 0;
	}

	.pg-file-tree-shell.collapsed {
		width: 26px;
	}

	.pg-file-tree-handle {
		flex-shrink: 0;
		width: 26px;
		background: var(--color-bg-secondary);
		border: none;
		border-left: 1px solid var(--color-border);
		color: var(--color-text-muted);
		cursor: pointer;
		font-size: 0.9rem;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		transition: background 0.15s, color 0.15s;
	}

	.pg-file-tree-handle:hover {
		background: var(--color-bg);
		color: var(--color-primary);
	}

	.pg-file-tree-handle:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: -2px;
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
		height: 100%;
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
		.pg-file-tree-shell {
			width: 180px;
		}
	}
</style>
