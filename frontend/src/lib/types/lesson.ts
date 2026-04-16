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
	expected_circuit_output: string;
	key_text_circuit: string;
	lesson_info: string;
	initial_code: string;
	initial_code_c: string;
	initial_python: string;
	initial_circuit: string;
	initial_quiz: string;
	initial_code_arduino: string;
	velxio_circuit: string;
	expected_serial_output: string;
	expected_wiring: string;
	solution_code: string;
	solution_circuit: string;
	solution_python: string;
	key_text: string;
	lesson_title: string;
	lesson_completed: boolean;
	prev_lesson: Lesson | null;
	next_lesson: Lesson | null;
	ordered_lessons: Lesson[];
	language: string;
	language_display_name: string;
	active_tabs: string[];
	evaluation_config: Record<string, any>;
}
