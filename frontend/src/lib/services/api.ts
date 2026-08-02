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
	studentToken: string,
	lessonName: string,
	customFetch = fetch
) {
	return post<{ success: boolean; message: string }>(
		'/reset-progress',
		{ teacher_token: teacherToken, student_token: studentToken, lesson_name: lessonName },
		customFetch
	);
}
