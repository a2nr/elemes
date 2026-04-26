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
	import { VelxioBridge, type EvaluationResult } from '$services/velxio-bridge';
	import { auth, authLoggedIn } from '$stores/auth';
	import { lessonContext } from '$stores/lessonContext';
	import { noSelect } from '$actions/noSelect';
	import { createFloatingPanel } from '$actions/floatingPanel.svelte';
	import { highlightAllCode } from '$actions/highlightCode';
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

	/** Try to directly read Velxio Zustand stores from iframe (same-origin). */
	function getVelxioState(): { code: string; circuit: string } | null {
		if (!velxioIframe) return null;
		try {
			const win = velxioIframe.contentWindow as any;
			if (!win) return null;
			
			const editorStore = win.__VELXIO_EDITOR_STORE__?.getState?.();
			const simStore = win.__VELXIO_SIMULATOR_STORE__?.getState?.();
			
			if (!editorStore || !simStore) return null;
			
			// Extract code
			const code = (editorStore.files as any[] || []).map((f: any) => f.content).join('\n');
			
			// Extract circuit state (Diagram format compatible with elemes:load_circuit)
			const circuit = {
				board: simStore.activeBoardId,
				components: (simStore.components as any[] || []).map(c => ({
					type: c.metadataId,
					id: c.id,
					x: c.x,
					y: c.y,
					rotation: c.properties?.rotation || 0,
					props: { ...c.properties }
				})),
				wires: simStore.wires || []
			};
			
			return {
				code,
				circuit: JSON.stringify(circuit)
			};
		} catch {
			return null;
		}
	}

	// Auto-save Velxio state periodically
	$effect(() => {
		if (velxioReady && $authLoggedIn && !showSolution) {
			const interval = setInterval(() => {
				const state = getVelxioState();
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

	// Apply syntax highlighting + circuit embeds after content renders
	$effect(() => {
		if (data) {
			tick().then(() => {
				if (contentEl) {
					highlightAllCode(contentEl);
					renderCircuitEmbeds(contentEl);
					autoRenderMath(contentEl);
				}
				if (tabsEl) {
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
					if (!checkAllPassed()) circuitOut.output += '\n⏳ Selesaikan juga tantangan kode untuk menyelesaikan pelajaran ini.';
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
				const currentCCode = (currentLanguage === 'c') ? code : cCode;
				const currentPythonCode = (currentLanguage === 'python') ? code : pythonCode;
				const mergedCode = currentCCode + '\n' + currentPythonCode;
				const passed = res.output.trim() === data.expected_output.trim() && checkKeyText(mergedCode, data.key_text ?? '');
				if (passed) {
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
							// To avoid logic flipping
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

	/** Match serial output using subsequence matching. */
	function matchSerialSubsequence(actual: string, expected: string): boolean {
		if (!expected) return true;
		if (!actual) return false;
		
		const actualLines = actual.split('\n').map(l => l.trim()).filter(l => l.length > 0);
		const expectedLines = expected.split('\n').map(l => l.trim()).filter(l => l.length > 0);
		
		let expectedIdx = 0;
		for (const actualLine of actualLines) {
			if (expectedIdx < expectedLines.length) {
				if (actualLine.toLowerCase().includes(expectedLines[expectedIdx].toLowerCase())) {
					expectedIdx++;
				}
			}
			if (expectedIdx === expectedLines.length) return true;
		}
		return expectedIdx === expectedLines.length;
	}

	function initVelxioBridge(iframe: HTMLIFrameElement) {
		velxioIframe = iframe;

		let settled = false;
		const onMessage = (e: MessageEvent) => {
			const type = e.data?.type;
			if (!type) return;

			if (!settled && type === 'velxio:ready') {
				settled = true;
				velxioBridge = new VelxioBridge(iframe);
				velxioReady = true;
				if (!data) return;
				velxioBridge.setEmbedMode({
					hideAuth: true,
					hideComponentPicker: true,
					lockComponents: true
				});
				
				// Priority: Restore from localStorage if available, otherwise use data from backend
				const savedCircuit = localStorage.getItem(arduinoCircuitKey);
				const savedCode = localStorage.getItem(arduinoCodeKey);

				if (savedCircuit) {
					console.log('[Velxio Bridge] Restoring circuit from draft');
					velxioBridge.loadCircuit(savedCircuit);
				} else if (data.velxio_circuit) {
					velxioBridge.loadCircuit(data.velxio_circuit);
				}

				if (savedCode) {
					console.log('[Velxio Bridge] Restoring code from draft');
					velxioBridge.loadCode([{ name: 'sketch.ino', content: savedCode }]);
				} else if (data.initial_code_arduino) {
					velxioBridge.loadCode([{ name: 'sketch.ino', content: data.initial_code_arduino }]);
				}
			}

			if (type === 'velxio:compile_result' && e.data.success) {
				const timeout = data?.evaluation_config?.timeout_ms ?? 5000;
				setTimeout(() => handleVelxioSubmit(), timeout);
			}
		};
		window.addEventListener('message', onMessage);

		// Fallback: if PostMessage bridge never connects, try direct iframe access (same-origin)
		const pollReady = setInterval(() => {
			if (settled) { clearInterval(pollReady); return; }
			try {
				const win = iframe.contentWindow as any;
				if (!win || !win.document) return;
				const root = win.document.getElementById('root');
				if (!root || !root.children.length) return;

				settled = true;
				clearInterval(pollReady);
				velxioReady = true;

				if (data) {
					win.postMessage({
						type: 'elemes:set_embed_mode',
						hideAuth: true,
						hideComponentPicker: true,
						lockComponents: true
					}, '*');
					
					const savedCircuit = localStorage.getItem(arduinoCircuitKey);
					const savedCode = localStorage.getItem(arduinoCodeKey);

					if (savedCircuit) {
						try {
							console.log('[Velxio Fallback] Restoring circuit from draft');
							const circuitData = JSON.parse(savedCircuit);
							win.postMessage({ type: 'elemes:load_circuit', ...circuitData }, '*');
						} catch {}
					} else if (data.velxio_circuit) {
						try {
							const circuitData = JSON.parse(data.velxio_circuit);
							win.postMessage({ type: 'elemes:load_circuit', ...circuitData }, '*');
						} catch {}
					}

					if (savedCode) {
						console.log('[Velxio Fallback] Restoring code from draft');
						win.postMessage({ type: 'elemes:load_code', files: [{ name: 'sketch.ino', content: savedCode }] }, '*');
					} else if (data.initial_code_arduino) {
						win.postMessage({ type: 'elemes:load_code', files: [{ name: 'sketch.ino', content: data.initial_code_arduino }] }, '*');
					}
				}
			} catch { /* cross-origin or not ready yet */ }
		}, 1000);

		setTimeout(() => {
			clearInterval(pollReady);
			if (settled) return;
			settled = true;
			window.removeEventListener('message', onMessage);
		}, 30_000);
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
			const state = getVelxioState();
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
			const messages: string[] = [];
			let keyTextPass: boolean | undefined;
			let serialPass: boolean | undefined;
			let wiringPass: boolean | undefined;

			// 1. Key text
			if (data.key_text) {
				const keys = data.key_text.split('\n').map(k => k.trim()).filter(k => k.length > 0);
				keyTextPass = keys.every(key => sourceCode.includes(key));
				messages.push(keyTextPass
					? '✅ Kata kunci ditemukan dalam kode'
					: '❌ Kata kunci belum ada dalam kode');
				dbg.push(`[key_text] keys="${keys.join(', ')}" → ${keyTextPass}`);
			}

			// 2. Serial output
			if (data.expected_serial_output) {
				const actualLog = serialLog.trim();
				const expectedLog = data.expected_serial_output.trim();
				
				// Use subsequence matching: expected lines must appear in order in actual output
				serialPass = matchSerialSubsequence(actualLog, expectedLog);
				
				messages.push(serialPass
					? '✅ Serial output sesuai'
					: '❌ Serial output belum sesuai');
				
				const preview = serialLog.substring(0, 150).replace(/\n/g, '↵');
				dbg.push(`[serial] actual(${serialLog.length}ch)="${preview}"`);
				dbg.push(`[serial] expected="${expectedLog.substring(0, 150).replace(/\n/g, '↵')}" → ${serialPass}`);
			}

			// 3. Wiring
			if (data.expected_wiring) {
				let expectedWires: any[] = [];
				try {
					const parsed = JSON.parse(data.expected_wiring);
					// Support both old format (array of pairs) and new format (object with wires array)
					if (Array.isArray(parsed)) {
						expectedWires = parsed;
					} else if (parsed.wires && Array.isArray(parsed.wires)) {
						expectedWires = parsed.wires;
					}
				} catch {}

				// Detect non-polarized component types (pins are interchangeable)
				const nonPolarizedTypes = new Set(['resistor']);

				// Normalize power pin names (e.g., GND.2 → GND, VCC.1 → VCC)
				// This handles multiple power pin variants
				const normalizePin = (pin: string) => {
					// Match power pins with numeric suffixes: GND.1, VCC.2, 5V.3, etc.
					return pin.replace(/^(GND|VCC|5V|3V3|3\.3V|POWER)\.\d+$/i, '$1');
				};

				// Normalize component:pin for comparison
				// For non-polarized components (like resistors), strip pin numbers
				// so that resistor:1 and resistor:2 are treated as equivalent
				const normalizeEdge = (compId: string, pinName: string): string => {
					const normPin = normalizePin(pinName);
					// Check if this component is non-polarized by looking at expected_wires
					// We detect resistor components by their ID pattern or type
					const isNonPolarized = nonPolarizedTypes.has(compId.split('-')[0]) ||
						compId.startsWith('resistor');
					if (isNonPolarized && /^\d+$/.test(normPin)) {
						// For non-polarized components with numeric pins, use a generic pin name
						return `${compId}:PIN`;
					}
					return `${compId}:${normPin}`;
				};

				const norm = (a: string, b: string) => {
					// Parse component:pin format
					const [compA, pinA] = a.split(':');
					const [compB, pinB] = b.split(':');
					const normA = `${compA}:${normalizePin(pinA || '')}`;
					const normB = `${compB}:${normalizePin(pinB || '')}`;
					// For non-polarized components, normalize numeric pins to generic
					const finalA = nonPolarizedTypes.has(compA) || compA.startsWith('resistor')
						? `${compA}:PIN` : normA;
					const finalB = nonPolarizedTypes.has(compB) || compB.startsWith('resistor')
						? `${compB}:PIN` : normB;
					// Sort to make edge comparison order-independent
					return [finalA, finalB].sort().join('↔');
				};

				const studentEdges = new Set(
					wireList.map(w => norm(
						`${w.start.componentId}:${w.start.pinName}`,
						`${w.end.componentId}:${w.end.pinName}`
					))
				);

				// Check all expected connections exist
				wiringPass = expectedWires.every((expected: any) => {
					let edgeKey: string;
					// Handle both formats
					if (Array.isArray(expected) && expected.length === 2) {
						// Old format: ["component:pin", "component:pin"]
						edgeKey = norm(expected[0], expected[1]);
					} else if (expected.start && expected.end) {
						// New format: { start: { componentId, pinName }, end: { componentId, pinName } }
						const startPin = `${expected.start.componentId}:${expected.start.pinName}`;
						const endPin = `${expected.end.componentId}:${expected.end.pinName}`;
						edgeKey = norm(startPin, endPin);
					} else {
						return false;
					}

					const exists = studentEdges.has(edgeKey);
					if (!exists) {
						dbg.push(`[wiring] MISSING: ${edgeKey}`);
					}
					return exists;
				});

				messages.push(wiringPass
					? '✅ Rangkaian wiring benar'
					: '❌ Wiring belum sesuai');

				const edgesStr = wireList.map(w =>
					`${w.start.componentId}:${w.start.pinName}↔${w.end.componentId}:${w.end.pinName}`
				);
				dbg.push(`[wiring] student (${wireList.length} wires): ${edgesStr.join(' | ') || '(kosong)'}`);
				dbg.push(`[wiring] expected (${expectedWires.length} connections): ${expectedWires.map((w: any) => {
					if (Array.isArray(w) && w.length === 2) return w.join('↔');
					if (w.start && w.end) return `${w.start.componentId}:${w.start.pinName}↔${w.end.componentId}:${w.end.pinName}`;
					return JSON.stringify(w);
				}).join(' | ')}`);
				dbg.push(`[wiring] result → ${wiringPass}`);
			}

			const checks = [keyTextPass, serialPass, wiringPass].filter(v => v !== undefined);
			const pass = checks.length > 0 && checks.every(Boolean);

			velxioOut.output = messages.join('\n');
			velxioOut.debug = dbg;
			velxioOut.success = pass;

			if (pass) {
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

				<!-- Velxio (Arduino) tab panel -->
				{#if isVelxio}
				<div class="tab-panel velxio-panel" class:tab-hidden={activeTab !== 'velxio'}>
					{#if velxioError}
						<div class="velxio-fallback">
							Simulator Arduino sedang tidak tersedia.
							Hubungi guru jika masalah berlanjut.
						</div>
					{:else}
						{#if $authLoggedIn}
							<div class="storage-indicator-inline" title={velxioSaving ? "Menyimpan draf..." : "Draf tersimpan di browser"}>
								<span class="indicator-icon" class:saving={velxioSaving}>
									{velxioSaving ? '●' : '☁'}
								</span>
								<span class="indicator-text">Auto-save</span>
							</div>
						{/if}
						<!-- svelte-ignore a11y_missing_attribute -->
						<iframe
							class="velxio-iframe"
							src="/velxio/editor?embed=true{hasArduinoCode ? '' : '&hideEditor=true'}&lockComponents=true"
							onload={(e) => initVelxioBridge(e.currentTarget as HTMLIFrameElement)}
							allow="cross-origin-isolated"
						></iframe>
					{/if}
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
		display: flex;
		flex-direction: column;
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
	.btn-run-all {
		padding: 0.3rem 0.6rem;
		font-size: 0.8rem;
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
		height: 70vh;
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

	/* ── Velxio (Arduino simulator) ─────────────────────── */
	.storage-indicator-inline {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 0.75rem;
		color: var(--color-text-muted);
		background: var(--color-bg-secondary);
		padding: 3px 10px;
		border-radius: 12px;
		border: 1px solid var(--color-border);
		position: absolute;
		bottom: 1rem;
		right: 1.5rem;
		z-index: 10;
		box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15);
		pointer-events: none;
		opacity: 0.8;
	}
	.storage-indicator-inline .indicator-icon {
		line-height: 1;
		font-size: 0.8rem;
		color: var(--color-success);
	}
	.storage-indicator-inline .indicator-icon.saving {
		color: var(--color-primary);
		animation: pulse 1s infinite;
	}
	.storage-indicator-inline .indicator-text {
		font-weight: 500;
	}

	.velxio-panel {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-height: 0;
		position: relative;
	}
	.velxio-panel.tab-hidden {
		display: none;
	}
	.velxio-iframe {
		flex: 1;
		width: 100%;
		min-height: 400px;
		border: none;
		border-radius: var(--radius);
	}
	.velxio-fallback {
		padding: 2rem;
		text-align: center;
		color: var(--color-text-muted);
		background: var(--color-bg-secondary);
		border-radius: var(--radius);
		margin: 0.5rem 0;
	}

</style>
