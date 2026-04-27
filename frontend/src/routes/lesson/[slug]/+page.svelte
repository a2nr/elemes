<script lang="ts">
	import './lesson.css';
	import { page } from '$app/stores';
	import { beforeNavigate } from '$app/navigation';
	import CodeEditor from '$components/CodeEditor.svelte';
	import CircuitEditor from '$components/CircuitEditor.svelte';
	import CodeTab from './CodeTab.svelte';
	import CircuitTab from './CircuitTab.svelte';
	import VelxioTab from './VelxioTab.svelte';
	import OutputPanel, { type OutputEntry } from '$components/OutputPanel.svelte';
	import CelebrationOverlay from '$components/CelebrationOverlay.svelte';
	import WorkspaceHeader from '$components/WorkspaceHeader.svelte';
	import LessonList from '$components/LessonList.svelte';
	import { compileCode, trackProgress } from '$services/api';
	import { checkKeyText, validateNodes } from '$services/exercise';
	import { evaluateVelxioSubmission } from '$services/velxio-evaluator';
	import { evaluateCircuitSubmission, processLanguageEvaluation } from '$services/evaluators';
	import { getVelxioState, initVelxioBridge } from '$services/velxio-manager';
	import { VelxioBridge, type EvaluationResult } from '$services/velxio-bridge';
	import { auth, authLoggedIn } from '$stores/auth';
	import { lessonContext } from '$stores/lessonContext';
	import { noSelect } from '$actions/noSelect';
	import { createFloatingPanel } from '$actions/floatingPanel.svelte';
	import { highlightAllCode } from '$actions/highlightCode';
	import { setupTryButtons } from '$actions/setupTryButtons';
	import { renderCircuitEmbeds } from '$actions/renderCircuitEmbeds';
	import { renderMath, autoRenderMath } from '$lib/actions/renderMath';
	import { tick, untrack } from 'svelte';
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
	const freshOutput = () => ({ output: '', error: '', loading: false, success: null as boolean | null, debug: undefined as string[] | undefined });
	let cOut = $state(freshOutput());
	let pyOut = $state(freshOutput());
	let circuitOut = $state(freshOutput());

	// Helper: get the active code output object for current language
	function getCodeOut() { return currentLanguage === 'python' ? pyOut : cOut; }

	let cPassed = $state(false);
	let pythonPassed = $state(false);
	let circuitPassed = $state(false);

	// Velxio (Arduino simulator) state
	let isVelxio = $derived(data?.active_tabs?.includes('velxio') ?? false);
	let velxioBridge = $state<VelxioBridge | null>(null);
	let velxioReady = $state(false);
	let velxioSaving = $state(false);
	let velxioError = $state(false);
	let velxioIframe = $state<HTMLIFrameElement | null>(null);
	let velxioOut = $state(freshOutput());
	let hasArduinoCode = $derived(!!data?.initial_code_arduino);

	// Velxio storage keys
	let arduinoCodeKey = $derived(`elemes_arduino_code_${slug}`);
	let arduinoCircuitKey = $derived(`elemes_arduino_circuit_${slug}`);

	// Auto-save Velxio state periodically
	$effect(() => {
		if (velxioReady && $authLoggedIn && !showSolution) {
			const interval = setInterval(() => {
				const state = getVelxioState(velxioIframe);
				if (!state) return;
				
				let changed = false;
				
				// 1. Source Code
				const savedCode = localStorage.getItem(arduinoCodeKey);
				if (state.code && state.code !== savedCode) {
					console.log('[Velxio Auto-save] Saving code changes (Zustand)');
					localStorage.setItem(arduinoCodeKey, state.code);
					changed = true;
				}

				// 2. Circuit (Diagram + Wires)
				const savedCircuit = localStorage.getItem(arduinoCircuitKey);
				if (state.circuit && state.circuit !== savedCircuit) {
					console.log('[Velxio Auto-save] Saving circuit changes (Zustand)');
					localStorage.setItem(arduinoCircuitKey, state.circuit);
					changed = true;
				}
				
				if (changed) {
					velxioSaving = true;
					setTimeout(() => { velxioSaving = false; }, 1500);
				}
			}, 7000); // Poll every 7 seconds
			
			return () => clearInterval(interval);
		}
	});

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
		if (tabs.includes('velxio')) {
			secs.push({ key: 'velxio', label: 'Arduino', icon: '\u{1F4DF}', data: velxioOut, placeholder: 'Klik "Compile & Run" untuk menjalankan kode', loadingText: 'Mengevaluasi...' });
		}
		return secs;
	});

	// UI state
	let showSolution = $state(false);
	let activeTab = $state<'info' | 'exercise' | 'editor' | 'circuit' | 'output' | 'velxio'>('info');

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
		const currentLesson = lesson; // capture dependency
		if (currentLesson) {
			untrack(() => {
				data = currentLesson;
				lessonCompleted = currentLesson.lesson_completed;

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
			velxioOut = freshOutput();
			cPassed = false;
			pythonPassed = false;
			circuitPassed = false;
			showSolution = false;

			// Cleanup previous Velxio bridge
			if (velxioBridge) { velxioBridge.destroy(); velxioBridge = null; }
			velxioReady = false;
			velxioError = false;
			const isVelxioLesson = lesson.active_tabs?.includes('velxio');
			if (lesson.lesson_info) activeTab = 'info';
			else if (lesson.exercise_content) activeTab = 'exercise';
			else if (isVelxioLesson) activeTab = 'velxio' as any;
			else if (lesson.active_tabs?.includes('circuit') && !hasC && !hasPython) activeTab = 'circuit';
			else activeTab = 'editor';
			mobileMode = 'half';

			// Populate navbar context
			lessonContext.set({
				title: lesson.lesson_title,
				completed: lesson.lesson_completed,
				prevLesson: lesson.prev_lesson,
				nextLesson: currentLesson.next_lesson
			});
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

	// Clear lesson context and Velxio bridge when leaving page
	beforeNavigate(() => {
		lessonContext.set(null);
		if (velxioBridge) { velxioBridge.destroy(); velxioBridge = null; }
	});

	function handleTryCode(code: string, lang: string) {
		if (lang === 'python' || lang === 'c') {
			currentLanguage = lang;
			currentCode = code;
			if (lang === 'c') cCode = code;
			else pythonCode = code;
			editor?.setCode(code);
			activeTab = 'editor';
			if (!isMobile) {
				float.floating = true;
			} else {
				mobileMode = 'half';
				tick().then(() => {
					document.querySelector('.editor-area')?.scrollIntoView({ behavior: 'smooth' });
				});
			}
		} else if (lang === 'cpp') {
			if (isVelxio && velxioBridge) {
				velxioBridge.loadCode([{ name: 'sketch.ino', content: code }]);
				activeTab = 'velxio';
				if (!isMobile) {
					float.floating = true;
				} else {
					mobileMode = 'half';
					tick().then(() => {
						document.querySelector('.editor-area')?.scrollIntoView({ behavior: 'smooth' });
					});
				}
			}
		}
	}

	// Apply syntax highlighting + circuit embeds after content renders
	$effect(() => {
		if (data) {
			tick().then(() => {
				if (contentEl) {
					setupTryButtons(contentEl, handleTryCode);
					highlightAllCode(contentEl);
					renderCircuitEmbeds(contentEl);
					autoRenderMath(contentEl);
				}
				if (tabsEl) {
					setupTryButtons(tabsEl, handleTryCode);
					highlightAllCode(tabsEl);
					renderCircuitEmbeds(tabsEl);
					autoRenderMath(tabsEl);
				}
			});
		}
	});

	/** Mark lesson as complete: track progress + celebration. Called when ALL exercises pass. */
	async function completeLesson() {
		if (lessonCompleted) return;
		showCelebration = true;
		if (auth.isLoggedIn) {
			const lessonName = slug.replace('.md', '');
			await trackProgress(auth.token, lessonName);
			lessonCompleted = true;
			lessonContext.update(ctx => ctx ? { ...ctx, completed: true } : ctx);
		}
	}

	/** Check if all exercise types for this lesson have passed (AND logic). */
	function checkAllPassed(): boolean {
		const needsC = data?.active_tabs?.includes('c');
		const needsPython = data?.active_tabs?.includes('python');
		const needsCircuit = data?.active_tabs?.includes('circuit');
		
		if (!data?.active_tabs?.length) return true;

		if (needsC && !cPassed) return false;
		if (needsPython && !pythonPassed) return false;
		if (needsCircuit && !circuitPassed) return false;
		
		return true;
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
			const circuitText = circuitEditor.getCircuitText();
			const res = evaluateCircuitSubmission(simApi, circuitText, isHybrid, data, checkAllPassed);

			if (res.error) {
				Object.assign(circuitOut, { error: res.error, success: false, loading: false });
				return;
			}

			circuitOut.output = res.output;
			circuitOut.success = res.pass;

			if (res.pass) {
				circuitPassed = true;
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

	async function evaluateLanguage(lang: 'c' | 'python') {
		if (!data) return;

		const out = lang === 'c' ? cOut : pyOut;
		Object.assign(out, { loading: true, output: '', error: '', success: null });
		activeTab = 'output';

		try {
			const code = (currentLanguage === lang) ? (editor?.getCode() ?? currentCode) : (lang === 'c' ? cCode : pythonCode);
			const res = await compileCode({ code, language: lang, token: auth.token });

			if (!res.success) {
				Object.assign(out, { error: res.error || 'Compilation failed', success: false });
				return;
			}

			out.output = res.output;
			out.success = true;

			if (data.expected_output) {
				const { isCorrect } = processLanguageEvaluation(res.output, code, lang, currentLanguage, cCode, pythonCode, data);
				if (isCorrect) {
					if (lang === 'c') cPassed = true;
					else if (lang === 'python') pythonPassed = true;

					if (!checkAllPassed()) {
						out.output += '\n✅ Kode benar!\n⏳ Selesaikan juga tantangan di tab lainnya untuk menyelesaikan pelajaran ini.';
					} else {
						out.output += '\n🎉 Semuanya benar!';
					}

					if (checkAllPassed()) {
						await completeLesson();
						if (data.solution_code || data.solution_python || data.solution_circuit) { 
							showSolution = true;
							handleShowSolution();
							showSolution = true; 
						}
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

	async function handleRun() {
		if (activeTab === 'circuit') { await evaluateCircuit(); return; }
		if (!data) return;

		activeTab = 'output';
		await evaluateLanguage(currentLanguage as 'c' | 'python');
	}

	async function handleRunAll() {
		if (!data) return;
		activeTab = 'output';

		const tabs = data.active_tabs ?? [];
		const hasC = tabs.includes('c') || (!tabs.length && !tabs.includes('python'));
		const hasPython = tabs.includes('python');

		if (hasC) await evaluateLanguage('c');
		if (hasPython) await evaluateLanguage('python');
		if (tabs.includes('circuit')) await evaluateCircuit();
		if (tabs.includes('velxio')) await handleVelxioSubmit();
	}

	function handleReset() {
		if (!data) return;
		if (activeTab === 'circuit') {
			circuitEditor?.setCircuitText(data.initial_circuit || data.initial_code);
			Object.assign(circuitOut, freshOutput());
		} else if (activeTab === 'velxio') {
			console.log('[Velxio Reset] Clearing drafts and reloading initial state');
			localStorage.removeItem(arduinoCodeKey);
			localStorage.removeItem(arduinoCircuitKey);
			if (data.initial_code_arduino) {
				velxioBridge?.loadCode([{ name: 'sketch.ino', content: data.initial_code_arduino }]);
			}
			if (data.velxio_circuit) {
				velxioBridge?.loadCircuit(data.velxio_circuit);
			}
			Object.assign(velxioOut, freshOutput());
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
		if (!data) return;
		if (!data.solution_code && !data.solution_circuit && !data.solution_python) return;
		
		showSolution = !showSolution;
		if (showSolution) {
			// Update Circuit if exists
			if (data.active_tabs?.includes('circuit') && data.solution_circuit) {
				circuitEditor?.setCircuitText(data.solution_circuit);
			}
			// Update Code Editor
			if (currentLanguage === 'python' && data.solution_python) {
				editor?.setCode(data.solution_python);
			} else if (data.solution_code) {
				editor?.setCode(data.solution_code);
			}
		} else {
			// Restore Circuit if exists
			if (data.active_tabs?.includes('circuit') && data.initial_circuit) {
				circuitEditor?.setCircuitText(data.initial_circuit);
			}
			// Restore Code Editor to their working code
			if (currentLanguage === 'python' || currentLanguage === 'c' || data.initial_code) {
				editor?.setCode(currentCode);
			}
		}
	}

	function setupVelxioBridge(iframe: HTMLIFrameElement) {
		velxioIframe = iframe;
		initVelxioBridge(
			iframe,
			data,
			arduinoCircuitKey,
			arduinoCodeKey,
			(bridge) => {
				velxioBridge = bridge;
				velxioReady = true;
			},
			() => handleVelxioSubmit()
		);
	}

	async function handleVelxioSubmit() {
		if (!data) return;

		Object.assign(velxioOut, { loading: true, output: 'Mengevaluasi...', error: '', success: null });
		activeTab = 'output';

		try {
			// === Gather data ===
			let sourceCode = '';
			let serialLog = '';
			let wireList: any[] = [];
			const dbg: string[] = [];

			// Try PostMessage bridge first for serial log (since it's harder to get from store)
			if (velxioBridge) {
				const serResp = await velxioBridge['request']('elemes:get_serial_log', 'velxio:serial_log');
				if (serResp) serialLog = serResp.log as string;
			}

			// Use getVelxioState for code and wires (more reliable/complete)
			const state = getVelxioState(velxioIframe);
			if (state) {
				sourceCode = state.code;
				try {
					const circuit = JSON.parse(state.circuit);
					wireList = circuit.wires || [];
				} catch {}
				dbg.push('[metode: Zustand store]');
			} else {
				dbg.push('[!] Gagal mengakses simulator state');
			}

			// === Evaluate ===
			const evalRes = evaluateVelxioSubmission(sourceCode, serialLog, wireList, data);

			velxioOut.output = evalRes.messages.join('\n');
			velxioOut.debug = dbg.concat(evalRes.dbg);
			velxioOut.success = evalRes.pass;

			if (evalRes.pass) {
				await completeLesson();
				setTimeout(() => { showCelebration = false; activeTab = 'velxio'; }, 3000);
			}
		} catch (err: any) {
			Object.assign(velxioOut, { error: `Evaluasi gagal: ${err.message}`, success: false });
		} finally {
			velxioOut.loading = false;
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
		<div class="lesson-content" bind:this={contentEl} use:noSelect use:renderMath
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
			<div class="editor-body" bind:this={tabsEl} use:renderMath>

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
					<CircuitTab
						{data}
						bind:circuitEditor
						compiling={compiling}
						authLoggedIn={$authLoggedIn}
						lessonCompleted={lessonCompleted}
						showSolution={showSolution}
						slug={slug}
						onRun={handleRun}
						onReset={handleReset}
						onShowSolution={handleShowSolution}
					/>
				</div>
				{/if}

				<!-- Velxio (Arduino) tab panel -->
				{#if isVelxio}
				<div class="tab-panel velxio-panel" class:tab-hidden={activeTab !== 'velxio'}>
					<VelxioTab
						{hasArduinoCode}
						velxioError={velxioError}
						authLoggedIn={$authLoggedIn}
						velxioSaving={velxioSaving}
						onSetupBridge={setupVelxioBridge}
					/>
				</div>
				{/if}

				<!-- Editor tab panel -->
				{#if !data.active_tabs || data.active_tabs.length === 0 || data.active_tabs.includes('c') || data.active_tabs.includes('python')}
				<div class="tab-panel" class:tab-hidden={activeTab !== 'editor'}>
					<CodeTab
						{data}
						bind:currentLanguage
						bind:currentCode
						bind:editor
						compiling={compiling}
						authLoggedIn={$authLoggedIn}
						lessonCompleted={lessonCompleted}
						showSolution={showSolution}
						slug={slug}
						onRun={handleRun}
						onReset={handleReset}
						onShowSolution={handleShowSolution}
					/>
				</div>
				{/if}

				<!-- Output tab panel -->
				<div class="tab-panel" class:tab-hidden={activeTab !== 'output'}>
					<OutputPanel sections={outputSections}>
						{#snippet actions()}
							<button class="btn btn-success btn-sm btn-run-all" onclick={handleRunAll} disabled={compiling}>
								{compiling ? 'Mengevaluasi...' : '▶ Run Keseluruhan'}
							</button>
						{/snippet}
					</OutputPanel>
				</div>
			</div>

			<CelebrationOverlay visible={showCelebration} />
		</div>
	</div>

{/if}

