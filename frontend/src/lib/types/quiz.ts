export interface QuizOption {
	id: string;
	text: string;
	is_correct: boolean;
	/** Bobot nilai opsi (>= 0). Legacy/MCQ: benar 1 / salah 0. Weighted: nilai [N]. */
	weight: number;
}

/** Jenis quiz menurut key asalnya — menentukan model penilaian. */
export type QuizType = 'mcq' | 'weighted' | 'flashcard';

export interface QuizQuestion {
	id: string;
	type: 'flashcard' | 'mcq';
	quiz_type: QuizType;
	category?: 'evaluasi' | 'diagnostik';
	question?: string;
	front?: string;
	back?: string;
	options?: QuizOption[];
	explanation?: string;
	image?: string;
}

export interface QuizAnswer {
	questionId: string;
	selectedOptionId: string | null;
	acknowledged: boolean;
	isCorrect: boolean;
	/** Flashcard — apakah siswa merasa mengerti materi (true/false). Opsional. */
	understood?: boolean;
	/** Poin yang diperoleh untuk soal berbobot (weighted) — 0 untuk biner. */
	earnedPoints: number;
	/** Poin maksimum soal ini (bobot tertinggi opsi weighted; 1 untuk MCQ). */
	questionMaxPoints: number;
}
