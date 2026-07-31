import type { LessonContent } from '$types/lesson';

export type LessonTab =
	| 'info'
	| 'exercise'
	| 'editor'
	| 'circuit'
	| 'output'
	| 'velxio'
	| 'flowchart'
	| 'deploy'
	| 'quiz';

/**
 * Pick the default tab shown when a lesson loads.
 *
 * Priority mirrors the panels ACTUALLY rendered by +page.svelte:
 * info > exercise > velxio > flowchart > circuit > editor (only when the
 * editor panel exists) > quiz > editor (last resort).
 *
 * Bugfix: quiz-only lessons previously fell through to 'editor', which is
 * never rendered for them (CodeTab requires 'c'/'python' in active_tabs),
 * leaving the workspace with no visible panel ("tab quiz kosong" on mobile).
 */
export function pickDefaultTab(lesson: LessonContent): LessonTab {
	const hasC = lesson.active_tabs?.includes('c');
	const hasPython = lesson.active_tabs?.includes('python');
	// The editor panel only renders for empty tab lists or c/python lessons.
	const hasEditor = !lesson.active_tabs?.length || !!hasC || !!hasPython;

	if (lesson.lesson_info) return 'info';
	if (lesson.exercise_content) return 'exercise';
	if (lesson.active_tabs?.includes('velxio')) return 'velxio';
	if (lesson.active_tabs?.includes('flowchart')) return 'flowchart';
	if (lesson.active_tabs?.includes('circuit') && !hasC && !hasPython) return 'circuit';
	if (hasEditor) return 'editor';
	if (lesson.active_tabs?.includes('quiz')) return 'quiz';
	return 'editor';
}

/**
 * The set of tabs that are RENDERED by +page.svelte for the given lesson.
 * Used by `ensureActiveTab` to guard against stale/phantom tab selections.
 *
 * Mirrors the exact {#if} conditions in +page.svelte so a tab is "valid"
 * iff its panel would actually exist in the DOM.
 */
export function getAvailableTabs(lesson: LessonContent): LessonTab[] {
	const tabs: LessonTab[] = [];
	if (lesson.lesson_info) tabs.push('info');
	if (lesson.exercise_content) tabs.push('exercise');
	// Circuit panel renders only if 'circuit' in active_tabs
	if (lesson.active_tabs?.includes('circuit')) tabs.push('circuit');
	// Velxio panel renders only if 'velxio' in active_tabs (isVelxio derived)
	if (lesson.active_tabs?.includes('velxio')) tabs.push('velxio');
	// Flowchart panel renders only if 'flowchart' in active_tabs (isFlowchart derived)
	if (lesson.active_tabs?.includes('flowchart')) tabs.push('flowchart');
	// Deploy panel renders only if isDeployable (= velxio in active_tabs)
	if (lesson.active_tabs?.includes('velxio')) tabs.push('deploy');
	// Editor panel renders if active_tabs empty OR has c/python
	const hasC = lesson.active_tabs?.includes('c');
	const hasPython = lesson.active_tabs?.includes('python');
	const hasEditor = !lesson.active_tabs?.length || !!hasC || !!hasPython;
	if (hasEditor) tabs.push('editor');
	// Quiz panel renders only if 'quiz' in active_tabs
	if (lesson.active_tabs?.includes('quiz')) tabs.push('quiz');
	// Output panel ALWAYS renders (it's outside any {#if} for active_tabs)
	tabs.push('output');
	return tabs;
}

/**
 * Safety-net guard: given a desired tab, return a tab that is actually
 * rendered for this lesson. If the requested tab is not available, falls
 * back to `pickDefaultTab`. This prevents "phantom tab" bugs where an
 * activeTab value points at a tab whose panel is never rendered, causing
 * the workspace to appear empty.
 *
 * Output is always available so it is never an invalid fallback.
 */
export function ensureActiveTab(lesson: LessonContent, desired: LessonTab): LessonTab {
	const available = getAvailableTabs(lesson);
	if (available.includes(desired)) return desired;
	return pickDefaultTab(lesson);
}
