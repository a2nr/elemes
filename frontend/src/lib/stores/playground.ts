/**
 * Playground Store
 *
 * State untuk route /playground: file tree (C/Python) + console output/input.
 * Mengikuti pola stores lain di proyek (svelte/store writable).
 */

import { writable } from 'svelte/store';

export interface PlaygroundFile {
	id: string;
	name: string;
	content: string;
	modified: boolean;
}

export type ConsoleLineType = 'input' | 'output' | 'error' | 'info';

export interface ConsoleLine {
	type: ConsoleLineType;
	text: string;
	timestamp: number;
}

export type RunState = 'idle' | 'running';

interface PlaygroundState {
	files: PlaygroundFile[];
	activeFileId: string;
	consoleHistory: ConsoleLine[];
	consoleInput: string;
	stdinQueue: string[];
	consoleVisible: boolean;
	running: boolean;
}

const STORAGE_KEY = 'elemes_playground_files_v1';

const DEFAULT_C_CONTENT = `#include <stdio.h>

int main() {
    printf("Halo, dunia!\\n");
    return 0;
}
`;

const DEFAULT_PY_CONTENT = `# Program Python sederhana
nama = input("Siapa nama kamu? ")
print(f"Halo, {nama}! Selamat belajar pemrograman.")
`;

function generateId(): string {
	return 'f_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
}

function defaultFiles(): PlaygroundFile[] {
	return [
		{ id: generateId(), name: 'main.c', content: DEFAULT_C_CONTENT, modified: false },
		{ id: generateId(), name: 'main.py', content: DEFAULT_PY_CONTENT, modified: false }
	];
}

function loadPersistedFiles(): PlaygroundFile[] {
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (!raw) return defaultFiles();
		const parsed = JSON.parse(raw) as PlaygroundFile[];
		if (!Array.isArray(parsed) || parsed.length === 0) return defaultFiles();
		return parsed.filter((f) => f && typeof f.name === 'string');
	} catch {
		return defaultFiles();
	}
}

function persistFiles(files: PlaygroundFile[]) {
	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(files));
	} catch {
		// storage penuh / private mode — abaikan
	}
}

function initialState(): PlaygroundState {
	const files = loadPersistedFiles();
	return {
		files,
		activeFileId: files[0]?.id ?? '',
		consoleHistory: [],
		consoleInput: '',
		stdinQueue: [],
		consoleVisible: true,
		running: false
	};
}

function createPlaygroundStore() {
	const { subscribe, update, set } = writable<PlaygroundState>(initialState());

	return {
		subscribe,

		addFile: (name: string): string => {
			const id = generateId();
			update((s) => {
				const files = [...s.files, { id, name, content: '', modified: true }];
				persistFiles(files);
				return { ...s, files, activeFileId: id };
			});
			return id;
		},

		renameFile: (id: string, name: string) => {
			update((s) => {
				const files = s.files.map((f) =>
					f.id === id ? { ...f, name, modified: true } : f
				);
				persistFiles(files);
				return { ...s, files };
			});
		},

		updateFile: (id: string, content: string) => {
			update((s) => {
				const files = s.files.map((f) =>
					f.id === id ? { ...f, content, modified: true } : f
				);
				persistFiles(files);
				return { ...s, files };
			});
		},

		deleteFile: (id: string) => {
			update((s) => {
				const files = s.files.filter((f) => f.id !== id);
				persistFiles(files);
				return {
					...s,
					files,
					activeFileId:
						s.activeFileId === id ? (files[0]?.id ?? '') : s.activeFileId
				};
			});
		},

		setActiveFile: (id: string) => {
			update((s) => ({ ...s, activeFileId: id }));
		},

		markSaved: (id: string) => {
			update((s) => {
				const files = s.files.map((f) =>
					f.id === id ? { ...f, modified: false } : f
				);
				persistFiles(files);
				return { ...s, files };
			});
		},

		appendConsole: (line: ConsoleLine) => {
			update((s) => ({
				...s,
				consoleHistory: [...s.consoleHistory, line].slice(-500)
			}));
		},

		clearConsole: () => {
			update((s) => ({ ...s, consoleHistory: [] }));
		},

		setConsoleInput: (text: string) => {
			update((s) => ({ ...s, consoleInput: text }));
		},

		enqueueStdin: (text: string) => {
			const trimmed = text.trim();
			if (!trimmed) return;
			update((s) => ({ ...s, stdinQueue: [...s.stdinQueue, trimmed] }));
		},

		consumeStdin: (): string => {
			let stdin = '';
			update((s) => {
				stdin = s.stdinQueue.map((line) => line + '\n').join('') + s.consoleInput;
				return { ...s, stdinQueue: [], consoleInput: '' };
			});
			return stdin;
		},

		clearStdinQueue: () => {
			update((s) => ({ ...s, stdinQueue: [] }));
		},

		toggleConsole: () => {
			update((s) => ({ ...s, consoleVisible: !s.consoleVisible }));
		},

		setRunning: (running: boolean) => {
			update((s) => ({ ...s, running }));
		},

		reset: () => {
			const fresh = initialState();
			update(() => fresh);
		}
	};
}

export const playgroundStore = createPlaygroundStore();
