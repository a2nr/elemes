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
	/** Skor resmi = seluruh MCQ (evaluasi + diagnostik) tergabung; flashcard tidak dihitung. "X/Y" bila ada MCQ, "completed" bila tidak ada MCQ. */
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
	// Skor resmi = seluruh MCQ (evaluasi + diagnostik) tergabung; bila tidak ada MCQ → 'completed'.
	const statusString = totalMcq > 0 ? `${correctMcq}/${totalMcq}` : 'completed';

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

/** Ringkasan jawaban tersimpan dari attempt sebelumnya (payload backend). */
export interface StoredQuizAnswer {
	question_id: string;
	selected_option_id: string | null;
	is_correct?: boolean;
	category?: 'evaluasi' | 'diagnostik';
	type?: 'mcq' | 'flashcard';
}

/**
 * Rekonstruksi sesi kuis dari jawaban tersimpan (resume attempt oleh guru).
 *
 * Berbeda dari createQuizSession: jawaban siswa dari attempt sebelumnya
 * di-seed by question_id. `is_correct` dihitung ulang dari source (bukan
 * percaya nilai tersimpan) sebagai guard bila konten soal berubah antara
 * attempt dan resume — option_id yang tidak dikenal dianggap belum dijawab.
 *
 * Catatan: status `acknowledged` flashcard tidak tersimpan di payload
 * attempt — siswa perlu acknowledge ulang saat resume.
 */
export function restoreQuizSession(
	source: QuizQuestion[],
	savedAnswers: StoredQuizAnswer[],
	rng: () => number = Math.random
): QuizSession {
	const session = createQuizSession(source, rng);
	const byId = new Map(savedAnswers.map((a) => [a.question_id, a]));
	for (const q of session.questions) {
		const saved = byId.get(q.id);
		if (!saved) continue;
		const answer = session.answers[q.id];
		if (q.type === 'mcq' && saved.selected_option_id) {
			const opt = q.options?.find((o) => o.id === saved.selected_option_id);
			if (opt) {
				answer.selectedOptionId = opt.id;
				answer.isCorrect = opt.is_correct;
			}
		}
	}
	return session;
}

/**
 * Index soal pertama yang belum dijawab — posisi mulai saat resume.
 * Return 0 bila semua sudah terjawab (mis. attempt di-resume setelah
 * semua soal sempat dijawab).
 */
export function firstUnansweredIndex(session: QuizSession): number {
	const idx = session.questions.findIndex((q) => {
		const a = session.answers[q.id];
		return a.selectedOptionId === null && !a.acknowledged;
	});
	return idx === -1 ? 0 : idx;
}
