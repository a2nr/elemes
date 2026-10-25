/**
 * Markers that activate the 'quiz' tab — new per-type quiz keys plus the
 * legacy ones (kept for backward compatibility with existing content).
 */
export const QUIZ_TAB_MARKERS = [
	'---INITIAL_QUIZ---',
	'---QUIZ_FLASHCARD---',
	'---QUIZ_MCQ---',
	'---QUIZ_WEIGHTED---',
	'---FLASHCARD---'
];

/**
 * Detect active tabs for the lesson editor/workspace.
 */
export function detectActiveTabs(content: string): string[] {
	const activeTabs: string[] = [];

	if (content.includes('---INITIAL_CODE_ARDUINO---')) {
		activeTabs.push('velxio');
	} else {
		if (content.includes('---INITIAL_CODE---')) {
			activeTabs.push('c');
		}
		if (content.includes('---INITIAL_PYTHON---')) {
			activeTabs.push('python');
		}
	}

	if (content.includes('---INITIAL_CIRCUIT---')) {
		activeTabs.push('circuit');
	}

	if (content.includes('---INITIAL_FLOWCHART---')) {
		activeTabs.push('flowchart');
	}

	// Intentional deduplication: only push 'quiz' once even if several quiz
	// markers (INITIAL_QUIZ, QUIZ_MCQ, QUIZ_WEIGHTED, FLASHCARD, ...) exist.
	if (QUIZ_TAB_MARKERS.some((marker) => content.includes(marker))) {
		activeTabs.push('quiz');
	}

	if (content.includes('---VELXIO_CIRCUIT---') && !activeTabs.includes('velxio')) {
		activeTabs.push('velxio');
	}

	// Default to 'c' if nothing specified (for backwards compatibility)
	if (
		activeTabs.length === 0 &&
		!content.includes('---INITIAL_CODE---') &&
		!content.includes('---INITIAL_PYTHON---') &&
		!content.includes('---INITIAL_CIRCUIT---') &&
		!content.includes('---INITIAL_FLOWCHART---') &&
		!QUIZ_TAB_MARKERS.some((marker) => content.includes(marker))
	) {
		if (content.includes('---EXERCISE---')) {
			activeTabs.push('c');
		}
	}

	return activeTabs;
}
