<script lang="ts">
	import { page } from '$app/stores';
	import { beforeNavigate } from '$app/navigation';
	import CodeEditor from '$components/CodeEditor.svelte';
	import CircuitEditor from '$components/CircuitEditor.svelte';
	import OutputPanel, { type OutputEntry } from '$components/OutputPanel.svelte';
	import CelebrationOverlay from '$components/CelebrationOverlay.svelte';
	import WorkspaceHeader from '$components/WorkspaceHeader.svelte';
	import LessonList from '$components/LessonList.svelte';
	import { compileCode, trackProgress } from '$services/api';
	import { checkKeyText, validateNodes } from '$services/exercise';
	import { auth, authLoggedIn } from '$stores/auth';
	import { lessonContext } from '$stores/lessonContext';
	import { noSelect } from '$actions/noSelect';
	import { createFloatingPanel } from '$actions/floatingPanel.svelte';
	import { highlightAllCode } from '$actions/highlightCode';
	import { renderCircuitEmbeds } from '$actions/renderCircuitEmbeds';
	import { tick } from 'svelte';
	import type { LessonContent } from '$types/lesson';

	// Data from +page.ts load function (SSR + client)
	let { data: pageData } = $props();

	// Derive lesson reactively so navigation updates propagate
	let lesson = $derived(pageData.lesson);

	let data = $state<LessonContent | null>(null);
	let lessonCompleted = $state(false);
	let currentCode = $state('');
	let currentLanguage = $state<string>('c');

	// Per-language code tracking
	let cCode = $state('');
	let pythonCode = $state('');

	// Output state per language + circuit
	const freshOutput = () => ({ output: '', error: '', loading: false, success: null as boolean | null });
	let cOut = $state(freshOutput());
	let pyOut = $state(freshOutput());
	let circuitOut = $state(freshOutput());

	// Helper: get the active code output object for current language
	function getCodeOut() { return currentLanguage === 'python' ? pyOut : cOut; }

	// AND-logic: track whether each exercise type has passed (persists across runs)
	let codePassed = $state(false);
	let circuitPassed = $state(false);

	// Derived: is this a hybrid lesson (has both code and circuit)?
	let isHybrid = $derived(
		(data?.active_tabs?.includes('c') || data?.active_tabs?.includes('python')) &&
		data?.active_tabs?.includes('circuit')
	);

	// Derived: any loading state (for disabling Run button)
	let compiling = $derived(cOut.loading || pyOut.loading || circuitOut.loading);

	// Build output sections for OutputPanel
	let outputSections = $derived.by(() => {
		const tabs = data?.active_tabs ?? [];
		const secs: OutputEntry[] = [];
		if (tabs.includes('c') || (!tabs.length && !tabs.includes('python'))) {
			secs.push({ key: 'c', label: 'C', icon: '\u{1F4BB}', data: cOut, placeholder: 'Klik "Run" untuk menjalankan kode C', loadingText: 'Mengompilasi C...' });
		}
		if (tabs.includes('python')) {
			secs.push({ key: 'python', label: 'Python', icon: '\u{1F40D}', data: pyOut, placeholder: 'Klik "Run" untuk menjalankan kode Python', loadingText: 'Menjalankan Python...' });
		}
		if (tabs.includes('circuit')) {
			secs.push({ key: 'circuit', label: 'Circuit', icon: '\u26A1', data: circuitOut, placeholder: 'Klik "Cek Rangkaian" untuk mengevaluasi', loadingText: 'Mengevaluasi rangkaian...' });
		}
		return secs;
	});

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

	const slug = $derived($page.params.slug);

	// Sync lesson data when navigating between lessons
	$effect(() => {
		if (lesson) {
			data = lesson;
			lessonCompleted = lesson.lesson_completed;

			// Initialize per-language code
			cCode = lesson.initial_code_c || '';
			pythonCode = lesson.initial_python || '';

			// Determine initial language (use local var to avoid reactive dependency on currentLanguage)
			const hasC = lesson.active_tabs?.includes('c');
			const hasPython = lesson.active_tabs?.includes('python');
			const initLang = (hasPython && !hasC) ? 'python' : 'c';
			currentLanguage = initLang;
			prevLanguage = initLang;
			currentCode = initLang === 'python' ? pythonCode : (cCode || lesson.initial_code || '');

			cOut = freshOutput();
			pyOut = freshOutput();
			circuitOut = freshOutput();
			codePassed = false;
			circuitPassed = false;
			showSolution = false;
			if (lesson.lesson_info) activeTab = 'info';
			else if (lesson.exercise_content) activeTab = 'exercise';
			else if (lesson.active_tabs?.includes('circuit') && !hasC && !hasPython) activeTab = 'circuit';
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

	// Switch editor content when language tab changes
	let prevLanguage = $state<string>('c');
	$effect(() => {
		if (!data || currentLanguage === prevLanguage) return;
		// Save current code to the previous language slot
		const code = editor?.getCode() ?? currentCode;
		if (prevLanguage === 'c') cCode = code;
		else if (prevLanguage === 'python') pythonCode = code;
		// Load code for the new language
		const newCode = currentLanguage === 'python' ? pythonCode : (cCode || data.initial_code || '');
		currentCode = newCode;
		editor?.setCode(newCode);
		prevLanguage = currentLanguage;
	});

	// Clear lesson context when leaving page
	beforeNavigate(() => {
		lessonContext.set(null);
	});

	// Apply syntax highlighting + circuit embeds after content renders
	$effect(() => {
		if (data) {
			tick().then(() => {
				if (contentEl) {
					highlightAllCode(contentEl);
					renderCircuitEmbeds(contentEl);
				}
				if (tabsEl) {
					highlightAllCode(tabsEl);
					renderCircuitEmbeds(tabsEl);
				}
			});
		}
	});

	/** Mark lesson as complete: track progress + celebration. Called when ALL exercises pass. */
	async function completeLesson() {
		showCelebration = true;
		if (auth.isLoggedIn) {
			const lessonName = slug.replace('.md', '');
			await trackProgress(auth.token, lessonName);
			lessonCompleted = true;
			lessonContext.update(ctx => ctx ? { ...ctx, completed: true } : ctx);
		}
	}

	/** For hybrid lessons, check if all exercise types have passed (AND logic). */
	function checkAllPassed(): boolean {
		if (!isHybrid) return true; // not hybrid, each evaluator handles itself
		return codePassed && circuitPassed;
	}

	async function evaluateCircuit() {
		if (!data || !circuitEditor) return;
		const simApi = circuitEditor.getApi();
		if (!simApi) {
			Object.assign(circuitOut, { error: "Simulator belum siap.", success: false });
			activeTab = 'output';
			return;
		}

		Object.assign(circuitOut, { loading: true, output: 'Mengevaluasi rangkaian...', error: '', success: null });
		activeTab = 'output';

		try {
			const circuitExpected = (isHybrid && data.expected_circuit_output)
				? data.expected_circuit_output
				: data.expected_output;

			let expectedState: any = null;
			try {
				if (circuitExpected) expectedState = JSON.parse(circuitExpected);
			} catch {
				Object.assign(circuitOut, { error: "Format EXPECTED_OUTPUT tidak valid (Harus JSON).", success: false, loading: false });
				return;
			}

			if (!expectedState) {
				Object.assign(circuitOut, { output: "Tidak ada kriteria evaluasi yang ditetapkan.", success: true, loading: false });
				return;
			}

			let { allPassed, messages } = expectedState.nodes
				? validateNodes(simApi, expectedState.nodes)
				: { allPassed: true, messages: [] as string[] };

			const circuitText = circuitEditor.getCircuitText();
			const circuitKeyText = (isHybrid && data.key_text_circuit) ? data.key_text_circuit : data.key_text;
			if (!checkKeyText(circuitText, circuitKeyText ?? '')) {
				allPassed = false;
				messages.push(`❌ Komponen wajib belum lengkap (lihat instruksi).`);
			}

			circuitOut.output = messages.join('\n');
			circuitOut.success = allPassed;

			if (allPassed) {
				circuitPassed = true;
				if (isHybrid) {
					circuitOut.output += '\n✅ Rangkaian benar!';
					if (!codePassed) circuitOut.output += '\n⏳ Selesaikan juga tantangan kode untuk menyelesaikan pelajaran ini.';
				}
				if (checkAllPassed()) {
					await completeLesson();
					setTimeout(() => { showCelebration = false; activeTab = 'circuit'; }, 3000);
				}
			}
		} catch (err: any) {
			Object.assign(circuitOut, { error: `Evaluasi gagal: ${err.message}`, success: false });
		} finally {
			circuitOut.loading = false;
		}
	}

	async function handleRun() {
		if (activeTab === 'circuit') { await evaluateCircuit(); return; }
		if (!data) return;

		const out = getCodeOut();
		Object.assign(out, { loading: true, output: '', error: '', success: null });
		activeTab = 'output';

		try {
			const code = editor?.getCode() ?? currentCode;
			const res = await compileCode({ code, language: currentLanguage });

			if (!res.success) {
				Object.assign(out, { error: res.error || 'Compilation failed', success: false });
				return;
			}

			out.output = res.output;
			out.success = true;

			if (data.expected_output) {
				const passed = res.output.trim() === data.expected_output.trim() && checkKeyText(code, data.key_text ?? '');
				if (passed) {
					codePassed = true;
					if (isHybrid && !circuitPassed) {
						out.output += '\n✅ Kode benar!\n⏳ Selesaikan juga tantangan rangkaian untuk menyelesaikan pelajaran ini.';
					}
					if (checkAllPassed()) {
						await completeLesson();
						if (data.solution_code) { showSolution = true; editor?.setCode(data.solution_code); }
						setTimeout(() => { showCelebration = false; activeTab = 'editor'; }, 3000);
					}
				}
			}
		} catch {
			Object.assign(out, { error: 'Gagal terhubung ke server', success: false });
		} finally {
			out.loading = false;
		}
	}

	function handleReset() {
		if (!data) return;
		if (activeTab === 'circuit') {
			circuitEditor?.setCircuitText(data.initial_circuit || data.initial_code);
			Object.assign(circuitOut, freshOutput());
		} else {
			const resetCode = currentLanguage === 'python'
				? (data.initial_python || '')
				: (data.initial_code_c || data.initial_code || '');
			currentCode = resetCode;
			if (currentLanguage === 'c') cCode = resetCode;
			else pythonCode = resetCode;
			editor?.setCode(resetCode);
			Object.assign(getCodeOut(), freshOutput());
		}
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

			<LessonList lessons={data.ordered_lessons ?? []} currentSlug={slug} />
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

			<WorkspaceHeader
				{isMobile}
				bind:mobileMode
				bind:activeTab
				bind:currentLanguage
				hasInfo={!!data.lesson_info}
				hasExercise={!!data.exercise_content}
				activeTabs={data.active_tabs ?? []}
				floating={float.floating}
				minimized={float.minimized}
				onDragStart={float.onDragStart}
				onResizeStart={float.onResizeStart}
				onFloatToggle={float.toggle}
				onMinimize={float.minimize}
			/>

			<!-- Editor body -->
			<div class="editor-body" bind:this={tabsEl}>

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
						<span class="lang-label">{currentLanguage === 'python' ? 'Python' : 'C'}</span>
					</div>

					<div class="panel">
						{#key currentLanguage}
						<CodeEditor
							bind:this={editor}
							code={currentCode}
							language={currentLanguage}
							noPaste={true}
							storageKey={($authLoggedIn && !showSolution) ? `elemes_draft_${slug}_${currentLanguage}` : undefined}
							onchange={(val) => { if (!showSolution) currentCode = val; }}
						/>
						{/key}
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
					<OutputPanel sections={outputSections} />
				</div>
			</div>

			<CelebrationOverlay visible={showCelebration} />
		</div>
	</div>

{/if}

<style>
	/* ── Shared rich-text styles (.prose + .tab-content) ──── */
	.tab-content {
		font-size: 0.85rem;
		padding: 0.75rem 0.5rem;
		line-height: 1.65;
	}
	.tab-heading {
		color: var(--color-primary);
		font-size: 1.1rem;
		margin-top: 0;
	}
	.prose :global(pre),
	.tab-content :global(pre) {
		background: var(--color-bg-secondary);
		padding: 0.75rem;
		border-radius: var(--radius);
		overflow-x: auto;
	}
	.prose :global(code),
	.tab-content :global(code) {
		font-family: var(--font-mono);
		font-size: 0.85rem;
	}
	.prose :global(p),
	.tab-content :global(p) {
		margin-bottom: 0.75rem;
	}
	.prose :global(h2), .prose :global(h3),
	.tab-content :global(h2), .tab-content :global(h3) {
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
	.editor-area.floating-hidden {
		display: none !important;
	}

	/* ── Mobile bottom sheet ──────────────────────────────── */
	.editor-area.mobile-sheet {
		position: fixed;
		top: auto;
		bottom: 0;
		left: 0;
		right: 0;
		z-index: 9999;
		background: var(--color-bg);
		border-top: 2px solid var(--color-primary);
		border-radius: 12px 12px 0 0;
		box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
		display: flex;
		flex-direction: column;
		overflow: hidden;
		transition: height 0.3s cubic-bezier(0.4, 0, 0.2, 1), border-radius 0.2s ease;
	}
	.editor-area.mobile-hidden {
		height: 52px;
	}
	.editor-area.mobile-half {
		height: 60vh;
	}
	.editor-area.mobile-full {
		height: calc(100vh - 3rem);
		border-radius: 0;
	}
	.mobile-sheet .editor-body {
		overscroll-behavior: contain;
	}
	/* ── Mobile full: expand content to fill ────────────── */
	.editor-area.mobile-full .editor-body,
	.editor-area.mobile-full .tab-panel:not(.tab-hidden),
	.editor-area.mobile-full .panel,
	.editor-area.mobile-full :global(.circuit-container),
	.editor-area.mobile-full :global(.editor-wrapper) {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-height: 0;
	}
	.editor-area.mobile-full :global(.circuit-wrapper) {
		flex: 1;
		height: auto;
	}
	.editor-area.mobile-full :global(.cm-editor) {
		flex: 1;
		max-height: none;
		min-height: 0;
	}
	.editor-area.mobile-full :global(.cm-scroller) {
		flex: 1;
	}

	/* ── Tab panels ────────────────────────────────────────── */
	.tab-panel {
		overflow-y: auto;
	}
	.tab-hidden {
		display: none;
	}

</style>
