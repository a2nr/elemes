import { describe, it, expect } from 'vitest';
import { detectContentFeatures } from './content-features';
import type { QuizQuestion } from '$types/quiz';

describe('detectContentFeatures', () => {
	it('array kosong/undefined → []', () => {
		expect(detectContentFeatures(undefined)).toEqual([]);
		expect(detectContentFeatures([])).toEqual([]);
	});

	it('mendeteksi mcq evaluasi vs diagnostik secara terpisah', () => {
		const qs: QuizQuestion[] = [
			{ id: 'q-0', type: 'mcq', category: 'evaluasi', options: [] },
			{ id: 'q-1', type: 'mcq', category: 'diagnostik', options: [] }
		];
		const ids = detectContentFeatures(qs).map((f) => f.id);
		expect(ids).toContain('mcq');
		expect(ids).toContain('mcq-diagnostik');
	});

	it('mendeteksi flashcard, image, explanation', () => {
		const qs: QuizQuestion[] = [
			{ id: 'q-0', type: 'flashcard', front: 'F', back: 'B', image: 'x.png' },
			{ id: 'q-1', type: 'mcq', options: [], explanation: 'karena begitu' }
		];
		const ids = detectContentFeatures(qs).map((f) => f.id);
		expect(ids).toEqual(
			expect.arrayContaining(['flashcard', 'has-image', 'has-explanation', 'mcq'])
		);
	});

	it('tidak duplikat feature untuk banyak soal bertipe sama', () => {
		const qs: QuizQuestion[] = [
			{ id: 'q-0', type: 'mcq', options: [] },
			{ id: 'q-1', type: 'mcq', options: [] }
		];
		expect(detectContentFeatures(qs).filter((f) => f.id === 'mcq')).toHaveLength(1);
	});
});
