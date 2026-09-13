export interface RunRequest {
	id: string;
	language: 'c' | 'python';
	code: string;
	/** SharedArrayBuffer for interactive stdin (optional) */
	stdinBuffer?: SharedArrayBuffer;
	/** Prefilled stdin for non-interactive / test runner (optional) */
	stdinText?: string;
}

export type WorkerMessage =
	| { type: 'stdout'; text: string }
	| { type: 'stderr'; text: string }
	| { type: 'waiting_for_input' }
	| { type: 'done'; success: boolean; error?: string; executionTimeMs: number }
	| { type: 'ready' };
