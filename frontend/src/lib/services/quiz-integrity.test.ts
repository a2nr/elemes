import { describe, it, expect } from 'vitest';
import {
	createAttemptId,
	isFocusLossEvent,
	QUIZ_TERMINATION_REASONS,
	shouldShowQuizReview,
	type QuizTerminationReason
} from './quiz-integrity';

describe('isFocusLossEvent', () => {
	it('hidden + visibilitychange + belum terminated → true', () => {
		expect(isFocusLossEvent('visibilitychange', 'hidden', false)).toBe(true);
	});

	it('visible + visibilitychange → false (kembali fokus tidak memicu)', () => {
		expect(isFocusLossEvent('visibilitychange', 'visible', false)).toBe(false);
	});

	it('blur + belum terminated → true (fallback desktop)', () => {
		expect(isFocusLossEvent('blur', 'visible', false)).toBe(true);
		expect(isFocusLossEvent('blur', 'hidden', false)).toBe(true);
	});

	it('event apa pun setelah terminated → false (idempotent)', () => {
		expect(isFocusLossEvent('visibilitychange', 'hidden', true)).toBe(false);
		expect(isFocusLossEvent('blur', 'hidden', true)).toBe(false);
		expect(isFocusLossEvent('visibilitychange', 'visible', true)).toBe(false);
	});
});

describe('QuizTerminationReason', () => {
	it('reason bersifat typed — daftar nilai tetap terkontrol', () => {
		// Compile-time: setiap nilai harus anggota union QuizTerminationReason.
		const reasons: QuizTerminationReason[] = [...QUIZ_TERMINATION_REASONS];
		expect(reasons).toEqual([
			'focus_lost',
			'spa_navigation',
			'page_unload',
			'user_exit',
			'completed'
		]);
	});

	it('nilai arbitrary tidak lolos union type (runtime guard konsisten)', () => {
		const bogus: unknown = 'minimize_app';
		const asReason = bogus as QuizTerminationReason;
		expect(QUIZ_TERMINATION_REASONS).not.toContain(asReason);
	});
});

describe('shouldShowQuizReview', () => {
	it('focus_lost → false (pembahasan disembunyikan)', () => {
		expect(shouldShowQuizReview('focus_lost')).toBe(false);
	});

	it('completed → true (penyelesaian normal menampilkan pembahasan)', () => {
		expect(shouldShowQuizReview('completed')).toBe(true);
	});

	it('exit penalti lain tetap menampilkan pembahasan', () => {
		expect(shouldShowQuizReview('user_exit')).toBe(true);
		expect(shouldShowQuizReview('spa_navigation')).toBe(true);
		expect(shouldShowQuizReview('page_unload')).toBe(true);
	});

	it('null (belum ada termination / kunjungan ulang) → true', () => {
		expect(shouldShowQuizReview(null)).toBe(true);
	});
});

describe('createAttemptId', () => {
	it('menghasilkan UUID berformat canonical 8-4-4-4-12', () => {
		const id = createAttemptId();
		expect(id).toMatch(
			/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
		);
	});

	it('dua panggilan menghasilkan nilai berbeda', () => {
		expect(createAttemptId()).not.toBe(createAttemptId());
	});
});
