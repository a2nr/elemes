import { marked } from 'marked';
import { extractSection } from './extractSections';
import { processCircuitEmbeds, processFlowchartEmbeds, processEmbedEmbeds } from './processEmbeds';

/**
 * Extract, parse and return slides HTML and the cleaned lesson content.
 */
export function parseSlides(content: string): { slides: string[]; contentWithoutSlides: string } {
	const startMarker = '---slide-start---';
	const endMarker = '---slide-end---';

	const [slidesRaw] = extractSection(content, startMarker, endMarker);
	let contentWithoutSlides = content;
	const slidesHtml: string[] = [];

	if (slidesRaw) {
		const sIdx = content.indexOf(startMarker);
		const eIdx = content.indexOf(endMarker);
		if (sIdx !== -1 && eIdx !== -1 && eIdx > sIdx) {
			contentWithoutSlides =
				content.substring(0, sIdx) +
				'<div id="slide-mount-point"></div>' +
				content.substring(eIdx + endMarker.length);
		}

		// Split slides by "---" on a line by itself
		const slideParts = slidesRaw.split(/^\s*---\s*$/m);
		for (let s of slideParts) {
			s = s.trim();
			if (s) {
				s = processCircuitEmbeds(s);
				s = processFlowchartEmbeds(s);
				s = processEmbedEmbeds(s);

				const placeholders: Record<string, string> = {};
				let counter = 0;
				let text = s.replace(/<div class="(?:circuit|flowchart)-embed"[\s\S]*?<\/div>/g, (match) => {
					const id = `%%EMBED_BLOCK_${counter++}%%`;
					placeholders[id] = match;
					return `\n\n${id}\n\n`;
				});

				let html = marked.parse(text, { breaks: true, gfm: true }) as string;
				for (const [id, originalHtml] of Object.entries(placeholders)) {
					html = html.replace(`<p>${id}</p>`, originalHtml).replace(id, originalHtml);
				}

				slidesHtml.push(html);
			}
		}
	}

	return {
		slides: slidesHtml,
		contentWithoutSlides
	};
}
