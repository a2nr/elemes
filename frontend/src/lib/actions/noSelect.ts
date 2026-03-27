/**
 * Svelte action that prevents text selection inside the node.
 * Uses both CSS and JS (selectionchange) as a fallback for mobile browsers.
 */
export function noSelect(node: HTMLElement) {
	function clearIfInside() {
		const sel = window.getSelection();
		if (!sel || sel.isCollapsed) return;
		const anchor = sel.anchorNode;
		if (anchor && node.contains(anchor)) {
			sel.removeAllRanges();
		}
	}

	document.addEventListener('selectionchange', clearIfInside);
	document.addEventListener('mouseup', clearIfInside);
	document.addEventListener('touchend', clearIfInside);

	return {
		destroy() {
			document.removeEventListener('selectionchange', clearIfInside);
			document.removeEventListener('mouseup', clearIfInside);
			document.removeEventListener('touchend', clearIfInside);
		}
	};
}
