import { picoc } from '$lib/vendor/picoc.js';
import type { RunRequest, WorkerMessage } from './types';

let stdinArray: Int32Array | null = null;
let stdinDataView: Uint8Array | null = null;
let currentLine: string = '';
let charIndex: number = 0;
let justFinishedLine: boolean = false;
let prefilledStdin: string = '';
let prefilledIdx: number = 0;

function stdinRead(): number | null {
	if (prefilledStdin.length > 0) {
		if (prefilledIdx < prefilledStdin.length) {
			return prefilledStdin.charCodeAt(prefilledIdx++);
		}
		return null;
	}

	if (!stdinArray || !stdinDataView) {
		return null;
	}

	if (charIndex < currentLine.length) {
		return currentLine.charCodeAt(charIndex++);
	}

	if (justFinishedLine) {
		justFinishedLine = false;
		return null;
	}

	self.postMessage({ type: 'waiting_for_input' } satisfies WorkerMessage);
	Atomics.wait(stdinArray, 0, 0);

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

	try {
		let stdoutBuf: number[] = [];
		let stderrBuf: number[] = [];
		let callbackError = '';

		let hasExecuted = false;
		const execute = () => {
			if (hasExecuted) return;
			hasExecuted = true;
			try {
				pc.runc(code, (text: string) => {
					if (text) {
						callbackError += text + '\n';
						self.postMessage({ type: 'stdout', text: text + '\n' } satisfies WorkerMessage);
					}
				});
				if (stdoutBuf.length > 0) {
					const remaining = new TextDecoder().decode(new Uint8Array(stdoutBuf));
					self.postMessage({ type: 'stdout', text: remaining } satisfies WorkerMessage);
					stdoutBuf = [];
				}
				if (stderrBuf.length > 0) {
					const remaining = new TextDecoder().decode(new Uint8Array(stderrBuf));
					self.postMessage({ type: 'stderr', text: remaining } satisfies WorkerMessage);
					stderrBuf = [];
				}
				self.postMessage({
					type: 'done',
					success: !callbackError,
					error: callbackError || undefined,
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
					callbackError += text + '\n';
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
