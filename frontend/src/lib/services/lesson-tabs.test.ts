import { describe, it, expect } from 'vitest';
import type { LessonContent } from '$types/lesson';
import { pickDefaultTab, getAvailableTabs, ensureActiveTab } from './lesson-tabs';

function makeLesson(overrides: Partial<LessonContent> = {}): LessonContent {
	return {
		lesson_title: 'Test',
		filename: 'test.md',
		slug: 'test.md',
		lesson_content: '',
		active_tabs: [],
		lesson_completed: false,
		...overrides
	} as LessonContent;
}

describe('pickDefaultTab', () => {
	it('picks quiz for a quiz-only lesson (regression: empty workspace)', () => {
		const lesson = makeLesson({ active_tabs: ['quiz'] });
		expect(pickDefaultTab(lesson)).toBe('quiz');
	});

	it('keeps editor default for quiz + c/python lessons (unchanged behavior)', () => {
		const lesson = makeLesson({ active_tabs: ['quiz', 'c'] });
		expect(pickDefaultTab(lesson)).toBe('editor');
	});

	it('keeps editor default for lessons with c/python only', () => {
		expect(pickDefaultTab(makeLesson({ active_tabs: ['c'] }))).toBe('editor');
		expect(pickDefaultTab(makeLesson({ active_tabs: ['python'] }))).toBe('editor');
	});

	it('keeps editor default for empty tab lists (unchanged behavior)', () => {
		expect(pickDefaultTab(makeLesson({ active_tabs: [] }))).toBe('editor');
	});

	it('prefers info over quiz when lesson_info exists', () => {
		const lesson = makeLesson({ active_tabs: ['quiz'], lesson_info: '<p>info</p>' });
		expect(pickDefaultTab(lesson)).toBe('info');
	});

	it('prefers exercise over quiz when exercise_content exists', () => {
		const lesson = makeLesson({ active_tabs: ['quiz'], exercise_content: '<p>exercise</p>' });
		expect(pickDefaultTab(lesson)).toBe('exercise');
	});

	it('keeps velxio/flowchart/circuit priority', () => {
		expect(pickDefaultTab(makeLesson({ active_tabs: ['velxio', 'quiz'] }))).toBe('velxio');
		expect(pickDefaultTab(makeLesson({ active_tabs: ['flowchart', 'quiz'] }))).toBe('flowchart');
		expect(pickDefaultTab(makeLesson({ active_tabs: ['circuit', 'quiz'] }))).toBe('circuit');
	});

	it('falls back to quiz when tabs exist but no panel-rendering tab is present', () => {
		const lesson = makeLesson({ active_tabs: ['quiz', 'deploy'] });
		expect(pickDefaultTab(lesson)).toBe('quiz');
	});
});

describe('getAvailableTabs', () => {
	it('includes info when lesson_info exists', () => {
		const lesson = makeLesson({ active_tabs: ['quiz'], lesson_info: '<p>info</p>' });
		expect(getAvailableTabs(lesson)).toContain('info');
	});

	it('includes exercise when exercise_content exists', () => {
		const lesson = makeLesson({ active_tabs: ['quiz'], exercise_content: '<p>ex</p>' });
		expect(getAvailableTabs(lesson)).toContain('exercise');
	});

	it('includes editor only when c/python present or tabs empty', () => {
		expect(getAvailableTabs(makeLesson({ active_tabs: ['c'] }))).toContain('editor');
		expect(getAvailableTabs(makeLesson({ active_tabs: ['python'] }))).toContain('editor');
		expect(getAvailableTabs(makeLesson({ active_tabs: [] }))).toContain('editor');
		// No c/python and tabs non-empty → editor NOT rendered
		expect(getAvailableTabs(makeLesson({ active_tabs: ['circuit', 'quiz'] }))).not.toContain('editor');
		expect(getAvailableTabs(makeLesson({ active_tabs: ['quiz'] }))).not.toContain('editor');
	});

	it('includes circuit only when active_tabs has circuit', () => {
		expect(getAvailableTabs(makeLesson({ active_tabs: ['circuit'] }))).toContain('circuit');
		expect(getAvailableTabs(makeLesson({ active_tabs: ['quiz'] }))).not.toContain('circuit');
	});

	it('always includes output (panel is always rendered)', () => {
		expect(getAvailableTabs(makeLesson({ active_tabs: ['quiz'] }))).toContain('output');
	});
});

describe('ensureActiveTab', () => {
	it('returns desired tab when it is available', () => {
		const lesson = makeLesson({ active_tabs: ['c', 'quiz'] });
		// 'editor' is valid because 'c' is present
		expect(ensureActiveTab(lesson, 'editor')).toBe('editor');
		expect(ensureActiveTab(lesson, 'quiz')).toBe('quiz');
		expect(ensureActiveTab(lesson, 'output')).toBe('output');
	});

	it('falls back to pickDefaultTab when desired tab is not rendered', () => {
		const lesson = makeLesson({ active_tabs: ['quiz'] });
		// 'editor' is NOT rendered for quiz-only lesson → fallback to 'quiz'
		expect(ensureActiveTab(lesson, 'editor')).toBe('quiz');
	});

	it('falls back to pickDefaultTab when desired tab is circuit but not in active_tabs', () => {
		const lesson = makeLesson({ active_tabs: ['c', 'quiz'] });
		// 'circuit' not in active_tabs → fallback to 'editor' (default for c)
		expect(ensureActiveTab(lesson, 'circuit')).toBe('editor');
	});

	it('never returns an unavailable tab (regression: phantom tab leads to empty workspace)', () => {
		// Quiz-only lesson: 'editor' and 'circuit' are unavailable
		const quizOnly = makeLesson({ active_tabs: ['quiz'] });
		const available = getAvailableTabs(quizOnly);
		// Whatever desired tab we try, result must be in available
		for (const desired of ['editor', 'circuit', 'velxio', 'flowchart', 'deploy'] as const) {
			const result = ensureActiveTab(quizOnly, desired);
			expect(available).toContain(result);
		}
	});

	it('handles empty active_tabs gracefully', () => {
		const lesson = makeLesson({ active_tabs: [] });
		// editor is available for empty tabs
		expect(ensureActiveTab(lesson, 'editor')).toBe('editor');
		// circuit not available, falls back to editor
		expect(ensureActiveTab(lesson, 'circuit')).toBe('editor');
	});
});
