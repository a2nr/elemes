import { describe, it, expect, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { playgroundStore } from './playground';

describe('playgroundStore stdinQueue', () => {
	beforeEach(() => {
		playgroundStore.reset();
		playgroundStore.clearConsole();
	});

	it('enqueueStdin menambah baris ke antrean', () => {
		playgroundStore.enqueueStdin('Budi');
		playgroundStore.enqueueStdin('17');
		const state = get(playgroundStore);
		expect(state.stdinQueue).toEqual(['Budi', '17']);
	});

	it('enqueueStdin mengabaikan baris kosong', () => {
		playgroundStore.enqueueStdin('');
		playgroundStore.enqueueStdin('   ');
		const state = get(playgroundStore);
		expect(state.stdinQueue).toEqual([]);
	});

	it('consumeStdin mengembalikan seluruh antrean tanpa memakan draft consoleInput', () => {
		playgroundStore.enqueueStdin('Budi');
		playgroundStore.enqueueStdin('17');
		playgroundStore.setConsoleInput('draft yang belum dikirim');
		const stdin = playgroundStore.consumeStdin();
		expect(stdin).toBe('Budi\n17\n');
		const state = get(playgroundStore);
		expect(state.stdinQueue).toEqual([]);
		expect(state.consoleInput).toBe('draft yang belum dikirim');
	});

	it('appendConsole menambahkan id unik pada ConsoleLine', () => {
		playgroundStore.appendConsole({ type: 'output', text: 'Hello', timestamp: 123 } as any);
		playgroundStore.appendConsole({ type: 'output', text: 'World', timestamp: 123 } as any);
		const history = get(playgroundStore).consoleHistory;
		expect(history.length).toBe(2);
		expect(history[0].id).toBeDefined();
		expect(history[1].id).toBeDefined();
		expect(history[0].id).not.toBe(history[1].id);
	});

	it('consumeStdin mengembalikan string kosong jika tidak ada baris maupun draft', () => {
		const stdin = playgroundStore.consumeStdin();
		expect(stdin).toBe('');
	});

	it('consumeStdin menambah baris baru di akhir masing-masing baris', () => {
		playgroundStore.enqueueStdin('Budi');
		const stdin = playgroundStore.consumeStdin();
		expect(stdin).toBe('Budi\n');
	});

	it('clearStdinQueue mengosongkan antrean tanpa menyentuh consoleInput', () => {
		playgroundStore.enqueueStdin('Budi');
		playgroundStore.setConsoleInput('draft');
		playgroundStore.clearStdinQueue();
		const state = get(playgroundStore);
		expect(state.stdinQueue).toEqual([]);
		expect(state.consoleInput).toBe('draft');
	});
});

describe('playgroundStore session lifecycle', () => {
	beforeEach(() => {
		playgroundStore.reset();
	});

	it('startRunSession mengisi sessionId, status, dan mereset cursor/error', () => {
		playgroundStore.startRunSession('sess-abc', 'running');
		const state = get(playgroundStore);
		expect(state.runSessionId).toBe('sess-abc');
		expect(state.runStatus).toBe('running');
		expect(state.outputCursor).toBe(0);
		expect(state.runError).toBeNull();
	});

	it('hanya satu sesi aktif — start kedua menimpa sesi pertama', () => {
		playgroundStore.startRunSession('sess-1', 'running');
		playgroundStore.startRunSession('sess-2', 'running');
		const state = get(playgroundStore);
		expect(state.runSessionId).toBe('sess-2');
		expect(state.runStatus).toBe('running');
	});

	it('advanceOutputCursor tidak pernah mundur', () => {
		playgroundStore.startRunSession('sess-1', 'running');
		playgroundStore.advanceOutputCursor(1024);
		playgroundStore.advanceOutputCursor(512);
		const state = get(playgroundStore);
		expect(state.outputCursor).toBe(1024);
	});

	it('finishRun mengubah status ke terminal tapi mempertahankan sessionId', () => {
		playgroundStore.startRunSession('sess-1', 'running');
		playgroundStore.finishRun('exited');
		const state = get(playgroundStore);
		expect(state.runStatus).toBe('exited');
		expect(state.runSessionId).toBe('sess-1');
	});

	it('finishRun dapat menyimpan error', () => {
		playgroundStore.startRunSession('sess-1', 'running');
		playgroundStore.finishRun('error', 'Traceback: division by zero');
		const state = get(playgroundStore);
		expect(state.runStatus).toBe('error');
		expect(state.runError).toBe('Traceback: division by zero');
	});

	it('resetRunSession membersihkan semua state runtime tapi menyimpan file & fileTreeVisible', () => {
		playgroundStore.startRunSession('sess-1', 'running');
		playgroundStore.advanceOutputCursor(42);
		playgroundStore.setRunError('boom');
		playgroundStore.setFileTreeVisible(false);
		playgroundStore.toggleFileTree(); // → true

		const fileCountBefore = get(playgroundStore).files.length;
		playgroundStore.resetRunSession();

		const state = get(playgroundStore);
		expect(state.runStatus).toBe('idle');
		expect(state.runSessionId).toBeNull();
		expect(state.outputCursor).toBe(0);
		expect(state.runError).toBeNull();
		expect(state.files.length).toBe(fileCountBefore);
		expect(state.fileTreeVisible).toBe(true);
	});

	it('GATE: tidak ada kombinasi idle tapi sessionId masih aktif', () => {
		playgroundStore.startRunSession('sess-1', 'running');
		playgroundStore.resetRunSession();
		const state = get(playgroundStore);
		expect(state.runStatus === 'idle' ? state.runSessionId === null : true).toBe(true);
		// dan kebalikannya: sessionId aktif ⇒ status bukan idle
		playgroundStore.startRunSession('sess-2', 'running');
		const s2 = get(playgroundStore);
		expect(s2.runSessionId !== null ? s2.runStatus !== 'idle' : true).toBe(true);
	});

	it('updateRunStatus transisi queued → compiling → running', () => {
		playgroundStore.startRunSession('sess-1', 'queued');
		playgroundStore.updateRunStatus('compiling');
		playgroundStore.updateRunStatus('running');
		expect(get(playgroundStore).runStatus).toBe('running');
	});

	it('setWaitingForInput mengubah state dan dibersihkan saat finishRun/resetRunSession', () => {
		playgroundStore.startRunSession('sess-1', 'running');
		expect(get(playgroundStore).waitingForInput).toBe(false);

		playgroundStore.setWaitingForInput(true);
		expect(get(playgroundStore).waitingForInput).toBe(true);

		playgroundStore.finishRun('exited');
		expect(get(playgroundStore).waitingForInput).toBe(false);

		playgroundStore.setWaitingForInput(true);
		expect(get(playgroundStore).waitingForInput).toBe(true);

		playgroundStore.resetRunSession();
		expect(get(playgroundStore).waitingForInput).toBe(false);
	});
});

describe('playgroundStore default files & content', () => {
	beforeEach(() => {
		playgroundStore.reset();
	});

	it('file default memuat template C dengan scanf dan template Python dengan input', () => {
		const state = get(playgroundStore);
		const cFile = state.files.find((f) => f.name === 'main.c');
		const pyFile = state.files.find((f) => f.name === 'main.py');

		expect(cFile).toBeDefined();
		expect(cFile?.content).toContain('scanf');
		expect(cFile?.content).toContain('Siapa nama kamu?');

		expect(pyFile).toBeDefined();
		expect(pyFile?.content).toContain('input(');
		expect(pyFile?.content).toContain('Siapa nama kamu?');
	});

	it('addFile untuk main.c dan main.py secara otomatis mengisi template default jika kosong', () => {
		const cId = playgroundStore.addFile('main.c');
		const pyId = playgroundStore.addFile('main.py');
		const otherId = playgroundStore.addFile('helper.c');

		const state = get(playgroundStore);
		const cFile = state.files.find((f) => f.id === cId);
		const pyFile = state.files.find((f) => f.id === pyId);
		const otherFile = state.files.find((f) => f.id === otherId);

		expect(cFile?.content).toContain('scanf');
		expect(pyFile?.content).toContain('input(');
		expect(otherFile?.content).toBe('');
	});
});
