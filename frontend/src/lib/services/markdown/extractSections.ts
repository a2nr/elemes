/**
 * Extract content between startMarker and endMarker, returning the extracted content
 * and the remaining content with the markers and extracted block removed.
 */
export function extractSection(
	content: string,
	startMarker: string,
	endMarker: string
): [string, string] {
	if (!content.includes(startMarker) || !content.includes(endMarker)) {
		return ['', content];
	}

	const startIdx = content.indexOf(startMarker);
	const endIdx = content.indexOf(endMarker);

	if (startIdx === -1 || endIdx === -1 || endIdx <= startIdx) {
		return ['', content];
	}

	const extracted = content.substring(startIdx + startMarker.length, endIdx).trim();
	const remaining = content.substring(0, startIdx) + content.substring(endIdx + endMarker.length);

	return [extracted, remaining];
}

/**
 * Update the inner content between startMarker and endMarker in content,
 * or append the section block at the end if the markers are not present.
 */
export function upsertSection(
	content: string,
	startMarker: string,
	endMarker: string,
	newInnerContent: string
): string {
	const trimmedInner = newInnerContent.trim();
	const startIdx = content.indexOf(startMarker);
	const endIdx = content.indexOf(endMarker);

	if (startIdx !== -1 && endIdx !== -1 && endIdx > startIdx) {
		return (
			content.substring(0, startIdx + startMarker.length) +
			'\n' +
			trimmedInner +
			'\n' +
			content.substring(endIdx)
		);
	} else {
		const trimmedContent = content.trimEnd();
		return `${trimmedContent}\n\n${startMarker}\n${trimmedInner}\n${endMarker}\n`;
	}
}
