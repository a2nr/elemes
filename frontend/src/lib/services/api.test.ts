import { describe, it, expect, vi, afterEach } from 'vitest';
import {
	resetProgress,
	submitLessonProgress,
	lessonProgressBeacon,
	fetchLessonProgress,
	type ExerciseProgressPayload,
	type QuizProgressPayload
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

describe('submitLessonProgress (exercise)', () => {
	it('mengirim POST ke /api/lesson-progress dengan type exercise', async () => {
		const { calls, customFetch } = captureFetch();
		const payload: ExerciseProgressPayload = {
			token: 'student-token',
			lesson_name: 'hello_world',
			type: 'exercise'
		};
		await submitLessonProgress(payload, customFetch);

		expect(calls).toHaveLength(1);
		expect(calls[0].url).toBe('/api/lesson-progress');
		expect(calls[0].init.method).toBe('POST');
		expect((calls[0].init.headers as Record<string, string>)['Content-Type']).toBe(
			'application/json'
		);
		const body = JSON.parse(String(calls[0].init.body));
		expect(body).toEqual({
			token: 'student-token',
			lesson_name: 'hello_world',
			type: 'exercise'
		});
	});
});

describe('submitLessonProgress (quiz)', () => {
	function payload(overrides: Partial<QuizProgressPayload> = {}): QuizProgressPayload {
		return {
			token: 'student-token',
			lesson_name: 'quiz_test',
			type: 'quiz',
			attempt_id: '3f2f8c24-8c1a-4b2a-9e5a-1a2b3c4d5e6f',
			status: 'terminated',
			termination_reason: 'focus_lost',
			score: '2/4',
			occurred_at: '2026-08-09T14:04:44.000Z',
			started_at: '2026-08-09T14:03:00.000Z',
			visibility_event_count: 1,
			answers: [
				{
					question_id: 'q1',
					selected_option_id: 'o2',
					is_correct: false,
					category: 'evaluasi',
					type: 'mcq'
				}
			],
			...overrides
		};
	}

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('mengirim POST ke /api/lesson-progress dengan JSON fields kuis lengkap', async () => {
		const { calls, customFetch } = captureFetch();
		const p = payload();
		await submitLessonProgress(p, customFetch);

		expect(calls).toHaveLength(1);
		expect(calls[0].url).toBe('/api/lesson-progress');
		expect(calls[0].init.method).toBe('POST');
		expect((calls[0].init.headers as Record<string, string>)['Content-Type']).toBe(
			'application/json'
		);
		const body = JSON.parse(String(calls[0].init.body));
		expect(body).toEqual({
			token: p.token,
			lesson_name: 'quiz_test',
			type: 'quiz',
			attempt_id: p.attempt_id,
			status: 'terminated',
			termination_reason: 'focus_lost',
			score: '2/4',
			occurred_at: p.occurred_at,
			started_at: p.started_at,
			visibility_event_count: 1,
			answers: p.answers
		});
	});

	it('submit completed memakai status submitted + termination_reason null', async () => {
		const { calls, customFetch } = captureFetch();
		await submitLessonProgress(
			payload({ status: 'submitted', termination_reason: null }),
			customFetch
		);
		const body = JSON.parse(String(calls[0].init.body));
		expect(body.status).toBe('submitted');
		expect(body.termination_reason).toBeNull();
	});
});

describe('lessonProgressBeacon', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('memakai sendBeacon dengan Blob application/json di /api/lesson-progress', async () => {
		const sendBeacon = vi
			.fn<(url: string, blob: Blob) => boolean>()
			.mockReturnValue(true);
		vi.stubGlobal('navigator', { sendBeacon });

		const p: QuizProgressPayload = {
			token: 'student-token',
			lesson_name: 'quiz_test',
			type: 'quiz',
			attempt_id: '3f2f8c24-8c1a-4b2a-9e5a-1a2b3c4d5e6f',
			status: 'terminated',
			termination_reason: 'focus_lost',
			score: '2/4',
			occurred_at: '2026-08-09T14:04:44.000Z',
			started_at: '2026-08-09T14:03:00.000Z',
			visibility_event_count: 1,
			answers: []
		};

		const ok = lessonProgressBeacon(p);
		expect(ok).toBe(true);
		expect(sendBeacon).toHaveBeenCalledTimes(1);
		expect(sendBeacon.mock.calls[0][0]).toBe('/api/lesson-progress');
		const blob = sendBeacon.mock.calls[0][1];
		expect(blob.type).toBe('application/json');
		const text = await blob.text();
		const body = JSON.parse(text);
		expect(body).toEqual({
			token: p.token,
			lesson_name: 'quiz_test',
			type: 'quiz',
			attempt_id: p.attempt_id,
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
		const p: ExerciseProgressPayload = {
			token: 'student-token',
			lesson_name: 'quiz_test',
			type: 'exercise'
		};
		expect(lessonProgressBeacon(p)).toBe(false);
	});
});

describe('fetchLessonProgress', () => {
	it('mengirim GET ke /api/lesson-progress/<lesson>?token=...', async () => {
		const { calls, customFetch } = captureFetch();
		await fetchLessonProgress('quiz_test', 'student-token', customFetch);

		expect(calls).toHaveLength(1);
		expect(calls[0].url).toBe(
			'/api/lesson-progress/quiz_test?token=student-token'
		);
		expect(calls[0].init.method).toBeUndefined();
	});

	it('meng-encodeURIComponent lesson_name dan token', async () => {
		const { calls, customFetch } = captureFetch();
		await fetchLessonProgress('lesson with space', 'tok/with+slash', customFetch);

		expect(calls[0].url).toBe(
			'/api/lesson-progress/lesson%20with%20space?token=tok%2Fwith%2Bslash'
		);
	});
});
