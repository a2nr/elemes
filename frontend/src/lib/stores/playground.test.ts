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
