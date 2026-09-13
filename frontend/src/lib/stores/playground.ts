/**
 * Playground Store
 *
 * State untuk route /playground: file tree (C/Python) + console output/input.
 * Mengikuti pola stores lain di proyek (svelte/store writable).
 *
 * Lifecycle sesi interaktif:
 *   idle → queued/compiling/running → exited/error/stopped → idle
 *   'stopping' = DELETE session sedang berlangsung.
 */

import { writable } from 'svelte/store';
import type { InteractiveRunStatus } from '$types/compiler';

export interface PlaygroundFile {
	id: string;
	name: string;
	content: string;
	modified: boolean;
}

export type ConsoleLineType = 'input' | 'output' | 'error' | 'info';

export interface ConsoleLine {
	id: string;
	type: ConsoleLineType;
	text: string;
	timestamp: number;
}

/** Status sesi dari sisi UI. 'idle' = tidak ada sesi aktif. */
export type RunStatus = 'idle' | InteractiveRunStatus | 'stopping';

interface PlaygroundState {
	files: PlaygroundFile[];
	activeFileId: string;
	consoleHistory: ConsoleLine[];
	consoleInput: string;
	stdinQueue: string[];
	consoleVisible: boolean;
	fileTreeVisible: boolean;
	/** Status runtime sesi interaktif (bukan sekadar boolean). */
	runStatus: RunStatus;
	/** ID sesi interaktif di worker, null saat idle. */
	runSessionId: string | null;
	/** Byte cursor output terakhir yang sudah di-append ke console. */
	outputCursor: number;
	/** Pesan error runtime/sesi terakhir (null saat tidak ada). */
	runError: string | null;
	/** Apakah sesi sedang menunggu input pengguna. */
	waitingForInput: boolean;
}

const STORAGE_KEY = 'elemes_playground_files_v1';

export const DEFAULT_C_CONTENT = `#include <stdio.h>

int main() {
    char nama[50];
    printf("Siapa nama kamu? ");
    scanf("%s", nama);
    printf("Halo, %s! Selamat belajar pemrograman.\\n", nama);
    return 0;
}
`;

export const DEFAULT_PY_CONTENT = `# Program Python sederhana
nama = input("Siapa nama kamu? ")
print(f"Halo, {nama}! Selamat belajar pemrograman.")
`;

const OLD_DEFAULT_C = `#include <stdio.h>

int main() {
    printf("Halo, dunia!\\n");
    return 0;
}
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
		const files = parsed.filter((f) => f && typeof f.name === 'string');
		let hasChanges = false;
		const migrated = files.map((f) => {
			if (f.name === 'main.c' && (!f.content || f.content.trim() === OLD_DEFAULT_C.trim())) {
				hasChanges = true;
				return { ...f, content: DEFAULT_C_CONTENT };
			}
			return f;
		});
		if (hasChanges) {
			persistFiles(migrated);
		}
		return migrated;
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
		fileTreeVisible: true,
		runStatus: 'idle',
		runSessionId: null,
		outputCursor: 0,
		runError: null,
		waitingForInput: false
	};
}

function createPlaygroundStore() {
	const { subscribe, update, set } = writable<PlaygroundState>(initialState());

	return {
		subscribe,

		// ── File management ──────────────────────────────────────────

		addFile: (name: string, initialContent?: string): string => {
			const id = generateId();
			let content = initialContent ?? '';
			if (!initialContent) {
				if (name === 'main.c') content = DEFAULT_C_CONTENT;
				else if (name === 'main.py') content = DEFAULT_PY_CONTENT;
			}
			update((s) => {
				const files = [...s.files, { id, name, content, modified: true }];
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

		// ── Console ──────────────────────────────────────────────────

		appendConsole: (line: ConsoleLine | Omit<ConsoleLine, 'id'>) => {
			const withId: ConsoleLine =
				'id' in line && line.id
					? (line as ConsoleLine)
					: {
							...(line as Omit<ConsoleLine, 'id'>),
							id:
								typeof crypto !== 'undefined' && crypto.randomUUID
									? crypto.randomUUID()
									: 'cl_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8)
						};
			update((s) => ({
				...s,
				consoleHistory: [...s.consoleHistory, withId].slice(-500)
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
				stdin = s.stdinQueue.map((line) => line + '\n').join('');
				return { ...s, stdinQueue: [] };
			});
			return stdin;
		},

		clearStdinQueue: () => {
			update((s) => ({ ...s, stdinQueue: [] }));
		},

		toggleConsole: () => {
			update((s) => ({ ...s, consoleVisible: !s.consoleVisible }));
		},

		// ── File tree visibility ─────────────────────────────────────

		setFileTreeVisible: (visible: boolean) => {
			update((s) => ({ ...s, fileTreeVisible: visible }));
		},

		toggleFileTree: () => {
			update((s) => ({ ...s, fileTreeVisible: !s.fileTreeVisible }));
		},

		// ── Interactive session lifecycle ────────────────────────────

		setWaitingForInput: (waiting: boolean) => {
			update((s) => ({ ...s, waitingForInput: waiting }));
		},

		startRunSession: (sessionId: string, status: InteractiveRunStatus) => {
			update((s) => ({
				...s,
				runStatus: status,
				runSessionId: sessionId,
				outputCursor: 0,
				runError: null,
				waitingForInput: false
			}));
		},

		updateRunStatus: (status: RunStatus) => {
			update((s) => ({ ...s, runStatus: status }));
		},

		advanceOutputCursor: (cursor: number) => {
			update((s) => ({
				...s,
				outputCursor: Math.max(s.outputCursor, cursor)
			}));
		},

		setRunError: (error: string) => {
			update((s) => ({ ...s, runError: error }));
		},

		/** Transisi sesi → terminal. Hanya terima status terminal. */
		finishRun: (status: InteractiveRunStatus, error?: string | null) => {
			update((s) => ({
				...s,
				runStatus: status,
				runError: error ?? s.runError,
				waitingForInput: false
			}));
		},

		/** Bersihkan lifecycle sesi sepenuhnya (kembali idle). */
		resetRunSession: () => {
			update((s) => ({
				...s,
				runStatus: 'idle',
				runSessionId: null,
				outputCursor: 0,
				runError: null,
				waitingForInput: false
			}));
		},

		reset: () => {
			const fresh = initialState();
			update(() => fresh);
		}
	};
}

export const playgroundStore = createPlaygroundStore();
