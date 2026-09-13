import { picoc } from '$lib/vendor/picoc.js';
import type { RunRequest, WorkerMessage } from './types';

let stdinArray: Int32Array | null = null;
let stdinDataView: Uint8Array | null = null;
let currentLine: string = '';
let charIndex: number = 0;
let justFinishedLine: boolean = false;
let prefilledStdin: string = '';
let prefilledIdx: number = 0;
let stdoutBuf: number[] = [];
let stderrBuf: number[] = [];

function flushStdout(): void {
	if (stdoutBuf.length > 0) {
		const text = new TextDecoder().decode(new Uint8Array(stdoutBuf));
		self.postMessage({ type: 'stdout', text } satisfies WorkerMessage);
		stdoutBuf = [];
	}
}

function flushStderr(): void {
	if (stderrBuf.length > 0) {
		const text = new TextDecoder().decode(new Uint8Array(stderrBuf));
		self.postMessage({ type: 'stderr', text } satisfies WorkerMessage);
		stderrBuf = [];
	}
}

function stdinRead(): number | null {
	if (charIndex < currentLine.length) {
		return currentLine.charCodeAt(charIndex++);
	}

	if (justFinishedLine) {
		justFinishedLine = false;
		return null;
	}

	if (prefilledIdx < prefilledStdin.length) {
		return prefilledStdin.charCodeAt(prefilledIdx++);
	}

	if (!stdinArray || !stdinDataView) {
		return null;
	}

	flushStdout();

	// If main thread has not already written input (flag != 1), notify UI and wait
	if (Atomics.load(stdinArray, 0) === 0) {
		self.postMessage({ type: 'waiting_for_input' } satisfies WorkerMessage);
		Atomics.wait(stdinArray, 0, 0);
	}

	const len = Atomics.load(stdinArray, 1);
	if (len <= 0) {
		Atomics.store(stdinArray, 0, 0);
		return null;
	}

	const bytes = stdinDataView.slice(8, 8 + len);
	Atomics.store(stdinArray, 0, 0);

	currentLine = new TextDecoder().decode(bytes);
	if (!currentLine.endsWith('\n')) {
		currentLine += '\n';
	}
	charIndex = 0;
	justFinishedLine = true;

	return currentLine.charCodeAt(charIndex++);
}

function prepareCCode(code: string): string {
	if (!code.includes('setbuf(') && !code.includes('setvbuf(')) {
		const mainRegex = /\b(int|void)?\s*main\s*\([^)]*\)\s*\{/;
		if (mainRegex.test(code)) {
			code = code.replace(mainRegex, (match) => `${match}\n    setbuf(stdout, NULL);`);
		}
	}
	// In PicoC, 32-bit float in scanf("%f") writes 0 due to 64-bit JS numbers representation;
	// upgrading to double/%lf allows normal float code to execute accurately.
	code = code.replace(/\bfloat\b/g, 'double');
	code = code.replace(/scanf\s*\(\s*"([^"]*)"/g, (match, fmt) => {
		const upgradedFmt = fmt.replace(/%f/g, '%lf');
		return `scanf("${upgradedFmt}"`;
	});
	return code;
}

self.onmessage = (e: MessageEvent<RunRequest>) => {
	const { code, stdinBuffer, stdinText } = e.data;
	const start = performance.now();

	if (stdinBuffer) {
		stdinArray = new Int32Array(stdinBuffer);
		stdinDataView = new Uint8Array(stdinBuffer);
	} else {
		stdinArray = null;
		stdinDataView = null;
	}

	prefilledStdin = stdinText || '';
	prefilledIdx = 0;
	currentLine = '';
	charIndex = 0;
	justFinishedLine = false;
	stdoutBuf = [];
	stderrBuf = [];

	try {
		let hasExecuted = false;
		const execute = () => {
			if (hasExecuted) return;
			hasExecuted = true;
			try {
				pc.runc(prepareCCode(code), (text: string) => {
					if (text) {
						self.postMessage({ type: 'stdout', text: text + '\n' } satisfies WorkerMessage);
					}
				});
				flushStdout();
				flushStderr();
				self.postMessage({
					type: 'done',
					success: true,
					executionTimeMs: performance.now() - start
				} satisfies WorkerMessage);
			} catch (err: any) {
				const errMsg = err?.message || String(err);
				self.postMessage({ type: 'stderr', text: errMsg } satisfies WorkerMessage);
				self.postMessage({
					type: 'done',
					success: false,
					error: errMsg,
					executionTimeMs: performance.now() - start
				} satisfies WorkerMessage);
			}
		};

		const pc = (picoc as any)({
			noInitialRun: true,
			stdin: stdinRead,
			stdout: (c: number) => {
				if (c === 10) {
					const line = new TextDecoder().decode(new Uint8Array(stdoutBuf));
					self.postMessage({ type: 'stdout', text: line + '\n' } satisfies WorkerMessage);
					stdoutBuf = [];
				} else {
					stdoutBuf.push(c);
				}
			},
			stderr: (c: number) => {
				if (c === 10) {
					const line = new TextDecoder().decode(new Uint8Array(stderrBuf));
					self.postMessage({ type: 'stderr', text: line + '\n' } satisfies WorkerMessage);
					stderrBuf = [];
				} else {
					stderrBuf.push(c);
				}
			},
			print: (text: string) => {
				self.postMessage({ type: 'stdout', text: text + '\n' } satisfies WorkerMessage);
			},
			printErr: (text: string) => {
				self.postMessage({ type: 'stderr', text: text + '\n' } satisfies WorkerMessage);
			},
			consoleWrite: (text: string) => {
				if (text) {
					self.postMessage({ type: 'stdout', text: text + '\n' } satisfies WorkerMessage);
				}
			},
			onRuntimeInitialized: () => {
				execute();
			}
		});

		if (pc && pc.calledRun) {
			execute();
		}
	} catch (err: any) {
		const errMsg = err?.message || String(err);
		self.postMessage({
			type: 'done',
			success: false,
			error: errMsg,
			executionTimeMs: performance.now() - start
		} satisfies WorkerMessage);
	}
};

self.onerror = (event) => {
	console.error('[c-worker] Uncaught error in worker:', event);
};
