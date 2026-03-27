import { writable } from 'svelte/store';

export interface LessonNavContext {
	title: string;
	completed: boolean;
	prevLesson: { filename: string; title: string } | null;
	nextLesson: { filename: string; title: string } | null;
}

export const lessonContext = writable<LessonNavContext | null>(null);
