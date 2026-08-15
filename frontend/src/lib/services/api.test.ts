import { describe, it, expect, vi, afterEach } from 'vitest';
import {
	quizAttemptBeacon,
	resetProgress,
	submitQuizAttempt,
	trackProgress,
	type QuizAttemptSubmission
} from './api';

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

describe('submitQuizAttempt', () => {
	function payload(overrides: Partial<QuizAttemptSubmission> = {}): QuizAttemptSubmission {
		return {
			attempt_id: '3f2f8c24-8c1a-4b2a-9e5a-1a2b3c4d5e6f',
			token: 'student-token',
			lesson_name: 'quiz_test',
			status: 'terminated',
			termination_reason: 'focus_lost',
			score: '2/4',
			occurred_at: '2026-08-09T14:04:44.000Z',
			started_at: '2026-08-09T14:03:00.000Z',
			visibility_event_count: 1,
			answers: [],
			...overrides
		};
	}

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('mengirim POST ke /quiz-attempts/submit dengan JSON fields lengkap', async () => {
		const { calls, customFetch } = captureFetch();
		const p = payload();
		await submitQuizAttempt(p, customFetch);

		expect(calls).toHaveLength(1);
		expect(calls[0].url).toBe('/api/quiz-attempts/submit');
		expect(calls[0].init.method).toBe('POST');
		expect((calls[0].init.headers as Record<string, string>)['Content-Type']).toBe('application/json');
		const body = JSON.parse(String(calls[0].init.body));
		expect(body).toEqual({
			attempt_id: p.attempt_id,
			token: p.token,
			lesson_name: 'quiz_test',
			status: 'terminated',
			termination_reason: 'focus_lost',
			score: '2/4',
			occurred_at: p.occurred_at,
			started_at: p.started_at,
			visibility_event_count: 1,
			answers: []
		});
	});

	it('submit completed memakai status submitted + termination_reason null', async () => {
		const { calls, customFetch } = captureFetch();
		await submitQuizAttempt(payload({ status: 'submitted', termination_reason: null }), customFetch);
		const body = JSON.parse(String(calls[0].init.body));
		expect(body.status).toBe('submitted');
		expect(body.termination_reason).toBeNull();
	});
});

describe('quizAttemptBeacon', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('memakai sendBeacon dengan Blob application/json di endpoint yang sama', async () => {
		const sendBeacon = vi
			.fn<(url: string, blob: Blob) => boolean>()
			.mockReturnValue(true);
		vi.stubGlobal('navigator', { sendBeacon });

		const p: QuizAttemptSubmission = {
				attempt_id: '3f2f8c24-8c1a-4b2a-9e5a-1a2b3c4d5e6f',
				token: 'student-token',
				lesson_name: 'quiz_test',
				status: 'terminated',
				termination_reason: 'focus_lost',
				score: '2/4',
				occurred_at: '2026-08-09T14:04:44.000Z',
				started_at: '2026-08-09T14:03:00.000Z',
				visibility_event_count: 1,
				answers: [],
			};

			const ok = quizAttemptBeacon(p);
			expect(ok).toBe(true);
			expect(sendBeacon).toHaveBeenCalledTimes(1);
			expect(sendBeacon.mock.calls[0][0]).toBe('/api/quiz-attempts/submit');
			const blob = sendBeacon.mock.calls[0][1];
			expect(blob.type).toBe('application/json');
			const text = await blob.text();
			const body = JSON.parse(text);
			expect(body).toEqual({
				attempt_id: p.attempt_id,
				token: p.token,
				lesson_name: 'quiz_test',
				status: 'terminated',
				termination_reason: 'focus_lost',
				score: '2/4',
				occurred_at: p.occurred_at,
				started_at: p.started_at,
				visibility_event_count: 1,
				answers: p.answers
			});
		});

	it('tidak melempar dan mengembalikan false saat sendBeacon tidak tersedia', () => {
		vi.stubGlobal('navigator', {});
		const p: QuizAttemptSubmission = {
			attempt_id: '3f2f8c24-8c1a-4b2a-9e5a-1a2b3c4d5e6f',
			token: 'student-token',
			lesson_name: 'quiz_test',
			status: 'terminated',
			termination_reason: 'focus_lost',
			score: '2/4',
			occurred_at: '2026-08-09T14:04:44.000Z',
			started_at: '2026-08-09T14:03:00.000Z',
			visibility_event_count: 1,
			answers: []
		};
		expect(quizAttemptBeacon(p)).toBe(false);
	});
});
