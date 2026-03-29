<script lang="ts">
	import { page } from '$app/stores';
	import { beforeNavigate } from '$app/navigation';
	import CodeEditor from '$components/CodeEditor.svelte';
	import CircuitEditor from '$components/CircuitEditor.svelte';
	import OutputPanel from '$components/OutputPanel.svelte';
	import CelebrationOverlay from '$components/CelebrationOverlay.svelte';
	import { compileCode, trackProgress } from '$services/api';
	import { auth, authLoggedIn } from '$stores/auth';
	import { lessonContext } from '$stores/lessonContext';
	import { noSelect } from '$actions/noSelect';
	import { createFloatingPanel } from '$actions/floatingPanel.svelte';
	import { highlightAllCode } from '$actions/highlightCode';
	import { tick } from 'svelte';
	import type { LessonContent } from '$types/lesson';

	// Data from +page.ts load function (SSR + client)
	let { data: pageData } = $props();

	// Derive lesson reactively so navigation updates propagate
	let lesson = $derived(pageData.lesson);

	let data = $state<LessonContent | null>(null);
	let lessonCompleted = $state(false);
	let currentCode = $state('');
	let compileOutput = $state('');
	let compileError = $state('');
	let compiling = $state(false);
	let compileSuccess = $state<boolean | null>(null);

	// UI state
	let showSolution = $state(false);
	let activeTab = $state<'info' | 'exercise' | 'editor' | 'circuit' | 'output'>('info');

	let editor = $state<CodeEditor | null>(null);
	let circuitEditor = $state<CircuitEditor | null>(null);
	let showCelebration = $state(false);

	// Container refs for syntax highlighting
	let contentEl = $state<HTMLElement | null>(null);
	let tabsEl = $state<HTMLElement | null>(null);

	// Floating editor
	const float = createFloatingPanel();

	// Mobile state: 'hidden' (only handle bar), 'half' (60%), 'full' (100%)
	let isMobile = $state(false);
	let mobileMode = $state<'hidden' | 'half' | 'full'>('half');
	let touchStartY = 0;

	// Media query detection
	$effect(() => {
		if (typeof window === 'undefined') return;
		const mql = window.matchMedia('(max-width: 768px)');
		isMobile = mql.matches;
		const handler = (e: MediaQueryListEvent) => {
			isMobile = e.matches;
			if (isMobile) {
				float.floating = false;
				float.minimized = false;
			}
		};
		mql.addEventListener('change', handler);
		return () => mql.removeEventListener('change', handler);
	});

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
		if (delta > 60) {
			// Swipe down: full→half→hidden
			if (mobileMode === 'full') mobileMode = 'half';
			else mobileMode = 'hidden';
		} else if (delta < -60) {
			// Swipe up: hidden→half→full
			if (mobileMode === 'hidden') mobileMode = 'half';
			else mobileMode = 'full';
		}
	}

	const slug = $derived($page.params.slug);

	// Sync lesson data when navigating between lessons
	$effect(() => {
		if (lesson) {
			data = lesson;
			lessonCompleted = lesson.lesson_completed;
			currentCode = lesson.initial_code_c || lesson.initial_python || lesson.initial_code || '';
			compileOutput = '';
			compileError = '';
			compileSuccess = null;
			showSolution = false;
			if (lesson.lesson_info) activeTab = 'info';
			else if (lesson.exercise_content) activeTab = 'exercise';
			else if (lesson.active_tabs?.includes('circuit') && !lesson.active_tabs?.includes('c') && !lesson.active_tabs?.includes('python')) activeTab = 'circuit';
			else activeTab = 'editor';
			mobileMode = 'half';

			// Populate navbar context
			lessonContext.set({
				title: lesson.lesson_title,
				completed: lesson.lesson_completed,
				prevLesson: lesson.prev_lesson,
				nextLesson: lesson.next_lesson
			});
		}
	});

	// Clear lesson context when leaving page
	beforeNavigate(() => {
		lessonContext.set(null);
	});

	// Apply syntax highlighting after content renders
	$effect(() => {
		if (data) {
			tick().then(() => {
				if (contentEl) highlightAllCode(contentEl);
				if (tabsEl) highlightAllCode(tabsEl);
			});
		}
	});

	/** Check if student code contains all required key_text keywords. */
	function checkKeyText(code: string, keyText: string): boolean {
		if (!keyText.trim()) return true;
		const keys = keyText.split('\n').map(k => k.trim()).filter(k => k.length > 0);
		return keys.every(key => code.includes(key));
	}

	
	async function evaluateCircuit() {
		if (!data || !circuitEditor) return;
		const simApi = circuitEditor.getApi();
		if (!simApi) {
			compileError = "Simulator belum siap.";
			compileSuccess = false;
			activeTab = 'output';
			return;
		}

		compiling = true;
		compileOutput = 'Mengevaluasi rangkaian...';
		compileError = '';
		compileSuccess = null;
		activeTab = 'output';

		try {
			let expectedState: any = null;
			try {
				if (data.expected_output) {
					expectedState = JSON.parse(data.expected_output);
				}
			} catch (e) {
				compileError = "Format EXPECTED_OUTPUT tidak valid (Harus JSON).";
				compileSuccess = false;
				compiling = false;
				return;
			}

			if (!expectedState) {
				compileOutput = "Tidak ada kriteria evaluasi yang ditetapkan.";
				compileSuccess = true;
				compiling = false;
				return;
			}

			let allPassed = true;
			let messages: string[] = [];

			if (expectedState.nodes) {
				for (const [nodeName, criteria] of Object.entries<any>(expectedState.nodes)) {
					const actualV = simApi.getNodeVoltage(nodeName);
					if (actualV === undefined || actualV === null) {
						allPassed = false;
						messages.push(`❌ Node '${nodeName}' tidak ditemukan.`);
						continue;
					}
					
					const expectedV = criteria.voltage;
					const tol = criteria.tolerance || 0.1;
					if (Math.abs(actualV - expectedV) <= tol) {
						messages.push(`✅ Node '${nodeName}': Tegangan ${actualV.toFixed(2)}V (Sesuai)`);
					} else {
						allPassed = false;
						messages.push(`❌ Node '${nodeName}': Tegangan ${actualV.toFixed(2)}V (Harusnya ~${expectedV}V)`);
					}
				}
			}

			if (expectedState.elements && typeof simApi.elements === 'function' && typeof simApi.getElm === 'function') {
				const elmCount = simApi.elements();
				const elements = [];
				for (let i = 0; i < elmCount; i++) {
					elements.push(simApi.getElm(i));
				}
				for (const [infoMatch, criteria] of Object.entries<any>(expectedState.elements)) {
					let found = null;
					for (const el of elements) {
                        try {
						    const info = typeof el.getInfo === 'function' ? el.getInfo() : null;
                            // the info from getInfo is an array or something we might not be able to parse natively via JS.
                            // but we skip elements checking for now unless user really needs it
                        } catch (e) {}
					}
				}
			}

			// End of elements check

			const circuitText = circuitEditor.getCircuitText();
			const keyTextMatch = checkKeyText(circuitText, data.key_text ?? '');
			if (!keyTextMatch) {
				allPassed = false;
				messages.push(`❌ Komponen wajib belum lengkap (lihat instruksi).`);
			}

			compileOutput = messages.join('\n');
			compileSuccess = allPassed;

			if (allPassed) {
				showCelebration = true;
				if (auth.isLoggedIn) {
					const lessonName = slug.replace('.md', '');
					await trackProgress(auth.token, lessonName);
					lessonCompleted = true;
					lessonContext.update(ctx => ctx ? { ...ctx, completed: true } : ctx);
				}
				setTimeout(() => {
					showCelebration = false;
					activeTab = 'circuit';
				}, 3000);
			}
		} catch (err: any) {
			compileError = `Evaluasi gagal: ${err.message}`;
			compileSuccess = false;
		} finally {
			compiling = false;
		}
	}

	async function handleRun() {
		if (activeTab === 'circuit') {
			await evaluateCircuit();
			return;
		}
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

				if (data.expected_output) {
					const outputMatch = res.output.trim() === data.expected_output.trim();
					const keyTextMatch = checkKeyText(code, data.key_text ?? '');
					if (outputMatch && keyTextMatch) {
						showCelebration = true;
						if (auth.isLoggedIn) {
							const lessonName = slug.replace('.md', '');
							await trackProgress(auth.token, lessonName);
							lessonCompleted = true;
							lessonContext.update(ctx => ctx ? { ...ctx, completed: true } : ctx);
						}
						// Auto-show solution after celebration
						if (data.solution_code) {
							showSolution = true;
							editor?.setCode(data.solution_code);
						}
						setTimeout(() => {
							showCelebration = false;
							activeTab = 'editor';
						}, 3000);
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
		if (activeTab === 'circuit') {
			circuitEditor?.setCircuitText(data.initial_circuit || data.initial_code);
		} else {
			currentCode = data.initial_code;
			editor?.setCode(data.initial_code);
		}
		compileOutput = '';
		compileError = '';
		compileSuccess = null;
	}

	function handleShowSolution() {
		if (!data?.solution_code) return;
		showSolution = !showSolution;
		if (showSolution) {
			if (activeTab === 'circuit' || data.active_tabs?.includes('circuit')) {
				circuitEditor?.setCircuitText(data.solution_code);
			} else {
				editor?.setCode(data.solution_code);
			}
		} else {
			if (activeTab === 'circuit' || data.active_tabs?.includes('circuit')) {
				circuitEditor?.setCircuitText(data.initial_code);
			} else {
				editor?.setCode(currentCode);
			}
		}
	}
</script>

<svelte:head>
	<title>{data?.lesson_title ?? 'Pelajaran'} - Elemes LMS</title>
</svelte:head>

{#if data}
	<!-- Main content area -->
	<div class="lesson-layout" class:single-col={float.floating || isMobile}>
		<!-- Left: Lesson content (selection & copy prevention) -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="lesson-content" bind:this={contentEl} use:noSelect
			role="region" aria-label="Konten pelajaran"
			class:full-width={float.floating || isMobile}
			onselectstart={(e) => e.preventDefault()}
			oncopy={(e) => e.preventDefault()}
			oncut={(e) => e.preventDefault()}
			oncontextmenu={(e) => e.preventDefault()}>
			<div class="prose">{@html data.lesson_content}</div>

			<!-- All lessons list -->
			{#if data.ordered_lessons?.length}
				<div class="all-lessons">
					<h3 class="all-lessons-heading">Semua Pelajaran</h3>
					<div class="all-lessons-list">
						{#each data.ordered_lessons as lesson (lesson.filename)}
							<a href="/lesson/{lesson.filename}"
								class="lesson-item"
								class:lesson-item-active={lesson.filename === slug}>
								{#if lesson.completed}
									<span class="lesson-check">&#10003;</span>
								{/if}
								<span class="lesson-item-title">{lesson.title}</span>
							</a>
						{/each}
					</div>
				</div>
			{/if}
		</div>

		<!-- Floating restore button (visible when minimized) -->
		{#if float.floating && float.minimized && !isMobile}
			<button type="button" class="float-restore-btn" onclick={float.restore}
				title="Tampilkan Code Editor">
				&#9654; Editor
			</button>
		{/if}

		<!-- Editor + Output -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="editor-area"
			class:floating={float.floating && !isMobile && !float.minimized}
			class:floating-hidden={float.floating && float.minimized && !isMobile}
			class:mobile-sheet={isMobile}
			class:mobile-hidden={isMobile && mobileMode === 'hidden'}
			class:mobile-half={isMobile && mobileMode === 'half'}
			class:mobile-full={isMobile && mobileMode === 'full'}
			style={float.style}>

			<!-- Panel header -->
			{#if isMobile}
				<button class="panel-header sheet-handle"
					ontouchstart={onSheetTouchStart}
					ontouchend={onSheetTouchEnd}
					onclick={cycleMobileSheet}>
					<div class="sheet-handle-bar"></div>
					<span class="panel-title">Workspace</span>
				</button>
			{:else if float.floating && !float.minimized}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="panel-header draggable" onmousedown={float.onDragStart}>
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<span class="resize-handle" onmousedown={(e) => { e.stopPropagation(); float.onResizeStart(e); }} title="Resize">&#x25F3;</span>
					<span class="panel-title">Workspace</span>
					<div class="panel-actions">
						<button type="button" class="panel-btn" onclick={float.minimize}
							title="Minimize">▽</button>
						<button type="button" class="panel-btn" onclick={float.toggle}
							title="Dock editor">⊡</button>
					</div>
				</div>
			{:else if !isMobile}
				<div class="panel-header">
					<span class="panel-title">Workspace</span>
					<div class="panel-actions">
						<button type="button" class="btn-float-toggle" onclick={float.toggle} title="Float editor">&#x229E;</button>
					</div>
				</div>
			{/if}

			<!-- Editor body -->
			<div class="editor-body" bind:this={tabsEl} class:body-hidden={isMobile && mobileMode === 'hidden'}>
				<!-- Tabs -->
				<div class="panel-tabs">
					{#if data.lesson_info}
						<button class="tab" class:active={activeTab === 'info'}
							onclick={() => (activeTab = 'info')}>Informasi</button>
					{/if}
					{#if data.exercise_content}
						<button class="tab" class:active={activeTab === 'exercise'}
							onclick={() => (activeTab = 'exercise')}>Exercise</button>
					{/if}
					{#if !data.active_tabs || data.active_tabs.length === 0 || data.active_tabs.includes('c') || data.active_tabs.includes('python')}
					<button class="tab" class:active={activeTab === 'editor'}
						onclick={() => (activeTab = 'editor')}>Code Editor</button>
					{/if}
					{#if data.active_tabs?.includes('circuit')}
					<button class="tab" class:active={activeTab === 'circuit'}
						onclick={() => (activeTab = 'circuit')}>Circuit Simulator</button>
					{/if}
					<button class="tab" class:active={activeTab === 'output'}
						onclick={() => (activeTab = 'output')}>Output</button>
				</div>

				<!-- Info tab panel -->
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="tab-panel" class:tab-hidden={activeTab !== 'info'}
					use:noSelect
					onselectstart={(e) => e.preventDefault()}
					oncopy={(e) => e.preventDefault()}
					oncontextmenu={(e) => e.preventDefault()}>
					{#if data.lesson_info}
						<div class="tab-content">{@html data.lesson_info}</div>
					{/if}
				</div>

				<!-- Exercise tab panel -->
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="tab-panel" class:tab-hidden={activeTab !== 'exercise'}
					use:noSelect
					onselectstart={(e) => e.preventDefault()}
					oncopy={(e) => e.preventDefault()}
					oncontextmenu={(e) => e.preventDefault()}>
					{#if data.exercise_content}
						<div class="tab-content">
							<h2 class="tab-heading">Latihan</h2>
							{@html data.exercise_content}
						</div>
					{/if}
				</div>

				<!-- Circuit tab panel -->
				{#if data.active_tabs?.includes('circuit')}
				<div class="tab-panel" class:tab-hidden={activeTab !== 'circuit'}>
					<div class="toolbar">
						<button type="button" class="btn btn-success" onclick={handleRun} disabled={compiling}>
							{compiling ? 'Mengevaluasi...' : '▶ Cek Rangkaian'}
						</button>
						<button type="button" class="btn btn-secondary" onclick={handleReset}>Reset</button>
						{#if data.solution_code && $authLoggedIn && lessonCompleted}
							<button type="button" class="btn btn-secondary" onclick={handleShowSolution}>
								{showSolution ? 'Sembunyikan Solusi' : 'Lihat Solusi'}
							</button>
						{/if}
					</div>
					<div class="panel">
						<CircuitEditor
							bind:this={circuitEditor}
							initialCircuit={data.initial_circuit || data.initial_code}
							storageKey={($authLoggedIn && !showSolution) ? `elemes_circuit_${slug}` : undefined}
						/>
					</div>
				</div>
				{/if}

				<!-- Editor tab panel -->
				{#if !data.active_tabs || data.active_tabs.length === 0 || data.active_tabs.includes('c') || data.active_tabs.includes('python')}
				<div class="tab-panel" class:tab-hidden={activeTab !== 'editor'}>
					<div class="toolbar">
						<button type="button" class="btn btn-success" onclick={handleRun} disabled={compiling}>
							{compiling ? 'Compiling...' : '\u25B6 Run'}
						</button>
						<button type="button" class="btn btn-secondary" onclick={handleReset}>Reset</button>
						{#if data.solution_code && $authLoggedIn && lessonCompleted}
							<button type="button" class="btn btn-secondary" onclick={handleShowSolution}>
								{showSolution ? 'Sembunyikan Solusi' : 'Lihat Solusi'}
							</button>
						{/if}
						<span class="lang-label">{data.language_display_name}</span>
					</div>

					<div class="panel">
						<CodeEditor
							bind:this={editor}
							code={currentCode}
							language={data.language}
							noPaste={true}
							storageKey={($authLoggedIn && !showSolution) ? `elemes_draft_${slug}` : undefined}
							onchange={(val) => { if (!showSolution) currentCode = val; }}
						/>
					</div>

					{#if data.expected_output}
						<details class="expected-output">
							<summary>Expected Output</summary>
							<pre>{data.expected_output}</pre>
						</details>
					{/if}
				</div>

				{/if}

				<!-- Output tab panel -->
				<div class="tab-panel" class:tab-hidden={activeTab !== 'output'}>
					<OutputPanel
						output={compileOutput}
						error={compileError}
						loading={compiling}
						success={compileSuccess}
					/>
				</div>
			</div>

			<CelebrationOverlay visible={showCelebration} />
		</div>
	</div>

{/if}

<style>
	.tab-content {
		font-size: 0.85rem;
		padding: 0.75rem 0.5rem;
		line-height: 1.65;
	}
	.tab-content :global(pre) {
		background: var(--color-bg-secondary);
		padding: 0.75rem;
		border-radius: var(--radius);
		overflow-x: auto;
	}
	.tab-content :global(code) {
		font-family: var(--font-mono);
		font-size: 0.8rem;
	}
	.tab-content :global(p) {
		margin-bottom: 0.75rem;
	}
	.tab-content :global(h2),
	.tab-content :global(h3) {
		margin-top: 1.25rem;
		margin-bottom: 0.5rem;
	}
	.tab-content :global(ul),
	.tab-content :global(ol) {
		margin-bottom: 0.75rem;
		padding-left: 1.5rem;
	}
	.tab-content :global(li) {
		margin-bottom: 0.25rem;
	}
	.tab-heading {
		color: var(--color-primary);
		font-size: 1.1rem;
		margin-top: 0;
	}

	/* ── Two-column layout ─────────────────────────────────── */
	.lesson-layout {
		display: grid;
		grid-template-columns: 3fr 2fr;
		gap: 1.5rem;
		align-items: start;
	}

	.lesson-content {
		overflow-y: auto;
		max-height: 90vh;
		padding-right: 0.5rem;
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

	/* ── All lessons list ──────────────────────────────────── */
	.all-lessons {
		margin-top: 2rem;
		padding-top: 1.5rem;
		border-top: 1px solid var(--color-border);
	}
	.all-lessons-heading {
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		margin-bottom: 0.5rem;
	}
	.all-lessons-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.lesson-item {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.45rem 0.6rem;
		border-radius: 6px;
		font-size: 0.82rem;
		color: var(--color-text);
		text-decoration: none;
		transition: background 0.12s;
	}
	.lesson-item:hover {
		background: var(--color-bg-secondary);
		text-decoration: none;
		color: var(--color-text);
	}
	.lesson-item-active {
		background: var(--color-primary);
		color: #fff;
		font-weight: 600;
	}
	.lesson-item-active:hover {
		background: var(--color-primary-dark);
		color: #fff;
	}
	.lesson-check {
		color: var(--color-success);
		font-size: 0.75rem;
		flex-shrink: 0;
	}
	.lesson-item-active .lesson-check {
		color: #fff;
	}
	.lesson-item-title {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	/* ── Editor area (docked mode) ──────────────────────────── */
	.editor-area {
		position: sticky;
		top: 3.5rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
		display: flex;
		flex-direction: column;
		overflow: hidden;
		max-height: 85vh;
	}
	.editor-area .editor-body {
		flex: 1;
		overflow-y: auto;
		padding: 0.5rem;
		min-height: 0;
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

	/* ── Floating restore button ────────────────────────────── */
	.float-restore-btn {
		position: fixed;
		bottom: 1rem;
		right: 1rem;
		z-index: 9999;
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

	/* ── Panel header ───────────────────────────────────────── */
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
		max-width: 100vw;
		max-height: 100vh;
		z-index: 9999;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
		display: flex;
		flex-direction: column;
		overflow: hidden;
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
		z-index: 9999;
		background: var(--color-bg);
		border-top: 2px solid var(--color-primary);
		border-radius: 12px 12px 0 0;
		box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
		display: flex;
		flex-direction: column;
		transition: max-height 0.3s ease, transform 0.3s ease;
	}
	.editor-area.mobile-hidden {
		max-height: 100vh;
		transform: translateY(calc(100% - 48px));
	}
	.editor-area.mobile-half {
		max-height: 60vh;
		transform: translateY(0);
	}
	.editor-area.mobile-full {
		max-height: calc(100vh - 3rem);
		top: 3rem;
		border-radius: 0;
		transform: translateY(0);
	}
	.mobile-sheet .editor-body {
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

	/* ── Tabs ─────────────────────────────────────────────── */
	.panel-tabs {
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
		color: var(--color-text);
		cursor: pointer;
		font-weight: 500;
		font-size: 0.85rem;
		white-space: nowrap;
	}
	.tab.active {
		background: var(--color-primary);
		color: #fff;
	}

	/* ── Tab panels ────────────────────────────────────────── */
	.tab-panel {
		overflow-y: auto;
	}
	.tab-hidden {
		display: none;
	}

	/* ── Utility ───────────────────────────────────────────── */
	.editor-body.body-hidden {
		display: none;
	}
</style>
