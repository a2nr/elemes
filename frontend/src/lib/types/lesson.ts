export interface Lesson {
	filename: string;
	title: string;
	description: string;
	completed: boolean;
}

export interface LessonContent {
	lesson_content: string;
	exercise_content: string;
	expected_output: string;
	lesson_info: string;
	initial_code: string;
	solution_code: string;
	key_text: string;
	lesson_title: string;
	lesson_completed: boolean;
	prev_lesson: Lesson | null;
	next_lesson: Lesson | null;
	ordered_lessons: Lesson[];
	language: string;
	language_display_name: string;
}
