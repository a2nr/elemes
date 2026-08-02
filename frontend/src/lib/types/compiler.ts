export interface CompileRequest {
	code: string;
	language: string;
	token?: string;
	stdin?: string;
}

export interface CompileResponse {
	success: boolean;
	output: string;
	error: string;
}

// ── Interactive session (PTY) ───────────────────────────────────────

export type InteractiveRunStatus =
	| 'queued'
	| 'compiling'
	| 'running'
	| 'exited'
	| 'error'
	| 'stopped'
	| 'expired';

export interface CompilerFile {
	name: string;
	content: string;
}

export interface StartSessionRequest {
	language: 'c' | 'python';
	files: CompilerFile[];
	/** Entry point untuk Python; untuk C diabaikan (semua .c dikompilasi). */
	active_file?: string;
	/** Prefilled stdin (kompatibilitas pola lama). */
	stdin?: string;
	token?: string;
}

export interface SessionPollResponse {
	session_id: string;
	status: InteractiveRunStatus;
	/** Delta output sejak cursor terakhir. */
	output: string;
	cursor: number;
	truncated: boolean;
	exit_code: number | null;
	error: string | null;
}

export interface SessionStopResponse {
	success: boolean;
	status: InteractiveRunStatus;
	error: string | null;
}
