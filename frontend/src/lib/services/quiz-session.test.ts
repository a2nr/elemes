import { describe, it, expect } from 'vitest';
import type { QuizQuestion } from '../types/quiz';
import {
	createQuizSession,
	answerQuestion,
	acknowledgeQuestion,
	calculateQuizResult
} from './quiz-session';

function makeQuestion(id: string, type: 'mcq' | 'flashcard' = 'mcq', correctIdx = 0): QuizQuestion {
	if (type === 'flashcard') {
		return { id, type: 'flashcard', front: `F-${id}`, back: `B-${id}` };
	}
	return {
		id,
		type: 'mcq',
		question: `Q-${id}`,
		options: [
			{ id: `${id}-o-0`, text: 'A', is_correct: correctIdx === 0 },
			{ id: `${id}-o-1`, text: 'B', is_correct: correctIdx === 1 },
			{ id: `${id}-o-2`, text: 'C', is_correct: correctIdx === 2 }
		]
	};
}

describe('createQuizSession', () => {
	it('does not mutate the source array or its option arrays', () => {
		const source = [makeQuestion('q-0'), makeQuestion('q-1'), makeQuestion('q-2')];
		const srcOrder = source.map((q) => q.id);
		const srcOptOrder = source.map((q) => q.options!.map((o) => o.id));

		createQuizSession(source, () => 0);

		expect(source.map((q) => q.id)).toEqual(srcOrder);
		source.forEach((q, i) => {
			expect(q.options!.map((o) => o.id)).toEqual(srcOptOrder[i]);
		});
	});

	it('keeps original order when rng always returns 0 (identity)', () => {
		const source = [makeQuestion('q-0'), makeQuestion('q-1'), makeQuestion('q-2')];
		const session = createQuizSession(source, () => 0);
		expect(session.questions.map((q) => q.id)).toEqual(['q-0', 'q-1', 'q-2']);
		expect(session.questions[0].options!.map((o) => o.id)).toEqual(['q-0-o-0', 'q-0-o-1', 'q-0-o-2']);
	});

	it('shuffles deterministically with rng = 0.5 (Penaud variant: j = i + floor(rng*(n-i)))', () => {
		const source = [makeQuestion('q-0'), makeQuestion('q-1'), makeQuestion('q-2')];
		const session = createQuizSession(source, () => 0.5);
		// i=0: j=0+floor(1.5)=1 swap [q1,q0,q2]; i=1: j=1+floor(1.0)=2 swap [q1,q2,q0]
		expect(session.questions.map((q) => q.id)).toEqual(['q-1', 'q-2', 'q-0']);
		// options q-1: i=0: j=1 swap [o1,o0,o2]; i=1: j=2 swap [o1,o2,o0]
		expect(session.questions[0].options!.map((o) => o.id)).toEqual(['q-1-o-1', 'q-1-o-2', 'q-1-o-0']);
	});

	it('rejects duplicate question ids', () => {
		const source = [makeQuestion('q-0'), makeQuestion('q-0')];
		expect(() => createQuizSession(source, () => 0)).toThrow(/duplicate|ganda/i);
	});

	it('initializes every answer as unanswered/not acknowledged', () => {
		const source = [makeQuestion('q-0'), makeQuestion('q-1', 'flashcard')];
		const session = createQuizSession(source, () => 0);
		expect(session.answers['q-0']).toMatchObject({ selectedOptionId: null, acknowledged: false, isCorrect: false });
		expect(session.answers['q-1']).toMatchObject({ selectedOptionId: null, acknowledged: false, isCorrect: false });
	});
});

describe('answerQuestion', () => {
	it('stores the answer by question id, not display index', () => {
		const source = [makeQuestion('q-0'), makeQuestion('q-1'), makeQuestion('q-2')];
		const session = createQuizSession(source, () => 0.5); // display order: q-1, q-2, q-0
		answerQuestion(session, 'q-1', 'q-1-o-0');
		expect(session.answers['q-1'].selectedOptionId).toBe('q-1-o-0');
		expect(session.answers['q-1'].isCorrect).toBe(true);
		expect(session.answers['q-0'].selectedOptionId).toBeNull();
	});

	it('does not change the frozen question/option order', () => {
		const source = [makeQuestion('q-0'), makeQuestion('q-1'), makeQuestion('q-2')];
		const session = createQuizSession(source, () => 0.5);
		const orderBefore = session.questions.map((q) => q.id);
		answerQuestion(session, 'q-1', 'q-1-o-0');
		acknowledgeQuestion(session, 'q-0');
		expect(session.questions.map((q) => q.id)).toEqual(orderBefore);
	});

	it('allows changing the selection before submission (overwrite)', () => {
		const source = [makeQuestion('q-0'), makeQuestion('q-1')];
		const session = createQuizSession(source, () => 0);
		answerQuestion(session, 'q-0', 'q-0-o-0');
		answerQuestion(session, 'q-0', 'q-0-o-1');
		expect(session.answers['q-0'].selectedOptionId).toBe('q-0-o-1');
		// isCorrect ikut terhitung ulang terhadap opsi baru (o-1 bukan opsi benar)
		expect(session.answers['q-0'].isCorrect).toBe(false);
	});

	it('marks wrong answer as not correct', () => {
		const source = [makeQuestion('q-0')];
		const session = createQuizSession(source, () => 0);
		answerQuestion(session, 'q-0', 'q-0-o-2');
		expect(session.answers['q-0'].isCorrect).toBe(false);
	});
});

describe('acknowledgeQuestion', () => {
	it('marks a flashcard as acknowledged', () => {
		const source = [makeQuestion('q-0', 'flashcard')];
		const session = createQuizSession(source, () => 0);
		acknowledgeQuestion(session, 'q-0');
		expect(session.answers['q-0'].acknowledged).toBe(true);
	});
});

describe('calculateQuizResult', () => {
	it('counts only MCQ in the denominator, flashcards excluded', () => {
		const source = [makeQuestion('q-0'), makeQuestion('q-1'), makeQuestion('q-2', 'flashcard')];
		const session = createQuizSession(source, () => 0);
		answerQuestion(session, 'q-0', 'q-0-o-0');
		acknowledgeQuestion(session, 'q-2');
		const result = calculateQuizResult(session);
		expect(result.totalMcq).toBe(2);
		expect(result.correctMcq).toBe(1);
		expect(result.completedFlashcards).toBe(1);
	});

	it('treats unanswered MCQ as wrong', () => {
		const source = [makeQuestion('q-0'), makeQuestion('q-1')];
		const session = createQuizSession(source, () => 0);
		answerQuestion(session, 'q-0', 'q-0-o-0');
		const result = calculateQuizResult(session);
		expect(result.correctMcq).toBe(1);
		expect(result.unansweredMcq).toBe(1);
		expect(result.allHandled).toBe(false);
	});

	it('reports allHandled only when every MCQ answered and every flashcard acknowledged', () => {
		const source = [makeQuestion('q-0'), makeQuestion('q-1'), makeQuestion('q-2', 'flashcard')];
		const session = createQuizSession(source, () => 0);
		answerQuestion(session, 'q-0', 'q-0-o-0');
		answerQuestion(session, 'q-1', 'q-1-o-1');
		acknowledgeQuestion(session, 'q-2');
		expect(calculateQuizResult(session).allHandled).toBe(true);
	});

	it('computes a status string like "2/4" from MCQ totals', () => {
		const source = [makeQuestion('q-0'), makeQuestion('q-1'), makeQuestion('q-2'), makeQuestion('q-3')];
		const session = createQuizSession(source, () => 0);
		answerQuestion(session, 'q-0', 'q-0-o-0');
		answerQuestion(session, 'q-1', 'q-1-o-0');
		const result = calculateQuizResult(session);
		expect(result.statusString).toBe('2/4');
	});
});
