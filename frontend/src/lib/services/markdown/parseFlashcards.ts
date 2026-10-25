import { marked } from 'marked';
import { processCircuitEmbeds, processFlowchartEmbeds, processEmbedEmbeds } from './processEmbeds';

/**
 * Regex opsi LEGACY (key ---QUIZ_FLASHCARD--- lama).
 * Hanya mengenali '- [x]' / '- [X]' / '- [ ]' / '- []'.
 * Sengaja TIDAK mengenali '- [10]' supaya konten legacy berperilaku sama
 * persis dengan versi sebelum pemisahan key.
 */
const OPTION_LINE_RE = /^\s*-\s*\[([ xX]?)\]\s*(.*)$/;

/**
 * Regex opsi KEY BARU (---QUIZ_MCQ--- / ---QUIZ_WEIGHTED--- / ---FLASHCARD---).
 * group(1) = mark ('x'/'X'/' '/''), group(2) = bobot angka opsional.
 */
const WEIGHTED_OPTION_LINE_RE = /^\s*-\s*\[([ xX]?)(\d*)\]\s*(.*)$/;

/**
 * Jenis key quiz → model evaluasi.
 * - 'legacy'   → key lama ---QUIZ_FLASHCARD---: jenis implisit via inspeksi
 *                konten (ada opsi → MCQ, tanpa opsi → flashcard).
 * - 'mcq'      → ---QUIZ_MCQ---: wajib opsi, tepat satu [x].
 * - 'weighted' → ---QUIZ_WEIGHTED---: bobot [N] (N >= 1), minimal satu [ ].
 * - 'flashcard'→ ---FLASHCARD---: tanpa opsi jawaban.
 */
export type QuizParseKind = 'legacy' | 'mcq' | 'weighted' | 'flashcard';

export type QuizType = 'mcq' | 'weighted' | 'flashcard';

export interface QuizOption {
	id: string;
	text: string | Promise<string>;
	is_correct: boolean;
	/** Bobot nilai opsi (>= 0). Legacy: benar 1 / salah 0. Weighted: nilai [N]. */
	weight: number;
}

export interface QuizCard {
	id: string;
	type: 'mcq' | 'flashcard';
	/** Jenis quiz menurut key asalnya — menentukan model penilaian. */
	quiz_type: QuizType;
	question?: string | Promise<string>;
	front?: string | Promise<string>;
	back?: string | Promise<string>;
	options: QuizOption[] | null;
	explanation: string | Promise<string>;
	image: string;
	category: string;
}

/**
 * Yield (pos, mark, weight, content) for option lines outside fenced code blocks.
 */
export function iterOptionLines(
	body: string,
	kind: QuizParseKind = 'legacy'
): { pos: number; mark: string; weight: string; content: string }[] {
	const lines = body.split('\n');
	let inFence = false;
	let pos = 0;
	const results: { pos: number; mark: string; weight: string; content: string }[] = [];

	for (const line of lines) {
		if (line.trim().startsWith('```')) {
			inFence = !inFence;
		} else if (!inFence) {
			if (kind === 'legacy') {
				const m = line.match(OPTION_LINE_RE);
				if (m) {
					results.push({
						pos,
						mark: m[1],
						weight: '',
						content: m[2]
					});
				}
			} else {
				const m = line.match(WEIGHTED_OPTION_LINE_RE);
				if (m) {
					results.push({
						pos,
						mark: m[1],
						weight: m[2],
						content: m[3]
					});
				}
			}
		}
		pos += line.length + 1; // +1 for the newline character
	}
	return results;
}

/**
 * Return [imageUrl, cleanedText] for the first markdown image found outside fenced code blocks.
 */
export function extractBodyImage(text: string): [string | null, string] {
	const lines = text.split('\n');
	let inFence = false;

	for (let idx = 0; idx < lines.length; idx++) {
		const line = lines[idx];
		if (line.trim().startsWith('```')) {
			inFence = !inFence;
			continue;
		}
		if (inFence) {
			continue;
		}
		const match = line.match(/!\[[^\]]*\]\(([^)]+)\)/);
		if (match && match.index !== undefined) {
			const url = match[1].trim();
			const matchStart = match.index;
			const matchEnd = matchStart + match[0].length;
			const cleanedLine = line.substring(0, matchStart) + line.substring(matchEnd);

			const cleanedLines = [
				...lines.slice(0, idx),
				...(cleanedLine.trim() ? [cleanedLine] : []),
				...lines.slice(idx + 1)
			];
			return [url, cleanedLines.join('\n').trim()];
		}
	}
	return [null, text];
}

/**
 * Split markdown into per-question blocks on heading lines (`^#{1,3}\s+`),
 * ignoring heading-looking lines that live INSIDE a fenced code block.
 *
 * Mirror dari `_split_flashcard_parts` (backend) supaya preview guru dan
 * hasil parse backend selalu sama.
 */
export function splitFlashcardParts(text: string): string[] {
	const parts: string[] = [];
	let buf: string[] = [];
	let inFence = false;

	for (const line of text.split('\n')) {
		const stripped = line.trim();
		if (stripped.startsWith('```')) {
			inFence = !inFence;
			buf.push(line);
			continue;
		}
		if (!inFence && /^#{1,3}\s+/.test(line)) {
			if (buf.length > 0) {
				parts.push(buf.join('\n'));
			}
			buf = [line];
			continue;
		}
		buf.push(line);
	}
	if (buf.length > 0) {
		parts.push(buf.join('\n'));
	}
	return parts.filter((p) => p.trim().length > 0);
}

/**
 * Validasi ketat opsi per jenis key. Return { isCorrect, weights }.
 *
 * - 'legacy'  : tepat satu [x]; bobot diturunkan (benar=1, salah=0)
 * - 'mcq'     : tepat satu [x]; DILARANG memakai bobot angka ([N])
 * - 'weighted': DILARANG [x]; bobot integer >= 1; minimal satu opsi tanpa
 *               bobot ([ ]); bobot tertinggi harus unik
 * - 'flashcard': opsi jawaban DILARANG
 */
function validateQuizOptions(
	kind: QuizParseKind,
	questionNo: number,
	marks: string[],
	weights: (number | null)[]
): { isCorrect: boolean[]; weights: number[] } {
	if (kind === 'flashcard') {
		throw new Error(
			`Soal kuis ke-${questionNo} di FLASHCARD tidak boleh punya opsi jawaban; ` +
				`pindahkan soal pilihan ganda ke key QUIZ_MCQ atau QUIZ_WEIGHTED.`
		);
	}

	if (kind === 'legacy' || kind === 'mcq') {
		if (kind === 'mcq' && weights.some((w) => w !== null)) {
			throw new Error(
				`Soal kuis ke-${questionNo} di QUIZ_MCQ tidak boleh memakai bobot angka ` +
					`([N]); gunakan [x] untuk jawaban benar.`
			);
		}
		const correctCount = marks.filter((m) => m.toLowerCase() === 'x').length;
		if (correctCount !== 1) {
			throw new Error(
				`Soal kuis ke-${questionNo} wajib punya tepat satu opsi benar ` +
					`(ditemukan ${correctCount}).`
			);
		}
		const isCorrect = marks.map((m) => m.toLowerCase() === 'x');
		return { isCorrect, weights: isCorrect.map((ok) => (ok ? 1 : 0)) };
	}

	// kind === 'weighted'
	if (marks.some((m) => m.toLowerCase() === 'x')) {
		throw new Error(
			`Soal kuis ke-${questionNo} di QUIZ_WEIGHTED tidak boleh memakai penanda [x]; ` +
				`gunakan bobot angka ([N]) atau [ ] untuk jawaban salah.`
		);
	}
	if (weights.some((w) => w !== null && w < 1)) {
		throw new Error(
			`Soal kuis ke-${questionNo} di QUIZ_WEIGHTED: bobot harus berupa bilangan bulat >= 1.`
		);
	}
	if (!weights.some((w) => w === null)) {
		throw new Error(
			`Soal kuis ke-${questionNo} di QUIZ_WEIGHTED wajib punya minimal satu opsi tanpa ` +
				`bobot ([ ]) sebagai jawaban salah.`
		);
	}
	const numeric = weights.filter((w): w is number => w !== null);
	let isCorrect: boolean[];
	if (numeric.length > 0) {
		const maxWeight = Math.max(...numeric);
		const top = weights.filter((w) => w === maxWeight).length;
		if (top > 1) {
			throw new Error(
				`Soal kuis ke-${questionNo} di QUIZ_WEIGHTED: bobot tertinggi harus unik ` +
					`(ditemukan ${top} opsi dengan bobot ${maxWeight}).`
			);
		}
		isCorrect = weights.map((w) => w === maxWeight);
	} else {
		isCorrect = weights.map(() => false);
	}
	return { isCorrect, weights: weights.map((w) => (w === null ? 0 : w)) };
}

/**
 * Parse a string of markdown with headings and options into a list of quiz objects.
 *
 * `kind` menentukan model evaluasi & validasi per jenis key (lihat QuizParseKind).
 * `idOffset` dipakai saat beberapa blok key quiz digabung agar id soal unik.
 */
export function parseFlashcards(
	text: string,
	kind: QuizParseKind = 'legacy',
	idOffset = 0
): QuizCard[] {
	if (!text.trim()) {
		return [];
	}

	// Split by headings starting with #, ##, or ### at the start of a line
	// (heading di dalam code fence diabaikan).
	const parts = splitFlashcardParts(text);
	const flashcards: QuizCard[] = [];

	const renderMarkdown = (md: string) => {
		return marked.parse(md, { breaks: true, gfm: true }) as string;
	};

	for (const part of parts) {
		if (!part.trim()) {
			continue;
		}

		// First line is the question (Front)
		const subparts = part.split('\n');
		const question = subparts[0].trim();
		let body = subparts.slice(1).join('\n');

		if (!question) {
			continue;
		}

		let imageUrl = '';

		// Extract image from markdown syntax ![...](path) in question
		const mdImageMatch = question.match(/!\[.*?\]\(([^)]+)\)/);
		if (mdImageMatch) {
			const mdImagePath = mdImageMatch[1].trim();
			if (
				mdImagePath.startsWith('/assets/') ||
				(!mdImagePath.startsWith('http://') && !mdImagePath.startsWith('https://'))
			) {
				imageUrl = mdImagePath;
			}
		}

		// Check for image: URL directive in body
		const imageMatch = body.match(/^\s*image:\s*(.*)$/m);
		if (imageMatch) {
			imageUrl = imageMatch[1].trim();
			if (
				!imageUrl.startsWith('/assets/') &&
				!imageUrl.startsWith('http://') &&
				!imageUrl.startsWith('https://') &&
				!imageUrl.startsWith('/')
			) {
				imageUrl = `/assets/${imageUrl}`;
			}
			body = body.replace(/^\s*image:\s*.*$/gm, '').trim();
		}

		// Check for ::diagnostic marker
		let category = 'evaluasi';
		if (/^\s*::diagnostic\s*$/m.test(body)) {
			category = 'diagnostik';
			body = body.replace(/^\s*::diagnostic\s*$/gm, '').trim();
		}

		const optionLines = iterOptionLines(body, kind);
		const firstOptionIdx = optionLines.length > 0 ? optionLines[0].pos : body.length;

		// Explanation blockquote: after options for MCQ, anywhere for flashcard
		const explanationSearchRegion = optionLines.length > 0
			? body.substring(firstOptionIdx)
			: body;
		const explanationMatch = explanationSearchRegion.match(/^\s*(>[\s\S]*)$/m);
		const explanation = explanationMatch ? explanationMatch[1].trim() : '';

		const qId = `q-${idOffset + flashcards.length}`;
		const questionNo = idOffset + flashcards.length + 1;

		if (optionLines.length > 0) {
			const marks = optionLines.map((o) => o.mark);
			const rawWeights = optionLines.map((o) => (o.weight ? parseInt(o.weight, 10) : null));
			const { isCorrect, weights } = validateQuizOptions(kind, questionNo, marks, rawWeights);

			const parsedOptions: QuizOption[] = [];
			for (let i = 0; i < optionLines.length; i++) {
				const opt = optionLines[i];
				parsedOptions.push({
					id: `${qId}-o-${parsedOptions.length}`,
					text: renderMarkdown(opt.content.trim()),
					is_correct: isCorrect[i],
					weight: weights[i]
				});
			}

			let promptBody = body.substring(0, firstOptionIdx).trim();

			// Extract markdown image from prompt body if no image yet
			if (!imageUrl) {
				const [extractedUrl, cleanedPromptBody] = extractBodyImage(promptBody);
				if (extractedUrl) {
					imageUrl = extractedUrl;
					promptBody = cleanedPromptBody;
				}
			}

			let promptText = promptBody ? `${question}\n\n${promptBody}` : question;
			promptText = processCircuitEmbeds(promptText);
			promptText = processFlowchartEmbeds(promptText);
			promptText = processEmbedEmbeds(promptText);

			flashcards.push({
				id: qId,
				type: 'mcq',
				quiz_type: kind === 'weighted' ? 'weighted' : 'mcq',
				question: renderMarkdown(promptText),
				options: parsedOptions,
				explanation: explanation ? renderMarkdown(explanation) : '',
				image: imageUrl,
				category: category
			});
		} else {
			// Tanpa opsi → flashcard. Pada key QUIZ_MCQ / QUIZ_WEIGHTED ini
			// tidak valid (wajib ada opsi jawaban).
			if (kind === 'mcq') {
				throw new Error(
					`Soal kuis ke-${questionNo} di QUIZ_MCQ wajib punya opsi jawaban.`
				);
			}
			if (kind === 'weighted') {
				throw new Error(
					`Soal kuis ke-${questionNo} di QUIZ_WEIGHTED wajib punya opsi jawaban.`
				);
			}

			// Simple Flashcard
			let cleanBack = body;
			if (explanationMatch) {
				const expIdx = body.indexOf(explanationMatch[1]);
				if (expIdx !== -1) {
					cleanBack = body.substring(0, expIdx).trim();
				}
			}

			flashcards.push({
				id: qId,
				type: 'flashcard',
				quiz_type: 'flashcard',
				front: renderMarkdown(question),
				back: renderMarkdown(cleanBack),
				explanation: explanation ? renderMarkdown(explanation) : '',
				image: imageUrl,
				options: null,
				category: category
			});
		}
	}

	return flashcards;
}
