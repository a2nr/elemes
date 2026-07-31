export interface QuizOption {
	id: string;
	text: string;
	is_correct: boolean;
}

export interface QuizQuestion {
	id: string;
	type: 'flashcard' | 'mcq';
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
}
