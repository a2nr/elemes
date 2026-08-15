/**
 * Flask API client.
 *
 * All backend calls go through this module so the base URL and headers
 * are managed in one place.
 *
 * In dev the Vite proxy rewrites /api/* → Flask :5000.
 * In production the reverse-proxy does the same.
 */

import type { LoginResponse, ValidateTokenResponse } from '$types/auth';
import type {
	CompileRequest,
	CompileResponse,
	SessionPollResponse,
	SessionStopResponse,
	StartSessionRequest
} from '$types/compiler';
import type { Lesson, LessonContent } from '$types/lesson';
import type { QuizTerminationReason } from './quiz-integrity';

const BASE = '/api';

async function post<T>(path: string, body: unknown, customFetch = fetch): Promise<T> {
	const res = await customFetch(`${BASE}${path}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
	return res.json() as Promise<T>;
}

async function get<T>(path: string, customFetch = fetch): Promise<T> {
	const res = await customFetch(`${BASE}${path}`);
	return res.json() as Promise<T>;
}

async function del<T>(path: string, customFetch = fetch): Promise<T> {
	const res = await customFetch(`${BASE}${path}`, { method: 'DELETE' });
	return res.json() as Promise<T>;
}

// ── Auth ─────────────────────────────────────────────────────────────

export function login(token: string, customFetch = fetch) {
	return post<LoginResponse>('/login', { token }, customFetch);
}

export function logout(customFetch = fetch) {
	return post<{ success: boolean; message: string }>('/logout', {}, customFetch);
}

export function validateToken(token: string, customFetch = fetch) {
	return post<ValidateTokenResponse>('/validate-token', { token }, customFetch);
}

// ── Lessons ──────────────────────────────────────────────────────────

export function getLessons(customFetch = fetch) {
	return get<{ lessons: Lesson[]; home_content: string }>('/lessons', customFetch);
}

export function getLesson(slug: string, customFetch = fetch, token = '') {
	const query = token ? `?token=${encodeURIComponent(token)}` : '';
	return get<LessonContent>(`/lesson/${slug}.json${query}`, customFetch);
}

export function getKeyText(filename: string, customFetch = fetch) {
	return get<{ success: boolean; key_text: string }>(`/get-key-text/${filename}`, customFetch);
}

// ── Compile ──────────────────────────────────────────────────────────

export function compileCode(req: CompileRequest, customFetch = fetch) {
	return post<CompileResponse>('/compile', req, customFetch);
}

// ── Interactive session (PTY) ───────────────────────────────────────

export function startCompileSession(req: StartSessionRequest, customFetch = fetch) {
	return post<SessionPollResponse>('/compile/sessions', req, customFetch);
}

export function readCompileSession(sessionId: string, cursor: number, customFetch = fetch) {
	const query = cursor > 0 ? `?cursor=${cursor}` : '';
	return get<SessionPollResponse>(`/compile/sessions/${sessionId}${query}`, customFetch);
}

export function sendCompileInput(sessionId: string, text: string, customFetch = fetch) {
	return post<SessionPollResponse>(`/compile/sessions/${sessionId}/input`, { text }, customFetch);
}

export function stopCompileSession(sessionId: string, customFetch = fetch) {
	return del<SessionStopResponse>(`/compile/sessions/${sessionId}`, customFetch);
}

export interface VelxioCompileRequest {
	code: string;
	board_fqbn?: string;
}

export interface VelxioCompileResponse {
	success: boolean;
	hex_content: string | null;
	binary_content: string | null;
	binary_type: string | null;
	has_wifi: boolean;
	stdout: string;
	stderr: string;
	error: string | null;
	core_install_log: string | null;
}

export function getHexContent(req: VelxioCompileRequest, customFetch = fetch) {
	return post<VelxioCompileResponse>('/velxio-compile', req, customFetch);
}

// ── Progress ─────────────────────────────────────────────────────────

export function trackProgress(
	token: string,
	lessonName: string,
	status = 'completed',
	customFetch = fetch
) {
	return post<{ success: boolean; message: string }>(
		'/track-progress',
		{ token, lesson_name: lessonName, status },
		customFetch
	);
}

export function resetProgress(
	teacherToken: string,
	studentId: string,
	lessonName: string,
	customFetch = fetch
) {
	return post<{ success: boolean; message: string }>(
		'/reset-progress',
		{ teacher_token: teacherToken, student_id: studentId, lesson_name: lessonName },
		customFetch
	);
}

// ── Quiz attempt (anti-cheat / focus-loss) ────────────────────────

export interface QuizAttemptSubmission {
	attempt_id: string;
	token: string;
	lesson_name: string;
	status: 'submitted' | 'terminated';
	termination_reason: QuizTerminationReason | null;
	score: string;
	occurred_at: string;
	started_at: string;
	visibility_event_count: number;
	/** Ringkasan per-soal untuk review-after-refresh + breakdown kategori. */
	answers: QuizAnswerPayload[];
}

export interface QuizAnswerPayload {
	question_id: string;
	selected_option_id: string | null;
	is_correct: boolean;
	category: 'evaluasi' | 'diagnostik';
}

export interface QuizAttemptSubmitResponse {
	success: boolean;
	idempotent?: boolean;
	attempt_id?: string;
	message: string;
}

/** Attempt yang dikembalikan endpoint GET (untuk review-after-refresh). */
export interface QuizAttemptFetchResponse {
	success: boolean;
	attempt_id: string;
	status: 'submitted' | 'terminated';
	termination_reason: QuizTerminationReason | null;
	score: string;
	score_earned?: number | null;
	score_total?: number | null;
	started_at?: string | null;
	finished_at?: string | null;
	answers: QuizAnswerPayload[];
}

/**
 * Submit finalisasi kuis (satu attempt) — endpoint atomic di backend.
 * Dipakai untuk exit path normal: tombol Keluar, SPA navigation, finish.
 */
export function submitQuizAttempt(
	payload: QuizAttemptSubmission,
	customFetch = fetch
): Promise<QuizAttemptSubmitResponse> {
	return post<QuizAttemptSubmitResponse>('/quiz-attempts/submit', payload, customFetch);
}

/**
 * Fetch attempt kuis siswa untuk sebuah lesson (GET /quiz-attempts/<lesson>).
 * Dipakai saat halaman dibuka kembali supaya review per-soal tetap tampil
 * setelah refresh (one-attempt policy → session hilang, tapi attempt persist).
 */
export function fetchQuizAttempt(
	token: string,
	lessonName: string,
	customFetch = fetch
): Promise<QuizAttemptFetchResponse> {
	const query = `token=${encodeURIComponent(token)}`;
	return get<QuizAttemptFetchResponse>(`/quiz-attempts/${lessonName}?${query}`, customFetch);
}

/**
 * Kirim attempt via `navigator.sendBeacon` (synchronous, fire-and-forget).
 * Dipakai untuk event lifecycle yang bisa membuat browser suspend
 * (focus_lost / page_unload) — tidak boleh mengandalkan `await`.
 *
 * Mengembalikan `false` bila beacon tidak tersedia/gagal; TIDAK melempar.
 */
export function quizAttemptBeacon(payload: QuizAttemptSubmission): boolean {
	if (typeof navigator === 'undefined' || typeof navigator.sendBeacon !== 'function') {
		return false;
	}
	const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
	return navigator.sendBeacon('/api/quiz-attempts/submit', blob);
}
