import { marked } from 'marked';
import { extractSection, findMarkerIndex } from './extractSections';
import { detectActiveTabs } from './detectActiveTabs';
import { parseFlashcards, type QuizCard, type QuizParseKind } from './parseFlashcards';
import { parseSlides } from './parseSlides';
import { processCircuitEmbeds, processFlowchartEmbeds, processEmbedEmbeds } from './processEmbeds';

/**
 * Blok key quiz (baru + legacy) beserta model evaluasinya.
 * Ekstraksi memilih marker start PALING AWAL berulang-ulang sampai habis,
 * supaya soal gabungan (bisa lebih dari satu blok per key) berurutan dokumen
 * dan id-nya (q-0, q-1, ...) identik dengan backend (parity).
 */
const QUIZ_SECTION_SPECS: { start: string; end: string; kind: QuizParseKind }[] = [
	{ start: '---QUIZ_FLASHCARD---', end: '---END_QUIZ_FLASHCARD---', kind: 'legacy' },
	{ start: '---QUIZ_MCQ---', end: '---END_QUIZ_MCQ---', kind: 'mcq' },
	{ start: '---QUIZ_WEIGHTED---', end: '---END_QUIZ_WEIGHTED---', kind: 'weighted' },
	{ start: '---FLASHCARD---', end: '---END_FLASHCARD---', kind: 'flashcard' }
];

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

		// Blok kuis (key baru + legacy): ambil marker start PALING AWAL berulang-ulang
		// (mendukung beberapa blok per key), ekstrak urut dokumen, lalu gabungkan
		// menjadi satu daftar soal datar — sesi/attempt kuis tetap satu.
		const quiz_data: QuizCard[] = [];
		for (;;) {
			let best: { idx: number; spec: (typeof QUIZ_SECTION_SPECS)[number] } | null = null;
			for (const spec of QUIZ_SECTION_SPECS) {
				const idx = findMarkerIndex(content, spec.start);
				if (idx !== -1 && (best === null || idx < best.idx)) {
					best = { idx, spec };
				}
			}
			if (!best) break;
			let raw = '';
			[raw, content] = extractSection(content, best.spec.start, best.spec.end);
			if (!raw) {
				// Blok kosong → marker sudah terangkat; blok tidak valid (marker
				// end hilang) → konten tak berubah. Buang marker start supaya
				// loop selalu maju (mirror backend _extract_quiz_sections).
				const idx = findMarkerIndex(content, best.spec.start);
				if (idx !== -1) {
					content = content.slice(0, idx) + content.slice(idx + best.spec.start.length);
				}
				continue;
			}
			quiz_data.push(...parseFlashcards(raw, best.spec.kind, quiz_data.length));
		}

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

export { extractSection, upsertSection } from './extractSections';
