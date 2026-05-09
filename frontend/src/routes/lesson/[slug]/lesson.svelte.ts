import { page } from '$app/stores';
import { get } from 'svelte/store';
import { tick, untrack } from 'svelte';
import { auth, authLoggedIn } from '$stores/auth';
import { lessonContext } from '$stores/lessonContext';
import { compileCode, trackProgress } from '$services/api';
import { evaluateVelxioSubmission } from '$services/velxio-evaluator';
import { evaluateFlowchartSubmission } from '$services/flowchart-evaluator';
import { evaluateCircuitSubmission, processLanguageEvaluation } from '$services/evaluators';
import { getVelxioState, initVelxioBridge } from '$services/velxio-manager';
import { VelxioBridge } from '$services/velxio-bridge';
import type { LessonContent } from '$types/lesson';
import type { CodeEditor } from '$components/CodeEditor.svelte';
import type { CircuitEditor } from '$components/CircuitEditor.svelte';

export class LessonManager {
	data = $state<LessonContent | null>(null);
	lessonCompleted = $state(false);
	isQuizMode = $state(false);
	currentCode = $state('');
	currentLanguage = $state<string>('c');

	// Per-language code tracking
	cCode = $state('');
	pythonCode = $state('');

	// Output state
	freshOutput = () => ({ output: '', error: '', loading: false, success: null as boolean | null, debug: undefined as string[] | undefined });
	cOut = $state(this.freshOutput());
	pyOut = $state(this.freshOutput());
	circuitOut = $state(this.freshOutput());
	velxioOut = $state(this.freshOutput());
	flowchartOut = $state(this.freshOutput());

	cPassed = $state(false);
	pythonPassed = $state(false);
	circuitPassed = $state(false);
	flowchartPassed = $state(false);

	velxioBridge = $state<VelxioBridge | null>(null);
	velxioReady = $state(false);
	velxioSaving = $state(false);
	velxioError = $state(false);
	velxioIframe = $state<HTMLIFrameElement | null>(null);

	showSolution = $state(false);
	activeTab = $state<'info' | 'exercise' | 'editor' | 'circuit' | 'output' | 'velxio' | 'flowchart'>('info');
	showCelebration = $state(false);
	mobileMode = $state<'hidden' | 'half' | 'full'>('hidden');
	isMobile = $state(false);

	// Refs (set from component)
	editor = $state<CodeEditor | null>(null);
	circuitEditor = $state<CircuitEditor | null>(null);
	flowchartTab = $state<any>(null);

	slug = $derived(get(page).params.slug);
	
	isVelxio = $derived(this.data?.active_tabs?.includes('velxio') ?? false);
	isFlowchart = $derived(this.data?.active_tabs?.includes('flowchart') ?? false);
	outputSections = $derived.by(() => {
		const tabs = this.data?.active_tabs ?? [];
		const secs: any[] = [];
		if (tabs.includes('c') || (!tabs.length && !tabs.includes('python'))) {
			secs.push({ key: 'c', label: 'C', icon: '\u{1F4BB}', data: this.cOut, placeholder: 'Klik "Run" untuk menjalankan kode C', loadingText: 'Mengompilasi C...' });
		}
		if (tabs.includes('python')) {
			secs.push({ key: 'python', label: 'Python', icon: '\u{1F40D}', data: this.pyOut, placeholder: 'Klik "Run" untuk menjalankan kode Python', loadingText: 'Menjalankan Python...' });
		}
		if (tabs.includes('circuit')) {
			secs.push({ key: 'circuit', label: 'Circuit', icon: '\u26A1', data: this.circuitOut, placeholder: 'Klik "Cek Rangkaian" untuk mengevaluasi', loadingText: 'Mengevaluasi rangkaian...' });
		}
		if (tabs.includes('velxio')) {
			secs.push({ key: 'velxio', label: 'Arduino', icon: '\u{1F4DF}', data: this.velxioOut, placeholder: 'Klik "Compile & Run" untuk menjalankan kode', loadingText: 'Mengevaluasi...' });
		}
		if (tabs.includes('flowchart')) {
			secs.push({ key: 'flowchart', label: 'Flowchart', icon: '\u{1F531}', data: this.flowchartOut, placeholder: 'Klik "Cek Flowchart" untuk mengevaluasi alur logika', loadingText: 'Mengevaluasi alur...' });
		}
		return secs;
	});

	isHybrid = $derived(
		(this.data?.active_tabs?.includes('c') || this.data?.active_tabs?.includes('python')) &&
		this.data?.active_tabs?.includes('circuit')
	);
	compiling = $derived(this.cOut.loading || this.pyOut.loading || this.circuitOut.loading || this.flowchartOut.loading);

	arduinoCodeKey = $derived(`elemes_arduino_code_${this.slug}`);
	arduinoCircuitKey = $derived(`elemes_arduino_circuit_${this.slug}`);
	flowchartStorageKey = $derived(`elemes_flowchart_draft_${this.slug}`);

	constructor() {
		// Media query detection
		if (typeof window !== 'undefined') {
			const mql = window.matchMedia('(max-width: 768px)');
			this.isMobile = mql.matches;
			const handler = (e: MediaQueryListEvent) => {
				this.isMobile = e.matches;
			};
			mql.addEventListener('change', handler);

			// Auto-save Velxio state periodically
			$effect(() => {
				if (this.velxioReady && get(authLoggedIn) && !this.showSolution) {
					const interval = setInterval(() => {
						const state = getVelxioState(this.velxioIframe);
						if (!state) return;
						
						let changed = false;
						
						// 1. Source Code
						const savedCode = localStorage.getItem(this.arduinoCodeKey);
						if (state.code && state.code !== savedCode) {
							console.log('[Velxio Auto-save] Saving code changes (Zustand)');
							localStorage.setItem(this.arduinoCodeKey, state.code);
							changed = true;
						}

						// 2. Circuit (Diagram + Wires)
						const savedCircuit = localStorage.getItem(this.arduinoCircuitKey);
						if (state.circuit && state.circuit !== savedCircuit) {
							console.log('[Velxio Auto-save] Saving circuit changes (Zustand)');
							localStorage.setItem(this.arduinoCircuitKey, state.circuit);
							changed = true;
						}
						
						if (changed) {
							this.velxioSaving = true;
							setTimeout(() => { this.velxioSaving = false; }, 1500);
						}
					}, 7000); // Poll every 7 seconds
					
					return () => clearInterval(interval);
				}
			});
		}
	}

	// Switch editor content when language tab changes
	prevLanguage = $state<string>('c');
	setupLanguageSync() {
		$effect(() => {
			if (!this.data || this.currentLanguage === this.prevLanguage) return;
			// Save current code to the previous language slot
			const code = this.editor?.getCode() ?? this.currentCode;
			if (this.prevLanguage === 'c') this.cCode = code;
			else if (this.prevLanguage === 'python') this.pythonCode = code;
			// Load code for the new language
			const newCode = this.currentLanguage === 'python' ? this.pythonCode : (this.cCode || this.data.initial_code || '');
			this.currentCode = newCode;
			this.editor?.setCode(newCode);
			this.prevLanguage = this.currentLanguage;
		});
	}

	init(lesson: LessonContent) {
		untrack(() => {
			this.data = lesson;
			this.lessonCompleted = lesson.lesson_completed;
			this.isQuizMode = false;

			this.cCode = lesson.initial_code_c || '';
			this.pythonCode = lesson.initial_python || '';

			const hasC = lesson.active_tabs?.includes('c');
			const hasPython = lesson.active_tabs?.includes('python');
			const initLang = (hasPython && !hasC) ? 'python' : 'c';
			this.currentLanguage = initLang;
			this.currentCode = initLang === 'python' ? this.pythonCode : (this.cCode || lesson.initial_code || '');

			this.cOut = this.freshOutput();
			this.pyOut = this.freshOutput();
			this.circuitOut = this.freshOutput();
			this.velxioOut = this.freshOutput();
			this.cPassed = false;
			this.pythonPassed = false;
			this.circuitPassed = false;
			this.showSolution = false;

			if (this.velxioBridge) { this.velxioBridge.destroy(); this.velxioBridge = null; }
			this.velxioReady = false;
			this.velxioError = false;

			if (lesson.lesson_info) this.activeTab = 'info';
			else if (lesson.exercise_content) this.activeTab = 'exercise';
			else if (lesson.active_tabs?.includes('velxio')) this.activeTab = 'velxio';
			else if (lesson.active_tabs?.includes('flowchart')) this.activeTab = 'flowchart';
			else if (lesson.active_tabs?.includes('circuit') && !hasC && !hasPython) this.activeTab = 'circuit';
			else this.activeTab = 'editor';
			
			this.mobileMode = 'hidden';

			lessonContext.set({
				title: lesson.lesson_title,
				completed: lesson.lesson_completed,
				prevLesson: lesson.prev_lesson,
				nextLesson: lesson.next_lesson
			});
		});
	}

	async completeLesson(status = 'completed') {
		if (this.lessonCompleted && status === 'completed') return;
		this.showCelebration = true;

		if (get(authLoggedIn)) {
			const lessonName = this.slug.replace('.md', '');
			await trackProgress(auth.token, lessonName, status);
			this.lessonCompleted = true;
			lessonContext.update(ctx => ctx ? { ...ctx, completed: true } : ctx);
		}
	}

	checkAllPassed(): boolean {
		const needsC = this.data?.active_tabs?.includes('c');
		const needsPython = this.data?.active_tabs?.includes('python');
		const needsCircuit = this.data?.active_tabs?.includes('circuit');
		const needsFlowchart = this.data?.active_tabs?.includes('flowchart');
		
		if (!this.data?.active_tabs?.length) return true;

		if (needsC && !this.cPassed) return false;
		if (needsPython && !this.pythonPassed) return false;
		if (needsCircuit && !this.circuitPassed) return false;
		if (needsFlowchart && !this.flowchartPassed) return false;
		
		return true;
	}

	async evaluateFlowchart() {
		if (!this.data || !this.flowchartTab) return;
		Object.assign(this.flowchartOut, { loading: true, output: 'Mengevaluasi alur...', error: '', success: null });
		this.activeTab = 'output';
		try {
			const flowchartText = await this.flowchartTab.getFlowchartText();
			if (!flowchartText) {
				Object.assign(this.flowchartOut, { error: 'Gagal mengambil data flowchart.', success: false });
				return;
			}
			const expectedFlowchart = this.data.expected_flowchart || '';
			if (!expectedFlowchart) {
				Object.assign(this.flowchartOut, { error: 'Kunci jawaban tidak tersedia untuk pelajaran ini.', success: false });
				return;
			}
			const result = evaluateFlowchartSubmission(flowchartText, expectedFlowchart);
			this.flowchartOut.output = result.output;
			this.flowchartOut.success = result.pass;
			if (this.flowchartOut.success) {
				this.flowchartPassed = true;
				if (this.checkAllPassed()) {
					await this.completeLesson();
					setTimeout(() => { this.showCelebration = false; this.activeTab = 'flowchart'; }, 3000);
				}
			}
		} catch (err: any) {
			Object.assign(this.flowchartOut, { error: `Terjadi kesalahan saat evaluasi: ${err.message}`, success: false });
		} finally {
			this.flowchartOut.loading = false;
		}
	}

	async evaluateCircuit() {
		if (!this.data || !this.circuitEditor) return;
		const simApi = this.circuitEditor.getApi();
		if (!simApi) {
			Object.assign(this.circuitOut, { error: "Simulator belum siap.", success: false });
			this.activeTab = 'output';
			return;
		}
		Object.assign(this.circuitOut, { loading: true, output: 'Mengevaluasi rangkaian...', error: '', success: null });
		this.activeTab = 'output';
		try {
			const circuitText = this.circuitEditor.getCircuitText();
			const res = evaluateCircuitSubmission(simApi, circuitText, this.isHybrid, this.data, () => this.checkAllPassed());
			if (res.error) {
				Object.assign(this.circuitOut, { error: res.error, success: false, loading: false });
				return;
			}
			this.circuitOut.output = res.output;
			this.circuitOut.success = res.pass;
			if (res.pass) {
				this.circuitPassed = true;
				if (this.checkAllPassed()) {
					await this.completeLesson();
					setTimeout(() => { this.showCelebration = false; this.activeTab = 'circuit'; }, 3000);
				}
			}
		} catch (err: any) {
			Object.assign(this.circuitOut, { error: `Evaluasi gagal: ${err.message}`, success: false });
		} finally {
			this.circuitOut.loading = false;
		}
	}

	async evaluateLanguage(lang: 'c' | 'python') {
		if (!this.data) return;
		const out = lang === 'c' ? this.cOut : this.pyOut;
		Object.assign(out, { loading: true, output: '', error: '', success: null });
		this.activeTab = 'output';
		try {
			const code = (this.currentLanguage === lang) ? (this.editor?.getCode() ?? this.currentCode) : (lang === 'c' ? this.cCode : this.pythonCode);
			const res = await compileCode({ code, language: lang, token: auth.token });
			if (!res.success) {
				Object.assign(out, { error: res.error || 'Compilation failed', success: false });
				return;
			}
			out.output = res.output;
			out.success = true;
			if (this.data.expected_output || this.data.expected_output_python) {
				const { isCorrect } = processLanguageEvaluation(res.output, code, lang, this.currentLanguage, this.cCode, this.pythonCode, this.data);
				if (isCorrect) {
					if (lang === 'c') this.cPassed = true;
					else if (lang === 'python') this.pythonPassed = true;
					if (!this.checkAllPassed()) {
						out.output += '\n✅ Kode benar!\n⏳ Selesaikan juga tantangan di tab lainnya untuk menyelesaikan pelajaran ini.';
					} else {
						out.output += '\n🎉 Semuanya benar!';
					}
					if (this.checkAllPassed()) {
						await this.completeLesson();
						if (this.data.solution_code || this.data.solution_python || this.data.solution_circuit) { 
							this.showSolution = true;
							this.handleShowSolution();
							this.showSolution = true; 
						}
						setTimeout(() => { this.showCelebration = false; this.activeTab = 'editor'; }, 3000);
					}
				}
			}
		} catch {
			Object.assign(out, { error: 'Gagal terhubung ke server', success: false });
		} finally {
			out.loading = false;
		}
	}

	async handleRun() {
		if (this.activeTab === 'circuit') { await this.evaluateCircuit(); return; }
		if (this.activeTab === 'flowchart') { await this.evaluateFlowchart(); return; }
		if (!this.data) return;
		this.activeTab = 'output';
		await this.evaluateLanguage(this.currentLanguage as 'c' | 'python');
	}

	async handleRunAll() {
		if (!this.data) return;
		this.activeTab = 'output';
		const tabs = this.data.active_tabs ?? [];
		if (tabs.includes('c') || (!tabs.length && !tabs.includes('python'))) await this.evaluateLanguage('c');
		if (tabs.includes('python')) await this.evaluateLanguage('python');
		if (tabs.includes('circuit')) await this.evaluateCircuit();
		if (tabs.includes('velxio')) await this.handleVelxioSubmit();
		if (tabs.includes('flowchart')) await this.evaluateFlowchart();
	}

	handleReset() {
		if (!this.data) return;
		if (this.activeTab === 'circuit') {
			this.circuitEditor?.setCircuitText(this.data.initial_circuit || this.data.initial_code);
			Object.assign(this.circuitOut, this.freshOutput());
		} else if (this.activeTab === 'velxio') {
			localStorage.removeItem(this.arduinoCodeKey);
			localStorage.removeItem(this.arduinoCircuitKey);
			if (this.data.initial_code_arduino) {
				this.velxioBridge?.loadCode([{ name: 'sketch.ino', content: this.data.initial_code_arduino }]);
			}
			if (this.data.velxio_circuit) {
				this.velxioBridge?.loadCircuit(this.data.velxio_circuit);
			}
			Object.assign(this.velxioOut, this.freshOutput());
		} else if (this.activeTab === 'flowchart') {
			localStorage.removeItem(this.flowchartStorageKey);
			if (this.flowchartTab && typeof this.flowchartTab.handleLoad === 'function') {
				this.flowchartTab.handleLoad(true);
			}
		} else {
			const resetCode = this.currentLanguage === 'python'
				? (this.data.initial_python || '')
				: (this.data.initial_code_c || this.data.initial_code || '');
			this.currentCode = resetCode;
			if (this.currentLanguage === 'c') this.cCode = resetCode;
			else this.pythonCode = resetCode;
			this.editor?.setCode(resetCode);
			const out = this.currentLanguage === 'python' ? this.pyOut : this.cOut;
			Object.assign(out, this.freshOutput());
		}
	}

	handleShowSolution() {
		if (!this.data) return;
		if (!this.data.solution_code && !this.data.solution_circuit && !this.data.solution_python) return;
		this.showSolution = !this.showSolution;
		if (this.showSolution) {
			if (this.data.active_tabs?.includes('circuit') && this.data.solution_circuit) {
				this.circuitEditor?.setCircuitText(this.data.solution_circuit);
			}
			if (this.currentLanguage === 'python' && this.data.solution_python) {
				this.editor?.setCode(this.data.solution_python);
			} else if (this.data.solution_code) {
				this.editor?.setCode(this.data.solution_code);
			}
		} else {
			if (this.data.active_tabs?.includes('circuit') && this.data.initial_circuit) {
				this.circuitEditor?.setCircuitText(this.data.initial_circuit);
			}
			if (this.currentLanguage === 'python' || this.currentLanguage === 'c' || this.data.initial_code) {
				this.editor?.setCode(this.currentCode);
			}
		}
	}

	setupVelxioBridge(iframe: HTMLIFrameElement) {
		this.velxioIframe = iframe;
		initVelxioBridge(
			iframe,
			this.data,
			this.arduinoCircuitKey,
			this.arduinoCodeKey,
			(bridge) => {
				this.velxioBridge = bridge;
				this.velxioReady = true;
			},
			() => this.handleVelxioSubmit()
		);
	}

	async handleVelxioSubmit() {
		if (!this.data) return;
		Object.assign(this.velxioOut, { loading: true, output: 'Mengevaluasi...', error: '', success: null });
		this.activeTab = 'output';
		try {
			let sourceCode = '';
			let serialLog = '';
			let wireList: any[] = [];
			const dbg: string[] = [];
			if (this.velxioBridge) {
				const serResp = await this.velxioBridge['request']('elemes:get_serial_log', 'velxio:serial_log');
				if (serResp) serialLog = serResp.log as string;
			}
			const state = getVelxioState(this.velxioIframe);
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
			const evalRes = evaluateVelxioSubmission(sourceCode, serialLog, wireList, this.data);
			this.velxioOut.output = evalRes.messages.join('\n');
			this.velxioOut.debug = dbg.concat(evalRes.dbg);
			this.velxioOut.success = evalRes.pass;
			if (evalRes.pass) {
				await this.completeLesson();
				setTimeout(() => { this.showCelebration = false; this.activeTab = 'velxio'; }, 3000);
			}
		} catch (err: any) {
			Object.assign(this.velxioOut, { error: `Evaluasi gagal: ${err.message}`, success: false });
		} finally {
			this.velxioOut.loading = false;
		}
	}

	getLessonTitle(slug: string) {
		const lesson = this.data?.ordered_lessons?.find(l => l.filename.replace('.md', '') === slug);
		return lesson?.title || slug.replace(/_/g, ' ').toUpperCase();
	}

	handleTryCode(code: string, lang: string, float: any) {
		if (lang === 'python' || lang === 'c') {
			this.currentLanguage = lang;
			this.currentCode = code;
			if (lang === 'c') this.cCode = code;
			else this.pythonCode = code;
			this.editor?.setCode(code);
			this.activeTab = 'editor';
			if (!this.isMobile) {
				float.floating = true;
			} else {
				this.mobileMode = 'half';
				tick().then(() => {
					document.querySelector('.editor-area')?.scrollIntoView({ behavior: 'smooth' });
				});
			}
		} else if (lang === 'cpp') {
			if (this.isVelxio && this.velxioBridge) {
				this.velxioBridge.loadCode([{ name: 'sketch.ino', content: code }]);
				this.activeTab = 'velxio';
				if (!this.isMobile) {
					float.floating = true;
				} else {
					this.mobileMode = 'half';
					tick().then(() => {
						document.querySelector('.editor-area')?.scrollIntoView({ behavior: 'smooth' });
					});
				}
			}
		}
	}
}
