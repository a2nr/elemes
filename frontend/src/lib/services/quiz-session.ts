import type { QuizQuestion, QuizAnswer } from '../types/quiz';

export interface QuizSession {
	/** Questions in shuffled (frozen) display order. Option arrays also shuffled once. */
	questions: QuizQuestion[];
	/** Answers keyed by stable question id — never by display index. */
	answers: Record<string, QuizAnswer>;
}

export interface QuizResult {
	totalMcq: number;
	correctMcq: number;
	unansweredMcq: number;
	completedFlashcards: number;
	allHandled: boolean;
	/** Skor resmi = evaluasi saja. "X/Y" bila ada MCQ evaluasi, "completed" bila tidak ada MCQ evaluasi (hanya diagnostik/flashcard). */
	statusString: string;
	/** MCQ dengan category 'evaluasi' */
	evalCorrect: number;
	evalTotal: number;
	/** MCQ dengan category 'diagnostik' */
	diagCorrect: number;
	diagTotal: number;
	/** Soal diagnostik yang salah/atur tidak dijawab */
	diagUnmastered: QuizQuestion[];
}

/**
 * Fisher-Yates (Penaud variant): j = i + floor(rng*(n-i)).
 * rng === 0 keeps the array in its original order — handy for deterministic tests.
 * Never mutates the input array.
 */
function shuffle<T>(arr: T[], rng: () => number): T[] {
	const a = [...arr];
	for (let i = 0; i < a.length - 1; i++) {
		const j = i + Math.floor(rng() * (a.length - i));
		[a[i], a[j]] = [a[j], a[i]];
	}
	return a;
}

export function createQuizSession(source: QuizQuestion[], rng: () => number = Math.random): QuizSession {
	const seen = new Set<string>();
	for (const q of source) {
		if (seen.has(q.id)) throw new Error(`Duplicate question id: ${q.id}`);
		seen.add(q.id);
	}

	const questions = shuffle(source, rng).map((q) => {
		if (q.type === 'mcq' && q.options?.length) {
			return { ...q, options: shuffle(q.options, rng) };
		}
		return q;
	});

	const answers: Record<string, QuizAnswer> = {};
	for (const q of questions) {
		answers[q.id] = { questionId: q.id, selectedOptionId: null, acknowledged: false, isCorrect: false };
	}

	return { questions, answers };
}

export function answerQuestion(session: QuizSession, questionId: string, optionId: string): void {
	const answer = session.answers[questionId];
	if (!answer) throw new Error(`Unknown question id: ${questionId}`);
	const q = session.questions.find((qq) => qq.id === questionId);
	const opt = q?.options?.find((o) => o.id === optionId);
	answer.selectedOptionId = optionId;
	answer.isCorrect = opt?.is_correct ?? false;
}

export function acknowledgeQuestion(session: QuizSession, questionId: string): void {
	const answer = session.answers[questionId];
	if (!answer) throw new Error(`Unknown question id: ${questionId}`);
	answer.acknowledged = true;
}

/**
 * Tandai flashcard sebagai handled. `understood` mencatat apakah siswa
 * merasa mengerti (true) atau tidak (false). Kedua state = acknowledged.
 */
export function acknowledgeFlashcard(session: QuizSession, questionId: string, understood: boolean): void {
	const answer = session.answers[questionId];
	if (!answer) throw new Error(`Unknown question id: ${questionId}`);
	answer.acknowledged = true;
	answer.understood = understood;
}

export function calculateQuizResult(session: QuizSession): QuizResult {
	let totalMcq = 0;
	let correctMcq = 0;
	let unansweredMcq = 0;
	let completedFlashcards = 0;

	let evalCorrect = 0;
	let evalTotal = 0;
	let diagCorrect = 0;
	let diagTotal = 0;
	const diagUnmastered: QuizQuestion[] = [];

	for (const q of session.questions) {
		const a = session.answers[q.id];
		const isEval = q.category !== 'diagnostik'; // default 'evaluasi'
		if (q.type === 'mcq') {
			totalMcq += 1;
			if (a.isCorrect) correctMcq += 1;
			if (a.selectedOptionId === null) unansweredMcq += 1;

			if (isEval) {
				evalTotal += 1;
				if (a.isCorrect) evalCorrect += 1;
			} else {
				diagTotal += 1;
				if (a.isCorrect) diagCorrect += 1;
				else diagUnmastered.push(q);
			}
		} else if (a.acknowledged) {
			completedFlashcards += 1;
		}
	}

	const allHandled = session.questions.every((q) =>
		q.type === 'mcq'
			? session.answers[q.id].selectedOptionId !== null
			: session.answers[q.id].acknowledged
	);
	// Skor resmi = evaluasi saja; bila tidak ada MCQ evaluasi → 'completed'.
	const statusString = evalTotal > 0 ? `${evalCorrect}/${evalTotal}` : 'completed';

	return {
		totalMcq,
		correctMcq,
		unansweredMcq,
		completedFlashcards,
		allHandled,
		statusString,
		evalCorrect,
		evalTotal,
		diagCorrect,
		diagTotal,
		diagUnmastered,
	};
}
