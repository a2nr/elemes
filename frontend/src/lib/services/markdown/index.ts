import { marked } from 'marked';
import { extractSection } from './extractSections';
import { detectActiveTabs } from './detectActiveTabs';
import { parseFlashcards, type QuizCard } from './parseFlashcards';
import { parseSlides } from './parseSlides';
import { processCircuitEmbeds, processFlowchartEmbeds, processEmbedEmbeds } from './processEmbeds';

export interface RenderedPreview {
	success: boolean;
	lesson_content: string;
	exercise_content: string;
	quiz_data: QuizCard[];
	slides: string[];
	active_tabs: string[];
	message?: string;
}

/**
 * Parses markdown on the client side, matching the backend's parsing output exactly.
 */
export function renderMarkdownPreview(rawMarkdown: string): RenderedPreview {
	try {
		const active_tabs = detectActiveTabs(rawMarkdown);

		let content = rawMarkdown;

		// Extract sections in order (matching Python code)
		let expected_output = '';
		[expected_output, content] = extractSection(content, '---EXPECTED_OUTPUT---', '---END_EXPECTED_OUTPUT---');

		let expected_output_python = '';
		[expected_output_python, content] = extractSection(content, '---EXPECTED_OUTPUT_PYTHON---', '---END_EXPECTED_OUTPUT_PYTHON---');

		let expected_circuit_output = '';
		[expected_circuit_output, content] = extractSection(content, '---EXPECTED_CIRCUIT_OUTPUT---', '---END_EXPECTED_CIRCUIT_OUTPUT---');

		let key_text = '';
		[key_text, content] = extractSection(content, '---KEY_TEXT---', '---END_KEY_TEXT---');

		let key_text_circuit = '';
		[key_text_circuit, content] = extractSection(content, '---KEY_TEXT_CIRCUIT---', '---END_KEY_TEXT_CIRCUIT---');

		let lesson_info = '';
		if (content.includes('---LESSON_INFO---') && content.includes('---END_LESSON_INFO---')) {
			[lesson_info, content] = extractSection(content, '---LESSON_INFO---', '---END_LESSON_INFO---');
		} else if (content.includes('---LESSON_INFO---')) {
			const parts = content.split('---LESSON_INFO---');
			if (parts.length === 2) {
				lesson_info = parts[0].trim();
				content = parts[1].trim();
			}
		}

		let solution_code = '';
		[solution_code, content] = extractSection(content, '---SOLUTION_CODE---', '---END_SOLUTION_CODE---');

		let solution_circuit = '';
		[solution_circuit, content] = extractSection(content, '---SOLUTION_CIRCUIT---', '---END_SOLUTION_CIRCUIT---');

		let solution_python = '';
		[solution_python, content] = extractSection(content, '---SOLUTION_PYTHON---', '---END_SOLUTION_PYTHON---');

		let initial_code_c = '';
		[initial_code_c, content] = extractSection(content, '---INITIAL_CODE---', '---END_INITIAL_CODE---');

		let initial_python = '';
		[initial_python, content] = extractSection(content, '---INITIAL_PYTHON---', '---END_INITIAL_PYTHON---');

		let initial_circuit = '';
		[initial_circuit, content] = extractSection(content, '---INITIAL_CIRCUIT---', '---END_INITIAL_CIRCUIT---');

		let initial_flowchart_str = '';
		[initial_flowchart_str, content] = extractSection(content, '---INITIAL_FLOWCHART---', '---END_INITIAL_FLOWCHART---');

		let initial_quiz = '';
		[initial_quiz, content] = extractSection(content, '---INITIAL_QUIZ---', '---END_INITIAL_QUIZ---');

		let quiz_flashcard_raw = '';
		[quiz_flashcard_raw, content] = extractSection(content, '---QUIZ_FLASHCARD---', '---END_QUIZ_FLASHCARD---');

		const quiz_data = parseFlashcards(quiz_flashcard_raw);

		let initial_code_arduino = '';
		[initial_code_arduino, content] = extractSection(content, '---INITIAL_CODE_ARDUINO---', '---END_INITIAL_CODE_ARDUINO---');

		let velxio_circuit = '';
		[velxio_circuit, content] = extractSection(content, '---VELXIO_CIRCUIT---', '---END_VELXIO_CIRCUIT---');

		let expected_serial_output = '';
		[expected_serial_output, content] = extractSection(content, '---EXPECTED_SERIAL_OUTPUT---', '---END_EXPECTED_SERIAL_OUTPUT---');

		let expected_wiring = '';
		[expected_wiring, content] = extractSection(content, '---EXPECTED_WIRING---', '---END_EXPECTED_WIRING---');

		let expected_flowchart = '';
		[expected_flowchart, content] = extractSection(content, '---EXPECTED_FLOWCHART---', '---END_EXPECTED_FLOWCHART---');

		let evaluation_config = '';
		[evaluation_config, content] = extractSection(content, '---EVALUATION_CONFIG---', '---END_EVALUATION_CONFIG---');

		// Parse slides
		const { slides, contentWithoutSlides } = parseSlides(content);
		content = contentWithoutSlides;

		// Split lesson vs exercise
		const exerciseParts = content.split('---EXERCISE---');
		let lessonContent = exerciseParts[0] || '';
		let exerciseContent = exerciseParts.length > 1 ? exerciseParts[1] : '';

		// Process embeds
		lessonContent = processCircuitEmbeds(lessonContent);
		lessonContent = processFlowchartEmbeds(lessonContent);
		lessonContent = processEmbedEmbeds(lessonContent);

		if (exerciseContent) {
			exerciseContent = processCircuitEmbeds(exerciseContent);
			exerciseContent = processFlowchartEmbeds(exerciseContent);
			exerciseContent = processEmbedEmbeds(exerciseContent);
		}

		// Render markdown to HTML with embed block protection
		const renderMarkdown = (md: string) => {
			const placeholders: Record<string, string> = {};
			let counter = 0;

			let text = md.replace(/<div class="(?:circuit|flowchart)-embed"[\s\S]*?<\/div>/g, (match) => {
				const id = `%%EMBED_BLOCK_${counter++}%%`;
				placeholders[id] = match;
				return `\n\n${id}\n\n`;
			});

			let html = marked.parse(text, { breaks: true, gfm: true }) as string;

			for (const [id, originalHtml] of Object.entries(placeholders)) {
				html = html.replace(`<p>${id}</p>`, originalHtml).replace(id, originalHtml);
			}

			return html;
		};

		const lesson_html = renderMarkdown(lessonContent);
		const exercise_html = exerciseContent ? renderMarkdown(exerciseContent) : '';

		return {
			success: true,
			lesson_content: lesson_html,
			exercise_content: exercise_html,
			quiz_data,
			slides,
			active_tabs
		};
	} catch (e: any) {
		return {
			success: false,
			lesson_content: '',
			exercise_content: '',
			quiz_data: [],
			slides: [],
			active_tabs: [],
			message: e.message || 'Gagal merender preview'
		};
	}
}
