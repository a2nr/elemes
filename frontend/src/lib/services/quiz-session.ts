import type { QuizQuestion, QuizAnswer, QuizType } from '../types/quiz';

export interface QuizSession {
	/** Questions in shuffled (frozen) display order. Option arrays also shuffled once. */
	questions: QuizQuestion[];
	/** Answers keyed by stable question id — never by display index. */
	answers: Record<string, QuizAnswer>;
}

/** Poin maksimum sebuah soal — bobot tertinggi opsi (weighted), 1 utk MCQ biner, 0 utk flashcard. */
export function questionMaxPoints(q: QuizQuestion | undefined): number {
	if (!q || q.type !== 'mcq' || !q.options?.length) return 0;
	return q.options.reduce((max, o) => Math.max(max, o.weight ?? 0), 0);
}

/** Persentase kategori per jenis quiz (sumbu kategori evaluasi/diagnostik). */
export interface QuizTypeScore {
	/** Poin yang diperoleh untuk jenis ini. */
	earned: number;
	/** Poin maksimum jenis ini (Σ bobot tertinggi tiap soal / jumlah soal MCQ). */
	max: number;
	/** Persentase 0–100 (belum dibulatkan — pembulatan hanya di skor akhir). */
	percent: number | null;
}

export interface QuizResult {
	totalMcq: number;
	correctMcq: number;
	unansweredMcq: number;
	completedFlashcards: number;
	allHandled: boolean;
	/**
	 * Skor resmi.
	 * - Ada soal weighted → "P/100" (P integer 0–100, rata-rata persentase jenis).
	 * - Hanya MCQ (atau legacy) → "X/Y" — tidak berubah (kompatibel).
	 * - Tanpa soal dinilai → "completed".
	 */
	statusString: string;
	/**
	 * Skor akhir integer 0–100 hasil rata-rata persentase per jenis quiz yang
	 * ADA di kuis (Math.round, 0.5 dibulatkan ke atas). Angka yang tampil =
	 * angka yang dipakai memutuskan lulus. null bila tidak ada soal dinilai.
	 */
	percent: number | null;
	/** True bila kuis memuat minimal satu soal weighted. */
	hasWeighted: boolean;
	/** Breakdown poin per jenis quiz (sumbu jenis, berdampingan dgn kategori). */
	typeScores: {
		mcq: QuizTypeScore;
		weighted: QuizTypeScore;
	};
	/** MCQ dengan category 'evaluasi' */
	evalCorrect: number;
	evalTotal: number;
	/** MCQ dengan category 'diagnostik' */
	diagCorrect: number;
	diagTotal: number;
	/** Soal diagnostik yang salah/atur tidak dijawab */
	diagUnmastered: QuizQuestion[];
}

/** Ambang lulus kuis (persen dari skor akhir). */
export const QUIZ_PASS_THRESHOLD = 75;

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

/** quiz_type soal — fallback aman untuk konten lama tanpa field quiz_type. */
function quizTypeOf(q: QuizQuestion): QuizType {
	if (q.type !== 'mcq') return 'flashcard';
	return q.quiz_type ?? 'mcq';
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
		answers[q.id] = {
			questionId: q.id,
			selectedOptionId: null,
			acknowledged: false,
			isCorrect: false,
			earnedPoints: 0,
			questionMaxPoints: questionMaxPoints(q)
		};
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
	// Poin parsial (weighted): bobot opsi terpilih. MCQ biner: 1/0 via weight.
	answer.earnedPoints = opt?.weight ?? 0;
	answer.questionMaxPoints = questionMaxPoints(q);
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

	// Poin per JENIS quiz (sumbu jenis) — flashcard netral (tidak dinilai).
	const mcqScore = { earned: 0, max: 0 };
	const weightedScore = { earned: 0, max: 0 };

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

			// Poin per jenis — ::diagnostic tetap masuk rasio MCQ (kompatibilitas).
			if (quizTypeOf(q) === 'weighted') {
				weightedScore.earned += a.earnedPoints ?? 0;
				weightedScore.max += a.questionMaxPoints || questionMaxPoints(q);
			} else {
				mcqScore.earned += a.isCorrect ? 1 : 0;
				mcqScore.max += 1;
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

	const pMcq = mcqScore.max > 0 ? (mcqScore.earned / mcqScore.max) * 100 : null;
	const pWeighted =
		weightedScore.max > 0 ? (weightedScore.earned / weightedScore.max) * 100 : null;

	const present = [pMcq, pWeighted].filter((p): p is number => p !== null);
	const percent = present.length > 0 ? Math.round(present.reduce((s, p) => s + p, 0) / present.length) : null;
	const hasWeighted = weightedScore.max > 0;

	// Skor resmi:
	// - weighted ikut → "P/100" (persen, rata-rata per jenis).
	// - hanya MCQ → "X/Y" (perilaku lama, kompatibel mundur).
	// - tanpa soal dinilai (flashcard saja) → 'completed'.
	let statusString: string;
	if (hasWeighted) {
		statusString = `${percent}/100`;
	} else if (mcqScore.max > 0) {
		statusString = `${mcqScore.earned}/${mcqScore.max}`;
	} else {
		statusString = 'completed';
	}

	return {
		totalMcq,
		correctMcq,
		unansweredMcq,
		completedFlashcards,
		allHandled,
		statusString,
		percent,
		hasWeighted,
		typeScores: {
			mcq: { earned: mcqScore.earned, max: mcqScore.max, percent: pMcq },
			weighted: { earned: weightedScore.earned, max: weightedScore.max, percent: pWeighted }
		},
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
	/** Jenis quiz menurut key asalnya (payload baru). */
	quiz_type?: QuizType;
	/** Poin jawaban weighted (payload baru) — dihitung ulang dari konten. */
	earned_points?: number;
	/** Poin maksimum soal (payload baru) — dihitung ulang dari konten. */
	question_max_points?: number;
}

/**
 * Rekonstruksi sesi kuis dari jawaban tersimpan (resume attempt oleh guru).
 *
 * Berbeda dari createQuizSession: jawaban siswa dari attempt sebelumnya
 * di-seed by question_id. `is_correct` dan poin weighted dihitung ulang dari
 * source (bukan percaya nilai tersimpan) sebagai guard bila konten soal
 * berubah antara attempt dan resume — option_id yang tidak dikenal dianggap
 * belum dijawab.
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
				// Poin dihitung ulang dari konten soal (bukan nilai tersimpan).
				answer.earnedPoints = opt.weight ?? 0;
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
