/**
 * Find the index of a marker, preferring an occurrence that stands alone on
 * its own line (only whitespace before it on that line).
 *
 * Falls back to the first plain occurrence when the marker is only mentioned
 * inline in prose. Mirrors the backend helper `_find_marker_index`.
 */
export function findMarkerIndex(content: string, marker: string, fromIndex = 0): number {
	let idx = content.indexOf(marker, fromIndex);
	let fallbackIdx = -1;
	while (idx !== -1) {
		const prevNewline = content.lastIndexOf('\n', idx - 1);
		const linePrefix = content.slice(prevNewline + 1, idx);
		if (/^[ \t]*$/.test(linePrefix)) {
			return idx;
		}
		if (fallbackIdx === -1) {
			fallbackIdx = idx;
		}
		idx = content.indexOf(marker, idx + marker.length);
	}
	return fallbackIdx;
}

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

	const startIdx = findMarkerIndex(content, startMarker);
	if (startIdx === -1) {
		return ['', content];
	}

	const endIdx = findMarkerIndex(content, endMarker, startIdx + startMarker.length);
	if (endIdx === -1 || endIdx <= startIdx) {
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
	const startIdx = findMarkerIndex(content, startMarker);
	const endIdx = startIdx !== -1 ? findMarkerIndex(content, endMarker, startIdx + startMarker.length) : -1;

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
