<script lang="ts">
	type TabType = 'info' | 'exercise' | 'editor' | 'circuit' | 'output' | 'velxio';

	interface Props {
		isMobile: boolean;
		mobileMode: 'hidden' | 'half' | 'full';
		activeTab: TabType;
		currentLanguage: string;
		hasInfo: boolean;
		hasExercise: boolean;
		activeTabs: string[];
		floating: boolean;
		minimized: boolean;
		onDragStart: (e: MouseEvent) => void;
		onResizeStart: (e: MouseEvent) => void;
		onFloatToggle: () => void;
		onMinimize: () => void;
	}

	let {
		isMobile,
		mobileMode = $bindable(),
		activeTab = $bindable(),
		currentLanguage = $bindable(),
		hasInfo,
		hasExercise,
		activeTabs,
		floating,
		minimized,
		onDragStart,
		onResizeStart,
		onFloatToggle,
		onMinimize,
	}: Props = $props();

	let touchStartY = 0;

	const hasC = $derived(activeTabs?.includes('c') ?? false);
	const hasPython = $derived(activeTabs?.includes('python') ?? false);
	const hasVelxio = $derived(activeTabs?.includes('velxio') ?? false);
	const hasCodeEditor = $derived(
		!hasVelxio && (!activeTabs || activeTabs.length === 0 || hasC || hasPython)
	);
	const hasMultiLang = $derived(hasC && hasPython);
	const hasCircuit = $derived(activeTabs?.includes('circuit') ?? false);

	function cycleMobileSheet() {
		if (mobileMode === 'hidden') mobileMode = 'half';
		else if (mobileMode === 'half') mobileMode = 'full';
		else mobileMode = 'hidden';
	}

	function onSheetTouchStart(e: TouchEvent) {
		touchStartY = e.touches[0].clientY;
	}

	function onSheetTouchEnd(e: TouchEvent) {
		const delta = e.changedTouches[0].clientY - touchStartY;
		if (delta < -60) {
			// Swipe up → expand (pull sheet up)
			if (mobileMode === 'hidden') mobileMode = 'half';
			else mobileMode = 'full';
		} else if (delta > 60) {
			// Swipe down → collapse (shrink downward)
			if (mobileMode === 'full') mobileMode = 'half';
			else mobileMode = 'hidden';
		}
	}
</script>

{#snippet chromeTabs()}
	{#if hasInfo}
		<button class="chrome-tab" class:active={activeTab === 'info'} onclick={() => (activeTab = 'info')}>Info</button>
	{/if}
	{#if hasExercise}
		<button class="chrome-tab" class:active={activeTab === 'exercise'} onclick={() => (activeTab = 'exercise')}>Exercise</button>
	{/if}
	{#if hasCodeEditor}
		{#if hasMultiLang}
			<button class="chrome-tab" class:active={activeTab === 'editor' && currentLanguage === 'c'} onclick={() => { activeTab = 'editor'; currentLanguage = 'c'; }}>C</button>
			<button class="chrome-tab" class:active={activeTab === 'editor' && currentLanguage === 'python'} onclick={() => { activeTab = 'editor'; currentLanguage = 'python'; }}>Python</button>
		{:else}
			<button class="chrome-tab" class:active={activeTab === 'editor'} onclick={() => (activeTab = 'editor')}>Code</button>
		{/if}
	{/if}
	{#if hasCircuit}
		<button class="chrome-tab" class:active={activeTab === 'circuit'} onclick={() => (activeTab = 'circuit')}>Circuit</button>
	{/if}
	{#if hasVelxio}
		<button class="chrome-tab" class:active={activeTab === 'velxio'} onclick={() => (activeTab = 'velxio')}>Arduino</button>
	{/if}
	<button class="chrome-tab" class:active={activeTab === 'output'} onclick={() => (activeTab = 'output')}>Output</button>
{/snippet}

{#if isMobile}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="panel-header sheet-handle"
		ontouchstart={onSheetTouchStart}
		ontouchend={onSheetTouchEnd}>
		<button type="button" class="sheet-handle-bar-btn" onclick={cycleMobileSheet} aria-label="Resize panel">
			<div class="sheet-handle-bar"></div>
		</button>
		<div class="chrome-tabs">
			{@render chromeTabs()}
		</div>
	</div>
{:else if floating && !minimized}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="panel-header draggable" onmousedown={onDragStart}>
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<span class="resize-handle" onmousedown={(e) => { e.stopPropagation(); onResizeStart(e); }} title="Resize">&#x25F3;</span>
		<div class="chrome-tabs">
			{@render chromeTabs()}
		</div>
		<div class="panel-actions">
			<button type="button" class="panel-btn" onclick={onMinimize} title="Minimize">▽</button>
			<button type="button" class="panel-btn" onclick={onFloatToggle} title="Dock editor">⊡</button>
		</div>
	</div>
{:else if !isMobile}
	<div class="panel-header">
		<div class="chrome-tabs">
			{@render chromeTabs()}
		</div>
		<div class="panel-actions">
			<button type="button" class="btn-float-toggle" onclick={onFloatToggle} title="Float editor">&#x229E;</button>
		</div>
	</div>
{/if}

<style>
	.panel-header {
		display: flex;
		align-items: flex-end;
		gap: 0.25rem;
		padding: 4px 8px 0;
		background: var(--color-bg-secondary);
		border-bottom: 1px solid var(--color-border);
		user-select: none;
		cursor: default;
		min-height: 36px;
	}
	.panel-header.draggable { cursor: grab; }
	.panel-header.draggable:active { cursor: grabbing; }

	/* ── Actions / buttons ─────────────────────────────── */
	.panel-actions {
		display: flex;
		gap: 0.25rem;
		align-self: center;
	}
	.panel-btn {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 4px;
		padding: 0.15rem 0.5rem;
		cursor: pointer;
		font-size: 0.8rem;
		color: var(--color-text);
		line-height: 1;
	}
	.panel-btn:hover { background: var(--color-border); }

	.btn-float-toggle {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 4px;
		padding: 0.2rem 0.5rem;
		cursor: pointer;
		font-size: 0.95rem;
		color: var(--color-text-muted);
		line-height: 1;
		align-self: center;
	}
	.btn-float-toggle:hover {
		background: var(--color-bg-secondary);
		color: var(--color-text);
	}

	.resize-handle {
		cursor: nwse-resize;
		font-size: 0.9rem;
		color: var(--color-text-muted);
		line-height: 1;
		padding: 0.1rem 0.3rem;
		border-radius: 3px;
		align-self: center;
	}
	.resize-handle:hover {
		background: var(--color-border);
		color: var(--color-text);
	}

	/* ── Chrome-style tabs ─────────────────────────────── */
	.chrome-tabs {
		display: flex;
		align-items: flex-end;
		gap: 2px;
		flex: 1;
		min-width: 0;
		overflow-x: auto;
		scrollbar-width: none;
		-webkit-overflow-scrolling: touch;
	}
	.chrome-tabs::-webkit-scrollbar { display: none; }

	.chrome-tab {
		position: relative;
		padding: 5px 12px;
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
	.chrome-tab:hover:not(.active) {
		background: var(--color-border);
		color: var(--color-text);
	}
	.chrome-tab.active {
		background: var(--color-bg);
		color: var(--color-text);
		font-weight: 600;
		border-color: var(--color-border);
		z-index: 1;
	}

	/* ── Mobile sheet handle ────────────────────────────── */
	.sheet-handle {
		flex-direction: column;
		align-items: stretch;
		border: none;
		border-bottom: none;
		width: 100%;
		color: inherit;
		font: inherit;
		padding: 4px 8px 0;
	}
	.sheet-handle-bar-btn {
		display: block;
		width: 100%;
		background: none;
		border: none;
		padding: 4px 0;
		cursor: pointer;
	}
	.sheet-handle-bar {
		width: 36px;
		height: 4px;
		background: var(--color-border);
		border-radius: 2px;
		margin: 0 auto;
	}
</style>
