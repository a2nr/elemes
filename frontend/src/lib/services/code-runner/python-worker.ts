import { loadMicroPython } from '@micropython/micropython-webassembly-pyscript';
import micropythonWasmUrl from '@micropython/micropython-webassembly-pyscript/micropython.wasm?url';
import type { RunRequest, WorkerMessage } from './types';

let mpInstance: any = null;
let stdinArray: Int32Array | null = null;
let stdinDataView: Uint8Array | null = null;
let prefilledLines: string[] = [];
let prefilledLineIdx = 0;

function readlineSync(): string {
	if (prefilledLines.length > 0) {
		if (prefilledLineIdx < prefilledLines.length) {
			return prefilledLines[prefilledLineIdx++];
		}
		return '';
	}

	if (!stdinArray || !stdinDataView) {
		return '';
	}

	self.postMessage({ type: 'waiting_for_input' } satisfies WorkerMessage);
	Atomics.wait(stdinArray, 0, 0);

	const len = Atomics.load(stdinArray, 1);
	if (len <= 0) {
		Atomics.store(stdinArray, 0, 0);
		return '';
	}

	const bytes = stdinDataView.slice(8, 8 + len);
	Atomics.store(stdinArray, 0, 0);

	return new TextDecoder().decode(bytes).replace(/\r?\n$/, '');
}

async function getMicroPython(): Promise<any> {
	if (!mpInstance) {
		const wasmUrl = typeof micropythonWasmUrl === 'string' && micropythonWasmUrl
			? new URL(micropythonWasmUrl, self.location.href).href
			: new URL('/micropython.wasm', self.location.origin).href;

		mpInstance = await loadMicroPython({
			url: wasmUrl,
			stdout: (text: string) => {
				self.postMessage({ type: 'stdout', text: text + '\n' } satisfies WorkerMessage);
			},
			stderr: (text: string) => {
				self.postMessage({ type: 'stderr', text: text + '\n' } satisfies WorkerMessage);
			},
			linebuffer: true
		});

		mpInstance.registerJsModule('_elemes_io', {
			readline: () => readlineSync()
		});

		mpInstance.runPython(`
import _elemes_io
import builtins

def _interactive_input(prompt=''):
    if prompt:
        print(prompt, end='')
    return _elemes_io.readline()

builtins.input = _interactive_input
`);
	}
	return mpInstance;
}

self.onmessage = async (e: MessageEvent<RunRequest>) => {
	const { code, stdinBuffer, stdinText } = e.data;
	const start = performance.now();

	if (stdinBuffer) {
		stdinArray = new Int32Array(stdinBuffer);
		stdinDataView = new Uint8Array(stdinBuffer);
	} else {
		stdinArray = null;
		stdinDataView = null;
	}

	prefilledLines = stdinText ? stdinText.split(/\r?\n/) : [];
	prefilledLineIdx = 0;

	try {
		const mp = await getMicroPython();
		mp.runPython(code);
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

self.onerror = (event) => {
	console.error('[python-worker] Uncaught error in worker:', event);
};
