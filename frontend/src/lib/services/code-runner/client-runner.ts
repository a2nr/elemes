import type { CompileResponse } from '$types/compiler';
import type { RunRequest, WorkerMessage } from './types';
import CWorker from './c-worker.ts?worker';
import PyWorker from './python-worker.ts?worker';

const DEFAULT_TIMEOUT_MS = 5000;
const SAB_SIZE = 4096; // 4 KB for one line of stdin buffer

export interface RunOptions {
	stdinText?: string;
	timeoutMs?: number;
	onStdout?: (text: string) => void;
	onStderr?: (text: string) => void;
	onWaitingForInput?: () => void;
}

export class ClientRunner {
	private cWorker: Worker | null = null;
	private pyWorker: Worker | null = null;
	private stdinSAB: SharedArrayBuffer | null = null;

	onWaitingForInput?: () => void;
	onStdout?: (text: string) => void;
	onStderr?: (text: string) => void;

	get isSharedArrayBufferSupported(): boolean {
		return typeof SharedArrayBuffer !== 'undefined';
	}

	private ensureSAB(): SharedArrayBuffer | undefined {
		if (!this.isSharedArrayBufferSupported) return undefined;
		if (!this.stdinSAB) {
			this.stdinSAB = new SharedArrayBuffer(SAB_SIZE);
		}
		new Int32Array(this.stdinSAB)[0] = 0; // reset ready flag
		return this.stdinSAB;
	}

	/**
	 * Send interactive user input to the waiting worker via SharedArrayBuffer
	 */
	sendInput(text: string): void {
		if (!this.stdinSAB) return;
		const arr = new Int32Array(this.stdinSAB);
		const view = new Uint8Array(this.stdinSAB);
		const encoded = new TextEncoder().encode(text.endsWith('\n') ? text : text + '\n');
		view.set(encoded, 8);
		Atomics.store(arr, 1, encoded.length);
		Atomics.store(arr, 0, 1); // flag ready = 1
		Atomics.notify(arr, 0);   // wake up worker
	}

	async run(
		lang: 'c' | 'python',
		code: string,
		options: RunOptions = {}
	): Promise<CompileResponse> {
		if (typeof window === 'undefined' || typeof Worker === 'undefined') {
			return {
				success: false,
				output: '',
				error: 'Client runner only available in browser environment'
			};
		}

		const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
		const sab = this.ensureSAB();

		return new Promise<CompileResponse>((resolve) => {
			let output = '';
			let error = '';
			let settled = false;

			const worker = this.spawnWorker(lang);

			const timer = setTimeout(() => {
				if (settled) return;
				settled = true;
				this.killWorker(lang);
				resolve({
					success: false,
					output: output.trimEnd(),
					error: `⏱️ Eksekusi dihentikan — batas waktu ${timeoutMs / 1000} detik terlampaui (kemungkinan infinite loop).`
				});
			}, timeoutMs);

			worker.onmessage = (e: MessageEvent<WorkerMessage>) => {
				const msg = e.data;
				if (msg.type === 'stdout') {
					output += msg.text;
					this.onStdout?.(msg.text);
					options.onStdout?.(msg.text);
				} else if (msg.type === 'stderr') {
					error += msg.text;
					this.onStderr?.(msg.text);
					options.onStderr?.(msg.text);
				} else if (msg.type === 'waiting_for_input') {
					this.onWaitingForInput?.();
					options.onWaitingForInput?.();
				} else if (msg.type === 'done') {
					if (settled) return;
					settled = true;
					clearTimeout(timer);
					resolve({
						success: msg.success,
						output: output.trimEnd(),
						error: msg.error || error || ''
					});
				}
			};

			worker.onerror = (errEvent) => {
				console.error('[client-runner] Worker onerror event:', errEvent);
				if (settled) return;
				settled = true;
				clearTimeout(timer);
				const details = [
					errEvent.message,
					errEvent.filename ? `(${errEvent.filename}:${errEvent.lineno}:${errEvent.colno})` : null,
					errEvent.error ? String(errEvent.error) : null
				].filter(Boolean).join(' ');
				const msg = details || 'Worker runtime error (periksa DevTools Console untuk detail script error)';
				resolve({
					success: false,
					output: output.trimEnd(),
					error: msg
				});
			};

			const req: RunRequest = {
				id: crypto.randomUUID(),
				language: lang,
				code,
				stdinBuffer: sab,
				stdinText: options.stdinText
			};

			worker.postMessage(req);
		});
	}

	terminate(lang?: 'c' | 'python'): void {
		if (!lang || lang === 'c') this.killWorker('c');
		if (!lang || lang === 'python') this.killWorker('python');
	}

	private spawnWorker(lang: 'c' | 'python'): Worker {
		this.killWorker(lang);
		const worker = lang === 'c' ? new CWorker() : new PyWorker();

		if (lang === 'c') this.cWorker = worker;
		else this.pyWorker = worker;

		return worker;
	}

	private killWorker(lang: 'c' | 'python'): void {
		const w = lang === 'c' ? this.cWorker : this.pyWorker;
		if (w) {
			w.terminate();
		}
		if (lang === 'c') this.cWorker = null;
		else this.pyWorker = null;
	}
}

export const clientRunner = new ClientRunner();
