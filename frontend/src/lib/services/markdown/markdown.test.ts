import { describe, it, expect } from 'vitest';
import { extractSection } from './extractSections';
import { detectActiveTabs } from './detectActiveTabs';
import { processCircuitEmbeds, processFlowchartEmbeds, processEmbedEmbeds } from './processEmbeds';
import { parseSlides } from './parseSlides';
import { parseFlashcards } from './parseFlashcards';
import { renderMarkdownPreview } from './index';

describe('Markdown Renderer & Extractor Tests', () => {
	describe('extractSection', () => {
		it('should extract section between markers and return remaining text', () => {
			const input = 'Before\n---EXPECTED_OUTPUT---\nexpected content\n---END_EXPECTED_OUTPUT---\nAfter';
			const [extracted, remaining] = extractSection(input, '---EXPECTED_OUTPUT---', '---END_EXPECTED_OUTPUT---');
			expect(extracted).toBe('expected content');
			expect(remaining).toBe('Before\n\nAfter');
		});

		it('should return empty string and original text if markers are not present', () => {
			const input = 'Some random content without markers';
			const [extracted, remaining] = extractSection(input, '---START---', '---END---');
			expect(extracted).toBe('');
			expect(remaining).toBe(input);
		});
	});

	describe('detectActiveTabs', () => {
		it('should detect velxio mode exclusively if INITIAL_CODE_ARDUINO is present', () => {
			const input = '---INITIAL_CODE_ARDUINO---\nvoid setup() {}\n---END_INITIAL_CODE_ARDUINO---\n---INITIAL_CODE---\nint main() {}\n---END_INITIAL_CODE---';
			const tabs = detectActiveTabs(input);
			expect(tabs).toContain('velxio');
			expect(tabs).not.toContain('c');
		});

		it('should detect c and python tabs if present', () => {
			const input = '---INITIAL_CODE---\nint main() {}\n---END_INITIAL_CODE---\n---INITIAL_PYTHON---\ndef main(): pass\n---END_INITIAL_PYTHON---';
			const tabs = detectActiveTabs(input);
			expect(tabs).toContain('c');
			expect(tabs).toContain('python');
		});

		it('should fallback to c tab if no markers match but ---EXERCISE--- is present', () => {
			const input = 'Plain lesson here\n---EXERCISE---\nDo this exercise';
			const tabs = detectActiveTabs(input);
			expect(tabs).toEqual(['c']);
		});
	});

	describe('processCircuitEmbeds', () => {
		it('should replace circuit fences with div placeholders', () => {
			const input = '```circuit\ncircuit_data_here\n```';
			const output = processCircuitEmbeds(input);
			expect(output).toContain('class="circuit-embed"');
			expect(output).toContain('data-width="100%"');
			expect(output).toContain('data-height="400px"');
			expect(output).toContain('circuit_data_here');
		});

		it('should handle height parameter', () => {
			const input = '```circuit,500px\ncircuit_data_here\n```';
			const output = processCircuitEmbeds(input);
			expect(output).toContain('data-height="500px"');
		});

		it('should handle width and height parameters', () => {
			const input = '```circuit,80%,600px\ncircuit_data_here\n```';
			const output = processCircuitEmbeds(input);
			expect(output).toContain('data-width="80%"');
			expect(output).toContain('data-height="600px"');
		});
	});

	describe('processFlowchartEmbeds', () => {
		it('should replace flowchart fences with div placeholders', () => {
			const input = '```flowchart\nflowchart_data_here\n```';
			const output = processFlowchartEmbeds(input);
			expect(output).toContain('class="flowchart-embed"');
			expect(output).toContain('data-width="100%"');
			expect(output).toContain('data-height="400px"');
			expect(output).toContain('flowchart_data_here');
		});
	});

	describe('processEmbedEmbeds', () => {
		it('should return error div for empty embed', () => {
			const input = '```embed\n\n```';
			const output = processEmbedEmbeds(input);
			expect(output).toContain('embed-error');
			expect(output).toContain('Konten embed kosong');
		});

		it('should sanitize and allow valid https iframe embed', () => {
			const input = '```embed\n<iframe src="https://example.com"></iframe>\n```';
			const output = processEmbedEmbeds(input);
			expect(output).toContain('<iframe');
			expect(output).toContain('https://example.com');
		});
	});

	describe('parseSlides', () => {
		it('should extract slides, mount point, and render individual slides', () => {
			const input = 'Before slides\n---slide-start---\n# Slide 1\nContent 1\n---\n# Slide 2\nContent 2\n---slide-end---\nAfter slides';
			const { slides, contentWithoutSlides } = parseSlides(input);
			expect(contentWithoutSlides).toBe('Before slides\n<div id="slide-mount-point"></div>\nAfter slides');
			expect(slides).toHaveLength(2);
			expect(slides[0]).toContain('<h1>Slide 1</h1>');
			expect(slides[1]).toContain('<h1>Slide 2</h1>');
		});
	});

	describe('parseFlashcards', () => {
		it('should parse simple flashcards without options', () => {
			const input = '### What is C?\nIt is a programming language.\n> Explanation text here';
			const cards = parseFlashcards(input);
			expect(cards).toHaveLength(1);
			expect(cards[0].type).toBe('flashcard');
			expect(cards[0].front).toContain('What is C?');
			expect(cards[0].back).toContain('It is a programming language.');
			expect(cards[0].explanation).toContain('Explanation text here');
		});

		it('should parse MCQ cards with options', () => {
			const input = '### Tipe Data C\nSelect one:\n- [] float\n- [x] int\n- [] char\n> Explanation for int';
			const cards = parseFlashcards(input);
			expect(cards).toHaveLength(1);
			expect(cards[0].type).toBe('mcq');
			expect(cards[0].question).toContain('Tipe Data C');
			expect(cards[0].options).toHaveLength(3);
			expect(cards[0].options![1].is_correct).toBe(true);
			expect(cards[0].explanation).toContain('Explanation for int');
		});

		it('should throw value validation error if MCQ has no correct option', () => {
			const input = '### Invalid Question\n- [] opt 1\n- [] opt 2';
			expect(() => parseFlashcards(input)).toThrow('wajib punya tepat satu opsi benar');
		});

		it('should throw value validation error if MCQ has multiple correct options', () => {
			const input = '### Invalid Question\n- [x] opt 1\n- [x] opt 2';
			expect(() => parseFlashcards(input)).toThrow('wajib punya tepat satu opsi benar');
		});
	});

	describe('renderMarkdownPreview orchestrator', () => {
		it('should successfully compile full markdown input into JSON structure', () => {
			const input = `# My Lesson
---LESSON_INFO---
**Prerequisite:** None
---END_LESSON_INFO---
This is the theory.
---EXERCISE---
This is the exercise.`;
			const res = renderMarkdownPreview(input);
			expect(res.success).toBe(true);
			expect(res.lesson_content).toContain('<h1>My Lesson</h1>');
			expect(res.lesson_content).toContain('<p>This is the theory.</p>');
			expect(res.exercise_content).toContain('<p>This is the exercise.</p>');
		});

		it('should catch validation errors from flashcards and report success: false', () => {
			const input = `# Lesson with invalid quiz
---QUIZ_FLASHCARD---
### Question without correct choice
- [] A
- [] B
---END_QUIZ_FLASHCARD---`;
			const res = renderMarkdownPreview(input);
			expect(res.success).toBe(false);
			expect(res.message).toContain('wajib punya tepat satu opsi benar');
		});
	});
});
