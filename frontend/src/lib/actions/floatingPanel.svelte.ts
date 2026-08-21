/**
 * Reactive state & event handlers for a draggable, resizable floating panel.
 */

export interface FloatPos {
	top: number;
	left: number;
}

export interface FloatSize {
	width: number;
	height: number;
}

export function createFloatingPanel() {
	let floating = $state(false);
	let minimized = $state(false);
	let dragging = $state(false);
	let pos = $state<FloatPos | null>(null);
	let size = $state<FloatSize | null>(null);

	let dragOffset = { x: 0, y: 0 };

	const style = $derived.by(() => {
		if (floating && !minimized) {
			let s = '';
			if (pos) s += `top:${pos.top}px;left:${pos.left}px;bottom:auto;right:auto;`;
			if (size) s += `width:${size.width}px;height:${size.height}px;`;
			return s;
		}
		return '';
	});

	function getPanelFromTarget(target: HTMLElement | null): HTMLElement | null {
		return target?.closest('.editor-area') as HTMLElement | null;
	}

	function onDragStart(e: MouseEvent) {
		if (!floating) return;
		e.preventDefault();
		const panel = getPanelFromTarget(e.currentTarget as HTMLElement);
		if (!panel) return;
		dragging = true;
		const rect = panel.getBoundingClientRect();
		dragOffset = { x: e.clientX - rect.left, y: e.clientY - rect.top };
		if (!size) {
			size = { width: rect.width, height: rect.height };
		}

		const onMove = (ev: MouseEvent) => {
			if (!dragging) return;
			const newLeft = Math.max(0, Math.min(window.innerWidth - 100, ev.clientX - dragOffset.x));
			const newTop = Math.max(0, Math.min(window.innerHeight - 48, ev.clientY - dragOffset.y));
			pos = { top: newTop, left: newLeft };
		};
		const onUp = () => {
			dragging = false;
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
		};
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
	}

	function onTouchDragStart(e: TouchEvent) {
		if (!floating) return;
		const panel = getPanelFromTarget(e.currentTarget as HTMLElement);
		if (!panel) return;
		dragging = true;
		const rect = panel.getBoundingClientRect();
		const touch = e.touches[0];
		dragOffset = { x: touch.clientX - rect.left, y: touch.clientY - rect.top };
		if (!size) {
			size = { width: rect.width, height: rect.height };
		}

		const onMove = (ev: TouchEvent) => {
			if (!dragging) return;
			const t = ev.touches[0];
			const newLeft = Math.max(0, Math.min(window.innerWidth - 100, t.clientX - dragOffset.x));
			const newTop = Math.max(0, Math.min(window.innerHeight - 48, t.clientY - dragOffset.y));
			pos = { top: newTop, left: newLeft };
		};
		const onUp = () => {
			dragging = false;
			window.removeEventListener('touchmove', onMove);
			window.removeEventListener('touchend', onUp);
		};
		window.addEventListener('touchmove', onMove, { passive: false });
		window.addEventListener('touchend', onUp);
	}

	function onResizeStart(e: MouseEvent) {
		if (!floating) return;
		e.preventDefault();
		const panel = getPanelFromTarget(e.currentTarget as HTMLElement);
		if (!panel) return;
		const rect = panel.getBoundingClientRect();
		const startX = e.clientX;
		const startY = e.clientY;
		const startW = rect.width;
		const startH = rect.height;
		const startLeft = rect.left;
		const startTop = rect.top;

		const onMove = (ev: MouseEvent) => {
			const dx = startX - ev.clientX;
			const dy = startY - ev.clientY;
			const newW = Math.max(320, startW + dx);
			const newH = Math.max(200, startH + dy);
			size = { width: newW, height: newH };
			pos = {
				left: startLeft - (newW - startW),
				top: startTop - (newH - startH),
			};
		};
		const onUp = () => {
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
		};
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
	}

	function onTouchResizeStart(e: TouchEvent) {
		if (!floating) return;
		const panel = getPanelFromTarget(e.currentTarget as HTMLElement);
		if (!panel) return;
		const rect = panel.getBoundingClientRect();
		const touch = e.touches[0];
		const startX = touch.clientX;
		const startY = touch.clientY;
		const startW = rect.width;
		const startH = rect.height;
		const startLeft = rect.left;
		const startTop = rect.top;

		const onMove = (ev: TouchEvent) => {
			const t = ev.touches[0];
			const dx = startX - t.clientX;
			const dy = startY - t.clientY;
			const newW = Math.max(320, startW + dx);
			const newH = Math.max(200, startH + dy);
			size = { width: newW, height: newH };
			pos = {
				left: startLeft - (newW - startW),
				top: startTop - (newH - startH),
			};
		};
		const onUp = () => {
			window.removeEventListener('touchmove', onMove);
			window.removeEventListener('touchend', onUp);
		};
		window.addEventListener('touchmove', onMove, { passive: false });
		window.addEventListener('touchend', onUp);
	}

	function toggle() {
		floating = !floating;
		minimized = false;
		pos = null;
		size = null;
	}

	function minimize() {
		minimized = true;
	}

	function restore() {
		minimized = false;
	}

	return {
		get floating() { return floating; },
		set floating(v: boolean) { floating = v; },
		get minimized() { return minimized; },
		set minimized(v: boolean) { minimized = v; },
		get style() { return style; },
		toggle,
		minimize,
		restore,
		onDragStart,
		onTouchDragStart,
		onResizeStart,
		onTouchResizeStart,
	};
}
