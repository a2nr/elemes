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

// ── Lesson progress (unified exercise + quiz) ─────────────────────

export interface ExerciseProgressPayload {
	token: string;
	lesson_name: string;
	type: 'exercise';
}

export interface QuizProgressPayload {
	token: string;
	lesson_name: string;
	type: 'quiz';
	attempt_id: string;
	status: 'submitted' | 'terminated';
	termination_reason: string | null;
	score: string;
	occurred_at: string;
	started_at: string;
	visibility_event_count: number;
	answers: Array<{
		question_id: string;
		selected_option_id: string | null;
		is_correct: boolean;
		category: 'evaluasi' | 'diagnostik';
		type: 'mcq' | 'flashcard';
	}>;
}

export type LessonProgressPayload = ExerciseProgressPayload | QuizProgressPayload;

/** Answers returned by the backend in GET /api/lesson-progress (attempt audit). */
export interface LessonProgressAnswer {
	question_id: string;
	selected_option_id: string | null;
	is_correct: boolean;
	category: 'evaluasi' | 'diagnostik';
	type: 'mcq' | 'flashcard';
}

export interface LessonProgressResponse {
	success: boolean;
	idempotent?: boolean;
	attempt_id?: string;
	message?: string;
}

export async function submitLessonProgress(
	payload: LessonProgressPayload,
	customFetch: typeof fetch = fetch
): Promise<LessonProgressResponse> {
	const res = await customFetch('/api/lesson-progress', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(payload)
	});
	return res.json();
}

export function lessonProgressBeacon(payload: LessonProgressPayload): boolean {
	if (typeof navigator === 'undefined' || typeof navigator.sendBeacon !== 'function') return false;
	const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
	return navigator.sendBeacon('/api/lesson-progress', blob);
}

export interface LessonProgressFetchResponse {
	success: boolean;
	lesson_name?: string;
	state?: string;
	exercise_passed?: boolean | null;
	quiz_score_earned?: number | null;
	quiz_score_total?: number | null;
	composite_percent?: number | null;
	attempt_id?: string | null;
	attempt_status?: string | null;
	termination_reason?: string | null;
	attempt_score?: string | null;
	attempt_started_at?: string | null;
	attempt_finished_at?: string | null;
	answers?: Array<LessonProgressAnswer>;
}

export async function fetchLessonProgress(
	lessonName: string,
	token: string,
	customFetch: typeof fetch = fetch
): Promise<LessonProgressFetchResponse> {
	const url = `/api/lesson-progress/${encodeURIComponent(lessonName)}?token=${encodeURIComponent(token)}`;
	const res = await customFetch(url);
	return res.json();
}
