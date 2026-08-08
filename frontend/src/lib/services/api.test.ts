import { describe, it, expect } from 'vitest';
import { resetProgress, trackProgress } from './api';

function captureFetch() {
	const calls: { url: string; init: RequestInit }[] = [];
	const customFetch = async (input: RequestInfo | URL, init?: RequestInit) => {
		calls.push({ url: String(input), init: init ?? {} });
		return { json: async () => ({ success: true }) } as Response;
	};
	return { calls, customFetch };
}

describe('resetProgress', () => {
	it('mengirim student_id (bukan student_token) — kontrak keamanan baru', async () => {
		const { calls, customFetch } = captureFetch();
		await resetProgress('teacher-token', 'student-uuid-123', 'hello_world', customFetch);

		expect(calls).toHaveLength(1);
		expect(calls[0].url).toBe('/api/reset-progress');
		const body = JSON.parse(String(calls[0].init.body));
		expect(body.teacher_token).toBe('teacher-token');
		expect(body.student_id).toBe('student-uuid-123');
		expect(body.lesson_name).toBe('hello_world');
		expect('student_token' in body).toBe(false);
	});
});

describe('trackProgress', () => {
	it('tetap mengirim token siswa + status', async () => {
		const { calls, customFetch } = captureFetch();
		await trackProgress('student-token', 'hello_world', 'completed', customFetch);

		expect(calls[0].url).toBe('/api/track-progress');
		const body = JSON.parse(String(calls[0].init.body));
		expect(body).toEqual({
			token: 'student-token',
			lesson_name: 'hello_world',
			status: 'completed'
		});
	});
});
