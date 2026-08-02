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

	it('consumeStdin mengembalikan seluruh antrean + draft, digabung dengan newline, lalu mengosongkan', () => {
		playgroundStore.enqueueStdin('Budi');
		playgroundStore.enqueueStdin('17');
		playgroundStore.setConsoleInput('draft yang belum dikirim');
		const stdin = playgroundStore.consumeStdin();
		expect(stdin).toBe('Budi\n17\ndraft yang belum dikirim');
		const state = get(playgroundStore);
		expect(state.stdinQueue).toEqual([]);
		expect(state.consoleInput).toBe('');
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
});
