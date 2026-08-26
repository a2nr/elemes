import { marked } from 'marked';
import { processCircuitEmbeds, processFlowchartEmbeds, processEmbedEmbeds } from './processEmbeds';

const OPTION_LINE_RE = /^\s*-\s*\[([ xX]?)\]\s*(.*)$/;

export interface QuizOption {
	id: string;
	text: string | Promise<string>;
	is_correct: boolean;
}

export interface QuizCard {
	id: string;
	type: 'mcq' | 'flashcard';
	question?: string | Promise<string>;
	front?: string | Promise<string>;
	back?: string | Promise<string>;
	options: QuizOption[] | null;
	explanation: string | Promise<string>;
	image: string;
	category: string;
}

/**
 * Yield (pos, mark, content) for option lines outside fenced code blocks.
 */
export function iterOptionLines(body: string): { pos: number; mark: string; content: string }[] {
	const lines = body.split('\n');
	let inFence = false;
	let pos = 0;
	const results: { pos: number; mark: string; content: string }[] = [];

	for (const line of lines) {
		if (line.trim().startsWith('```')) {
			inFence = !inFence;
		} else if (!inFence) {
			const m = line.match(OPTION_LINE_RE);
			if (m) {
				results.push({
					pos,
					mark: m[1],
					content: m[2]
				});
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
		if (match) {
			const url = match[1].trim();
			const matchStart = line.indexOf(match[0]);
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
 * Parse a string of markdown with headings and options into a list of quiz objects.
 */
export function parseFlashcards(text: string): QuizCard[] {
	if (!text.trim()) {
		return [];
	}

	// Split by headings starting with #, ##, or ### at the start of a line
	const parts = text.split(/^#{1,3}\s+/m);
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

		const optionLines = iterOptionLines(body);
		const firstOptionIdx = optionLines.length > 0 ? optionLines[0].pos : body.length;

		// Explanation blockquote: after options for MCQ, anywhere for flashcard
		const explanationSearchRegion = body.substring(firstOptionIdx);
		const explanationMatch = explanationSearchRegion.match(/^\s*(>[\s\S]*)$/m);
		const explanation = explanationMatch ? explanationMatch[1].trim() : '';

		const qId = `q-${flashcards.length}`;

		if (optionLines.length > 0) {
			const parsedOptions: QuizOption[] = [];
			for (const opt of optionLines) {
				const isCorrect = opt.mark.toLowerCase() === 'x';
				parsedOptions.push({
					id: `${qId}-o-${parsedOptions.length}`,
					text: renderMarkdown(opt.content.trim()),
					is_correct: isCorrect
				});
			}

			const correctCount = parsedOptions.filter((opt) => opt.is_correct).length;
			if (correctCount !== 1) {
				throw new Error(
					`Soal kuis ke-${flashcards.length + 1} wajib punya tepat satu opsi benar ` +
						`(ditemukan ${correctCount}).`
				);
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
				question: renderMarkdown(promptText),
				options: parsedOptions,
				explanation: explanation ? renderMarkdown(explanation) : '',
				image: imageUrl,
				category: category
			});
		} else {
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
