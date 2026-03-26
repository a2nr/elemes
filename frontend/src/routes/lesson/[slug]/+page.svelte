<script lang="ts">
	import { page } from '$app/stores';
	import CodeEditor from '$components/CodeEditor.svelte';
	import OutputPanel from '$components/OutputPanel.svelte';
	import ProgressBadge from '$components/ProgressBadge.svelte';
	import { compileCode, trackProgress, getKeyText } from '$services/api';
	import { auth } from '$stores/auth';
	import type { LessonContent } from '$types/lesson';

	// Data from +page.ts load function (SSR + client)
	let { data: pageData } = $props();

	// Derive lesson reactively so navigation updates propagate
	let lesson = $derived(pageData.lesson);

	let data = $state<LessonContent | null>(null);
	let currentCode = $state('');
	let compileOutput = $state('');
	let compileError = $state('');
	let compiling = $state(false);
	let compileSuccess = $state<boolean | null>(null);

	// UI state
	let showSolution = $state(false);
	let activeTab = $state<'editor' | 'output'>('editor');

	let editor = $state<CodeEditor | null>(null);
	let showCelebration = $state(false);

	// Floating editor state
	let editorFloating = $state(false);
	let editorMinimized = $state(false);
	let isMobile = $state(false);
	let mobileExpanded = $state(true);
	let touchStartY = 0;
	let lessonContentEl = $state<HTMLDivElement>();
	let lessonInfoEl = $state<HTMLDetailsElement>();

	// Drag & resize state for floating panel
	let dragging = $state(false);
	let dragOffset = { x: 0, y: 0 };
	let floatPos = $state<{ top: number; left: number } | null>(null);
	let floatSize = $state<{ width: number; height: number } | null>(null);

	// Computed inline style for position & size only (visibility handled via CSS class)
	let floatStyle = $derived.by(() => {
		if (editorFloating && !editorMinimized) {
			let s = '';
			if (floatPos) s += `top:${floatPos.top}px;left:${floatPos.left}px;bottom:auto;right:auto;`;
			if (floatSize) s += `width:${floatSize.width}px;height:${floatSize.height}px;`;
			return s;
		}
		return '';
	});

	function getFloatingPanel(e: MouseEvent): HTMLElement | null {
		return (e.currentTarget as HTMLElement).closest('.editor-area') as HTMLElement | null;
	}

	function onDragStart(e: MouseEvent) {
		if (!editorFloating || isMobile) return;
		const panel = getFloatingPanel(e);
		if (!panel) return;
		dragging = true;
		const rect = panel.getBoundingClientRect();
		dragOffset = { x: e.clientX - rect.left, y: e.clientY - rect.top };
		// Capture current size so it's preserved during/after drag
		if (!floatSize) {
			floatSize = { width: rect.width, height: rect.height };
		}

		const onMove = (ev: MouseEvent) => {
			if (!dragging) return;
			const newLeft = Math.max(0, Math.min(window.innerWidth - 100, ev.clientX - dragOffset.x));
			const newTop = Math.max(0, Math.min(window.innerHeight - 48, ev.clientY - dragOffset.y));
			floatPos = { top: newTop, left: newLeft };
		};
		const onUp = () => {
			dragging = false;
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
		};
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
	}

	function onResizeStart(e: MouseEvent) {
		if (!editorFloating || isMobile) return;
		e.preventDefault();
		const panel = (e.currentTarget as HTMLElement).closest('.editor-area') as HTMLElement;
		if (!panel) return;
		const rect = panel.getBoundingClientRect();
		const startX = e.clientX;
		const startY = e.clientY;
		const startW = rect.width;
		const startH = rect.height;
		const startLeft = rect.left;
		const startTop = rect.top;

		const onMove = (ev: MouseEvent) => {
			// Handle grows left+up from top-left corner
			const dx = startX - ev.clientX;
			const dy = startY - ev.clientY;
			const newW = Math.max(320, startW + dx);
			const newH = Math.max(200, startH + dy);
			floatSize = { width: newW, height: newH };
			floatPos = {
				left: startLeft - (newW - startW),
				top: startTop - (newH - startH),
			};
		};
		const onUp = () => {
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
		};
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
	}

	// Media query detection
	$effect(() => {
		if (typeof window === 'undefined') return;
		const mql = window.matchMedia('(max-width: 768px)');
		isMobile = mql.matches;
		const handler = (e: MediaQueryListEvent) => {
			isMobile = e.matches;
			if (isMobile) {
				editorFloating = false;
				editorMinimized = false;
			}
		};
		mql.addEventListener('change', handler);
		return () => mql.removeEventListener('change', handler);
	});

	// Selection prevention: clear any text selection inside lesson content
	// CSS user-select:none may be bypassed on some mobile browsers, so we
	// use JS as a fallback — detect selection via getSelection() and clear it.
	$effect(() => {
		if (typeof window === 'undefined') return;

		function clearIfInProtectedArea() {
			const sel = window.getSelection();
			if (!sel || sel.isCollapsed) return;

			const node = sel.anchorNode;
			if (!node) return;

			// Only clear if selection is inside lesson content or lesson info
			const inLesson = lessonContentEl?.contains(node);
			const inInfo = lessonInfoEl?.contains(node);
			if (inLesson || inInfo) {
				sel.removeAllRanges();
			}
		}

		// selectionchange: fires during selection (real-time)
		document.addEventListener('selectionchange', clearIfInProtectedArea);
		// mouseup: backup for desktop (fires after mouse release)
		document.addEventListener('mouseup', clearIfInProtectedArea);
		// touchend: backup for mobile (fires after long-press select)
		document.addEventListener('touchend', clearIfInProtectedArea);

		return () => {
			document.removeEventListener('selectionchange', clearIfInProtectedArea);
			document.removeEventListener('mouseup', clearIfInProtectedArea);
			document.removeEventListener('touchend', clearIfInProtectedArea);
		};
	});

	function toggleFloat() {
		editorFloating = !editorFloating;
		editorMinimized = false;
		floatPos = null;
		floatSize = null;
	}

	function minimizeFloat() {
		editorMinimized = true;
	}

	function restoreFloat() {
		editorMinimized = false;
	}

	function toggleMobileSheet() {
		mobileExpanded = !mobileExpanded;
	}

	function onSheetTouchStart(e: TouchEvent) {
		touchStartY = e.touches[0].clientY;
	}

	function onSheetTouchEnd(e: TouchEvent) {
		const delta = e.changedTouches[0].clientY - touchStartY;
		if (delta > 60) mobileExpanded = false;
		else if (delta < -60) mobileExpanded = true;
	}

	const slug = $derived($page.params.slug);

	// Sync lesson data when navigating between lessons
	$effect(() => {
		if (lesson) {
			data = lesson;
			currentCode = lesson.initial_code ?? '';
			compileOutput = '';
			compileError = '';
			compileSuccess = null;
			showSolution = false;
			activeTab = 'editor';
			mobileExpanded = true;
		}
	});

	/** Check if student code contains all required key_text keywords. */
	function checkKeyText(code: string, keyText: string): boolean {
		if (!keyText.trim()) return true;
		const keys = keyText.split('\n').map(k => k.trim()).filter(k => k.length > 0);
		return keys.every(key => code.includes(key));
	}

	async function handleRun() {
		if (!data) return;
		compiling = true;
		compileOutput = '';
		compileError = '';
		compileSuccess = null;
		activeTab = 'output';

		try {
			const code = editor?.getCode() ?? currentCode;
			const res = await compileCode({ code, language: data.language });

			if (res.success) {
				compileOutput = res.output;
				compileSuccess = true;

				// Check completion: output must match AND code must contain all key_text keywords
				if (data.expected_output) {
					const outputMatch = res.output.trim() === data.expected_output.trim();
					const keyTextMatch = checkKeyText(code, data.key_text ?? '');
					if (outputMatch && keyTextMatch) {
						// Celebration for everyone
						showCelebration = true;
						setTimeout(() => (showCelebration = false), 3000);
						// Track progress only for logged-in users
						if (auth.isLoggedIn) {
							const lessonName = slug.replace('.md', '');
							await trackProgress(auth.token, lessonName);
							data.lesson_completed = true;
						}
					}
				}
			} else {
				compileError = res.error || 'Compilation failed';
				compileSuccess = false;
			}
		} catch {
			compileError = 'Gagal terhubung ke server';
			compileSuccess = false;
		} finally {
			compiling = false;
		}
	}

	function handleReset() {
		if (!data) return;
		currentCode = data.initial_code;
		editor?.setCode(data.initial_code);
		compileOutput = '';
		compileError = '';
		compileSuccess = null;
	}

	function handleShowSolution() {
		if (!data?.solution_code) return;
		showSolution = !showSolution;
		if (showSolution) {
			editor?.setCode(data.solution_code);
		} else {
			editor?.setCode(currentCode);
		}
	}
</script>

<svelte:head>
	<title>{data?.lesson_title ?? 'Pelajaran'} - Elemes LMS</title>
</svelte:head>

<!-- Celebration overlay -->
{#if showCelebration}
	<div class="celebration-overlay">
		<div class="celebration-content">
			<div class="celebration-icon">&#10003;</div>
			<p class="celebration-text">Selamat! Latihan Selesai!</p>
		</div>
	</div>
{/if}

{#if data}
	<!-- Navigation breadcrumb -->
	<div class="lesson-nav">
		<a href="/">&larr; Semua Pelajaran</a>
		{#if data.lesson_completed}
			<ProgressBadge completed={true} />
		{/if}
	</div>

	<h1 class="lesson-title">{data.lesson_title}</h1>

	<!-- Lesson info (collapsible, selection prevented) -->
	{#if data.lesson_info}
		<details class="lesson-info" bind:this={lessonInfoEl}
			onselectstart={(e) => e.preventDefault()}
			oncopy={(e) => e.preventDefault()}
			oncontextmenu={(e) => e.preventDefault()}>
			<summary>Informasi Pelajaran</summary>
			<div class="info-content">{@html data.lesson_info}</div>
		</details>
	{/if}

	<!-- Main content area -->
	<div class="lesson-layout" class:single-col={editorFloating || isMobile}>
		<!-- Left: Lesson content (selection & copy prevention) -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="lesson-content" bind:this={lessonContentEl}
			role="region" aria-label="Konten pelajaran"
			class:full-width={editorFloating || isMobile}
			onselectstart={(e) => e.preventDefault()}
			oncopy={(e) => e.preventDefault()}
			oncut={(e) => e.preventDefault()}
			oncontextmenu={(e) => e.preventDefault()}>
			<div class="prose">{@html data.lesson_content}</div>

			{#if data.exercise_content}
				<div class="exercise-section">
					<h2>Latihan</h2>
					<div class="prose">{@html data.exercise_content}</div>
				</div>
			{/if}
		</div>

		<!-- Floating restore button (visible when minimized) -->
		{#if editorFloating && editorMinimized && !isMobile}
			<button type="button" class="float-restore-btn" onclick={restoreFloat}
				title="Tampilkan Code Editor">
				&#9654; Editor
			</button>
		{/if}

		<!-- Editor + Output -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="editor-area"
			class:floating={editorFloating && !isMobile && !editorMinimized}
			class:floating-hidden={editorFloating && editorMinimized && !isMobile}
			class:mobile-sheet={isMobile}
			class:mobile-collapsed={isMobile && !mobileExpanded}
			style={floatStyle}>

			<!-- Floating/Sheet header -->
			{#if isMobile}
				<button class="panel-header sheet-handle"
					ontouchstart={onSheetTouchStart}
					ontouchend={onSheetTouchEnd}
					onclick={toggleMobileSheet}>
					<div class="sheet-handle-bar"></div>
					<span class="panel-title">Code Editor</span>
				</button>
			{:else if editorFloating && !editorMinimized}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="panel-header draggable" onmousedown={onDragStart}>
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<span class="resize-handle" onmousedown={(e) => { e.stopPropagation(); onResizeStart(e); }} title="Resize">&#x25F3;</span>
					<span class="panel-title">Code Editor</span>
					<div class="panel-actions">
						<button type="button" class="panel-btn" onclick={minimizeFloat}
							title="Minimize">▽</button>
						<button type="button" class="panel-btn" onclick={toggleFloat}
							title="Dock editor">⊡</button>
					</div>
				</div>
			{/if}

			<!-- Editor body -->
			<div class="editor-body" class:body-hidden={isMobile && !mobileExpanded}>
				{#if isMobile}
					<div class="mobile-tabs">
						<button class="tab" class:active={activeTab === 'editor'}
							onclick={() => (activeTab = 'editor')}>Editor</button>
						<button class="tab" class:active={activeTab === 'output'}
							onclick={() => (activeTab = 'output')}>Output</button>
					</div>
				{/if}

				<!-- Toolbar -->
				<div class="toolbar">
					<button type="button" class="btn btn-success" onclick={handleRun} disabled={compiling}>
						{compiling ? 'Compiling...' : '&#9654; Run'}
					</button>
					<button type="button" class="btn btn-secondary" onclick={handleReset}>Reset</button>
					{#if data.solution_code && auth.isLoggedIn && data.lesson_completed}
						<button type="button" class="btn btn-secondary" onclick={handleShowSolution}>
							{showSolution ? 'Sembunyikan Solusi' : 'Lihat Solusi'}
						</button>
					{/if}
					<span class="lang-label">{data.language_display_name}</span>
					{#if !isMobile && !editorFloating}
						<button type="button" class="btn-float-toggle" onclick={toggleFloat} title="Float editor">&#x229E;</button>
					{/if}
				</div>

				<!-- Editor panel -->
				<div class="panel" class:hidden-mobile={isMobile && activeTab !== 'editor'}>
					<CodeEditor
						bind:this={editor}
						code={currentCode}
						language={data.language}
						noPaste={true}
						onchange={(val) => (currentCode = val)}
					/>
				</div>

				<!-- Output panel -->
				<div class="panel" class:hidden-mobile={isMobile && activeTab !== 'output'}>
					<OutputPanel
						output={compileOutput}
						error={compileError}
						loading={compiling}
						success={compileSuccess}
					/>
				</div>

				<!-- Expected output hint -->
				{#if data.expected_output}
					<details class="expected-output">
						<summary>Expected Output</summary>
						<pre>{data.expected_output}</pre>
					</details>
				{/if}
			</div>
		</div>
	</div>

	<!-- Prev / Next navigation -->
	<div class="lesson-footer-nav">
		{#if data.prev_lesson}
			<a href="/lesson/{data.prev_lesson.filename}" class="btn btn-secondary">
				&larr; {data.prev_lesson.title}
			</a>
		{:else}
			<span></span>
		{/if}
		{#if data.next_lesson}
			<a href="/lesson/{data.next_lesson.filename}" class="btn btn-primary">
				{data.next_lesson.title} &rarr;
			</a>
		{/if}
	</div>
{/if}

<style>
	.lesson-nav {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.5rem;
		font-size: 0.85rem;
	}

	.lesson-title {
		font-size: 1.5rem;
		margin-bottom: 1rem;
	}

	.lesson-info {
		margin-bottom: 1rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.75rem;
		background: var(--color-bg-secondary);
	}
	.lesson-info summary {
		cursor: pointer;
		font-weight: 600;
		font-size: 0.9rem;
	}
	.info-content {
		margin-top: 0.75rem;
		font-size: 0.85rem;
	}

	/* ── Two-column layout ─────────────────────────────────── */
	.lesson-layout {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1.5rem;
		align-items: start;
	}

	.lesson-content {
		overflow-y: auto;
		max-height: 80vh;
		padding-right: 0.5rem;
		-webkit-user-select: none;
		user-select: none;
		-webkit-touch-callout: none;
	}

	.lesson-info {
		-webkit-user-select: none;
		user-select: none;
		-webkit-touch-callout: none;
	}

	.prose :global(pre) {
		background: var(--color-bg-secondary);
		padding: 0.75rem;
		border-radius: var(--radius);
		overflow-x: auto;
	}
	.prose :global(code) {
		font-family: var(--font-mono);
		font-size: 0.85rem;
	}
	.prose :global(p) {
		margin-bottom: 0.75rem;
	}
	.prose :global(h2),
	.prose :global(h3) {
		margin-top: 1.25rem;
		margin-bottom: 0.5rem;
	}

	.exercise-section {
		margin-top: 1.5rem;
		padding-top: 1rem;
		border-top: 2px solid var(--color-primary);
	}
	.exercise-section h2 {
		color: var(--color-primary);
		font-size: 1.1rem;
	}

	/* ── Editor area (inline mode) ─────────────────────────── */
	.editor-area {
		position: sticky;
		top: 4rem;
	}

	/* ── Single-column layout ──────────────────────────────── */
	.lesson-layout.single-col {
		grid-template-columns: 1fr;
	}
	.lesson-content.full-width {
		max-height: none;
		padding-right: 0;
		padding-bottom: 60px;
	}

	/* ── Toolbar ───────────────────────────────────────────── */
	.toolbar {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
		flex-wrap: wrap;
	}
	.btn-secondary {
		background: var(--color-bg-secondary);
		color: var(--color-text);
		border: 1px solid var(--color-border);
	}
	.btn-secondary:hover {
		background: var(--color-border);
	}
	.lang-label {
		margin-left: auto;
		font-size: 0.75rem;
		color: var(--color-text-muted);
		font-weight: 600;
		text-transform: uppercase;
	}
	.panel {
		margin-bottom: 0.75rem;
	}
	.expected-output {
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}
	.expected-output pre {
		background: var(--color-bg-secondary);
		padding: 0.5rem;
		border-radius: var(--radius);
		margin-top: 0.5rem;
	}

	/* ── Floating restore button (when minimized) ────────── */
	.float-restore-btn {
		position: fixed;
		bottom: 1rem;
		right: 1rem;
		z-index: 50;
		background: var(--color-primary);
		color: #fff;
		border: none;
		border-radius: var(--radius);
		padding: 0.6rem 1rem;
		font-size: 0.85rem;
		font-weight: 600;
		cursor: pointer;
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
		transition: background 0.15s, transform 0.1s;
	}
	.float-restore-btn:hover {
		background: var(--color-primary-dark);
	}
	.float-restore-btn:active {
		transform: scale(0.95);
	}

	/* ── Float toggle button ───────────────────────────────── */
	.btn-float-toggle {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 4px;
		padding: 0.2rem 0.5rem;
		cursor: pointer;
		font-size: 0.95rem;
		color: var(--color-text-muted);
		line-height: 1;
	}
	.btn-float-toggle:hover {
		background: var(--color-bg-secondary);
		color: var(--color-text);
	}

	/* ── Panel header (floating & sheet) ───────────────────── */
	.panel-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		background: var(--color-bg-secondary);
		border-bottom: 1px solid var(--color-border);
		user-select: none;
		cursor: default;
		flex-wrap: wrap;
	}
	.panel-header.draggable {
		cursor: grab;
	}
	.panel-header.draggable:active {
		cursor: grabbing;
	}
	.panel-title {
		font-size: 0.85rem;
		font-weight: 600;
		flex: 1;
	}
	.panel-actions {
		display: flex;
		gap: 0.25rem;
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
	.panel-btn:hover {
		background: var(--color-border);
	}

	/* ── Desktop floating mode ─────────────────────────────── */
	.editor-area.floating {
		position: fixed;
		bottom: 1rem;
		right: 1rem;
		top: auto;
		width: 45vw;
		min-width: 320px;
		max-width: 90vw;
		max-height: 85vh;
		z-index: 50;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
		display: flex;
		flex-direction: column;
		overflow: auto;
	}
	.resize-handle {
		cursor: nwse-resize;
		font-size: 0.9rem;
		color: var(--color-text-muted);
		line-height: 1;
		padding: 0.1rem 0.3rem;
		border-radius: 3px;
	}
	.resize-handle:hover {
		background: var(--color-border);
		color: var(--color-text);
	}
	.editor-area.floating .editor-body {
		flex: 1;
		overflow-y: auto;
		padding: 0.5rem;
		min-height: 0;
	}
	.editor-area.floating-hidden {
		display: none !important;
	}

	/* ── Mobile bottom sheet ───────────────────────────────── */
	.editor-area.mobile-sheet {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		top: auto;
		z-index: 50;
		background: var(--color-bg);
		border-top: 2px solid var(--color-primary);
		border-radius: 12px 12px 0 0;
		box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
		max-height: 70vh;
		display: flex;
		flex-direction: column;
		transition: transform 0.3s ease;
	}
	.editor-area.mobile-collapsed {
		transform: translateY(calc(100% - 48px));
	}
	.mobile-sheet .editor-body {
		flex: 1;
		overflow-y: auto;
		padding: 0.5rem;
		overscroll-behavior: contain;
	}
	.sheet-handle {
		flex-direction: column;
		border: none;
		border-bottom: 1px solid var(--color-border);
		cursor: pointer;
		width: 100%;
		color: inherit;
		font: inherit;
		text-align: center;
	}
	.sheet-handle-bar {
		width: 36px;
		height: 4px;
		background: var(--color-border);
		border-radius: 2px;
		margin: 0 auto 0.25rem;
	}

	/* ── Mobile tabs ───────────────────────────────────────── */
	.mobile-tabs {
		display: flex;
		gap: 0;
		margin-bottom: 0.5rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.tab {
		flex: 1;
		padding: 0.5rem;
		border: none;
		background: var(--color-bg-secondary);
		cursor: pointer;
		font-weight: 500;
		font-size: 0.85rem;
	}
	.tab.active {
		background: var(--color-primary);
		color: #fff;
	}

	/* ── Utility ───────────────────────────────────────────── */
	.hidden-mobile {
		display: none;
	}
	.editor-body.body-hidden {
		display: none;
	}

	/* ── Footer nav ────────────────────────────────────────── */
	.lesson-footer-nav {
		display: flex;
		justify-content: space-between;
		margin-top: 2rem;
		padding-top: 1rem;
		border-top: 1px solid var(--color-border);
	}

	/* ── Celebration overlay ──────────────────────────────── */
	.celebration-overlay {
		position: fixed;
		inset: 0;
		z-index: 200;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(0, 0, 0, 0.4);
		animation: celebFadeIn 0.3s ease-out;
		pointer-events: none;
	}
	.celebration-content {
		text-align: center;
		animation: celebPop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
	}
	.celebration-icon {
		width: 80px;
		height: 80px;
		margin: 0 auto 1rem;
		background: var(--color-success);
		color: #fff;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 2.5rem;
		font-weight: 700;
		box-shadow: 0 0 0 0 rgba(25, 135, 84, 0.4);
		animation: celebRing 1.5s ease-out;
	}
	.celebration-text {
		font-size: 1.4rem;
		font-weight: 700;
		color: #fff;
		text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
	}
	@keyframes celebFadeIn {
		from { opacity: 0; }
		to { opacity: 1; }
	}
	@keyframes celebPop {
		0% { transform: scale(0.5); opacity: 0; }
		100% { transform: scale(1); opacity: 1; }
	}
	@keyframes celebRing {
		0% { box-shadow: 0 0 0 0 rgba(25, 135, 84, 0.6); }
		70% { box-shadow: 0 0 0 30px rgba(25, 135, 84, 0); }
		100% { box-shadow: 0 0 0 0 rgba(25, 135, 84, 0); }
	}
</style>
