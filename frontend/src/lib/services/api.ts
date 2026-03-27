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
import type { CompileRequest, CompileResponse } from '$types/compiler';
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
