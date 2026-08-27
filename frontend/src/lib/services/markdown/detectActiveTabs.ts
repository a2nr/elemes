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

	// Intentional deduplication: only push 'quiz' once even if both INITIAL_QUIZ and QUIZ_FLASHCARD markers exist
	if (content.includes('---INITIAL_QUIZ---') || content.includes('---QUIZ_FLASHCARD---')) {
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
		!content.includes('---INITIAL_QUIZ---') &&
		!content.includes('---QUIZ_FLASHCARD---')
	) {
		if (content.includes('---EXERCISE---')) {
			activeTabs.push('c');
		}
	}

	return activeTabs;
}
