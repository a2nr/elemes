/**
 * Svelte action that prevents an element from stealing focus from the
 * currently-focused text editor when tapped/clicked.
 *
 * Used on workspace tool buttons (quick-tools-rail, tabs, save/publish)
 * so interacting with the workspace does not blur the inline editor.
 *
 * Note: we deliberately do NOT preventDefault on touchstart, because doing
 * so suppresses the subsequent `click` event on mobile browsers. mousedown
 * (which fires as a compatibility event after touchend on touch devices)
 * is sufficient to block the focus change while still letting click fire.
 */
export function preserveFocus(node: HTMLElement) {
	function onDown(e: Event) {
		e.preventDefault();
	}

	node.addEventListener('pointerdown', onDown, { passive: false });
	node.addEventListener('mousedown', onDown, { passive: false });

	return {
		destroy() {
			node.removeEventListener('pointerdown', onDown);
			node.removeEventListener('mousedown', onDown);
		}
	};
}
