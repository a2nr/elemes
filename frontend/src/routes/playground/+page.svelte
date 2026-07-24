<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import DeployFAB from '$components/DeployFAB.svelte';
	import CircuitEditor from '$components/CircuitEditor.svelte';
	import CodeEditor from '$components/CodeEditor.svelte';
	import FlowchartTab from '../lesson/[slug]/FlowchartTab.svelte';

	type PlaygroundTab = 'velxio' | 'flowchart' | 'circuit' | 'code';

	let activeTab = $state<PlaygroundTab>('velxio');
	let codeLanguage = $state<'c' | 'python'>('c');
	let codeEditor = $state<CodeEditor | null>(null);
	let currentCode = $state('');

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

	// ── Storage keys ──
	const FLOWCHART_KEY = 'playground_flowchart_draft';
	const CIRCUIT_KEY = 'playground_circuit_draft';
	const CODE_C_KEY = 'playground_code_c_draft';
	const CODE_PY_KEY = 'playground_code_python_draft';

	let codeStorageKey = $derived(codeLanguage === 'python' ? CODE_PY_KEY : CODE_C_KEY);

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
			<button class="pg-tab pg-tab-sub" class:active={activeTab === 'code' && codeLanguage === 'c'} onclick={() => { activeTab = 'code'; codeLanguage = 'c'; }}>
				C
			</button>
			<button class="pg-tab pg-tab-sub" class:active={activeTab === 'code' && codeLanguage === 'python'} onclick={() => { activeTab = 'code'; codeLanguage = 'python'; }}>
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
				{#key codeLanguage}
				<CodeEditor
					bind:this={codeEditor}
					code={currentCode}
					language={codeLanguage}
					storageKey={codeStorageKey}
					onchange={(val) => currentCode = val}
				/>
				{/key}
			</div>
		{/if}
	</div>

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
		height: 100dvh;
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

	.pg-code-wrap {
		width: 100%;
		height: 100%;
		overflow: hidden;
		display: flex;
		flex-direction: column;
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
