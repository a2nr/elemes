<script lang="ts">
	import { env } from '$env/dynamic/public';

	interface Props {
		iframe: HTMLIFrameElement;
	}

	let { iframe }: Props = $props();

	let overlayEl: HTMLDivElement;
	let crosshairX = $state(0);
	let crosshairY = $state(0);
	let longPressTimer: ReturnType<typeof setTimeout> | null = null;
	let currentPointerX = 0;
	let currentPointerY = 0;
	let pointerDown = false;
	let isTouchDevice = $state(false);
	let lastTapTime = 0;
	let tapCount = 0;
	let singleTapTimer: ReturnType<typeof setTimeout> | null = null;
	let holdingTimer: ReturnType<typeof setTimeout> | null = null;

	// Two-finger tap detection
	let activePointers = new Map<number, { x: number; y: number }>();
	let twoFingerTapped = false;

	const LONG_PRESS_MS = 400;
	const DOUBLE_TAP_MS = 300;
	const HOLDING_TIMEOUT_MS = 5000;
	const BASE_OFFSET_Y = -(parseInt(env.PUBLIC_CURSOR_OFFSET_Y || '50', 10));
	let currentOffset = $derived(isTouchDevice ? BASE_OFFSET_Y : 0);

	/**
	 * State machine:
	 *   idle         → long tap → aiming_start (crosshair muncul, belum click)
	 *   aiming_start → release  → holding      (mousedown di crosshair, crosshair hilang)
	 *   holding      → long tap → aiming_end   (crosshair muncul lagi, mousemove live)
	 *   aiming_end   → release  → idle         (mouseup di crosshair, selesai)
	 *
	 *   idle    → short tap → forward click
	 *   holding → short tap → mouseup di posisi tap → idle
	 */
	type Phase = 'idle' | 'aiming_start' | 'holding' | 'aiming_end';
	let phase = $state<Phase>('idle');
	let showCrosshair = $derived(phase === 'aiming_start' || phase === 'aiming_end');

	$effect(() => {
		if (typeof window === 'undefined') return;
		const mql = window.matchMedia('(hover: none) and (pointer: coarse)');
		const checkTouch = () => {
			isTouchDevice = mql.matches && window.innerWidth < 768;
		};
		
		checkTouch();
		mql.addEventListener('change', checkTouch);
		window.addEventListener('resize', checkTouch);
		
		return () => {
			mql.removeEventListener('change', checkTouch);
			window.removeEventListener('resize', checkTouch);
		};
	});

	function getIframeTarget(x: number, y: number): Element | null {
		try {
			const doc = iframe?.contentDocument;
			if (!doc) {
				console.warn('[Crosshair] contentDocument null — mungkin cross-origin');
				return null;
			}
			// Coba elementFromPoint dulu, fallback ke canvas
			const el = doc.elementFromPoint(x, y);
			if (el) return el;
			return doc.querySelector('canvas');
		} catch (e) {
			console.warn('[Crosshair] Gagal akses iframe:', e);
			return null;
		}
	}

	function dispatchToCanvas(type: string, viewportX: number, viewportY: number) {
		const iframeRect = iframe.getBoundingClientRect();
		const x = viewportX - iframeRect.left;
		const y = viewportY - iframeRect.top;

		const target = getIframeTarget(x, y);
		if (!target) {
			console.warn('[Crosshair] Tidak ada target untuk dispatch', type);
			return;
		}

		target.dispatchEvent(
			new MouseEvent(type, {
				clientX: x,
				clientY: y,
				screenX: viewportX,
				screenY: viewportY,
				bubbles: true,
				cancelable: true,
				button: 0,
				buttons: type === 'mouseup' ? 0 : 1,
				view: iframe.contentWindow!
			})
		);
	}

	function dispatchRightClick(viewportX: number, viewportY: number) {
		const iframeRect = iframe.getBoundingClientRect();
		const x = viewportX - iframeRect.left;
		const y = viewportY - iframeRect.top;
		const target = getIframeTarget(x, y);
		if (!target) return;

		const opts = {
			clientX: x,
			clientY: y,
			screenX: viewportX,
			screenY: viewportY,
			bubbles: true,
			cancelable: true,
			button: 2,
			buttons: 2,
			view: iframe.contentWindow!
		};

		target.dispatchEvent(new MouseEvent('mousedown', opts));
		target.dispatchEvent(new MouseEvent('contextmenu', opts));
		target.dispatchEvent(new MouseEvent('mouseup', { ...opts, buttons: 0 }));
	}

	function focusIfEditable(viewportX: number, viewportY: number) {
		const iframeRect = iframe.getBoundingClientRect();
		const x = viewportX - iframeRect.left;
		const y = viewportY - iframeRect.top;
		const target = getIframeTarget(x, y);
		if (!target) return;

		const tag = target.tagName.toLowerCase();
		const isEditable =
			tag === 'input' || tag === 'textarea' || tag === 'select' ||
			(target as HTMLElement).isContentEditable;

		if (isEditable) {
			(target as HTMLElement).focus();
		}
	}

	function updateCrosshairPos(viewportX: number, viewportY: number) {
		if (!overlayEl) return;
		const rect = overlayEl.getBoundingClientRect();
		crosshairX = viewportX - rect.left;
		crosshairY = viewportY - rect.top + currentOffset;
	}

	function getCrosshairViewport(): { x: number; y: number } {
		const rect = overlayEl?.getBoundingClientRect();
		if (!rect) return { x: currentPointerX, y: currentPointerY };
		return { x: rect.left + crosshairX, y: rect.top + crosshairY };
	}

	function cancelTimer() {
		if (longPressTimer) {
			clearTimeout(longPressTimer);
			longPressTimer = null;
		}
	}

	function cancelSingleTapTimer() {
		if (singleTapTimer) {
			clearTimeout(singleTapTimer);
			singleTapTimer = null;
		}
	}

	function cancelHoldingTimer() {
		if (holdingTimer) {
			clearTimeout(holdingTimer);
			holdingTimer = null;
		}
	}

	function startHoldingTimeout() {
		cancelHoldingTimer();
		holdingTimer = setTimeout(() => {
			// Timeout — lepas click otomatis, kembali ke idle
			if (phase === 'holding') {
				dispatchToCanvas('mouseup', currentPointerX, currentPointerY);
				phase = 'idle';
			}
		}, HOLDING_TIMEOUT_MS);
	}

	function vibrate() {
		if (typeof navigator !== 'undefined' && navigator.vibrate) {
			navigator.vibrate(30);
		}
	}

	function handlePointerDown(e: PointerEvent) {
		if (e.pointerType !== 'touch') return;
		e.preventDefault();

		activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

		// Jari kedua turun → two-finger tap candidate, batalkan gesture lain
		if (activePointers.size >= 2) {
			cancelTimer();
			cancelSingleTapTimer();
			twoFingerTapped = true;
			return;
		}

		pointerDown = true;
		twoFingerTapped = false;
		currentPointerX = e.clientX;
		currentPointerY = e.clientY;

		if (phase === 'idle' || phase === 'holding') {
			cancelTimer();
			cancelSingleTapTimer();
			longPressTimer = setTimeout(() => {
				// Long press detected
				updateCrosshairPos(currentPointerX, currentPointerY);
				vibrate();

				if (phase === 'idle') {
					phase = 'aiming_start';
				} else if (phase === 'holding') {
					cancelHoldingTimer();
					phase = 'aiming_end';
				}
			}, LONG_PRESS_MS);
		}
	}

	function handlePointerMove(e: PointerEvent) {
		if (e.pointerType !== 'touch' || !pointerDown) return;
		e.preventDefault();

		currentPointerX = e.clientX;
		currentPointerY = e.clientY;

		if (phase === 'aiming_start') {
			updateCrosshairPos(currentPointerX, currentPointerY);
		} else if (phase === 'aiming_end') {
			updateCrosshairPos(currentPointerX, currentPointerY);
			// Live mousemove saat aiming release point
			const ch = getCrosshairViewport();
			dispatchToCanvas('mousemove', ch.x, ch.y);
		}
	}

	function handlePointerUp(e: PointerEvent) {
		if (e.pointerType !== 'touch') return;
		e.preventDefault();

		activePointers.delete(e.pointerId);

		// Two-finger tap: dispatch right-click saat semua jari terangkat
		if (twoFingerTapped) {
			if (activePointers.size === 0) {
				twoFingerTapped = false;
				pointerDown = false;
				cancelTimer();
				// Right-click di posisi midpoint atau posisi terakhir
				dispatchRightClick(e.clientX, e.clientY);
			}
			return;
		}

		if (!pointerDown) return;
		pointerDown = false;

		if (phase === 'aiming_start') {
			// Release setelah aim pertama → mousedown di crosshair
			const ch = getCrosshairViewport();
			dispatchToCanvas('mousedown', ch.x, ch.y);
			phase = 'holding';
			startHoldingTimeout();
		} else if (phase === 'aiming_end') {
			// Release setelah aim kedua → mouseup di crosshair
			const ch = getCrosshairViewport();
			dispatchToCanvas('mouseup', ch.x, ch.y);
			phase = 'idle';
		} else if (phase === 'idle') {
			// Short tap — detect single / double / triple
			cancelTimer();
			const x = e.clientX;
			const y = e.clientY;
			const now = Date.now();

			if (now - lastTapTime < DOUBLE_TAP_MS) {
				tapCount++;
			} else {
				tapCount = 1;
			}
			lastTapTime = now;
			cancelSingleTapTimer();

			if (tapCount === 2) {
				// Double tap → dblclick (edit komponen di CircuitJS)
				dispatchToCanvas('dblclick', x, y);
				focusIfEditable(x, y);
				tapCount = 0;
			} else if (tapCount >= 3) {
				// Triple tap → right click (context menu)
				dispatchRightClick(x, y);
				tapCount = 0;
			} else {
				// Single tap — tunggu DOUBLE_TAP_MS sebelum dispatch
				singleTapTimer = setTimeout(() => {
					dispatchToCanvas('mousedown', x, y);
					setTimeout(() => {
						dispatchToCanvas('mouseup', x, y);
						dispatchToCanvas('click', x, y);
						focusIfEditable(x, y);
					}, 50);
					tapCount = 0;
				}, DOUBLE_TAP_MS);
			}
		} else if (phase === 'holding') {
			// Short tap saat holding → mouseup di posisi tap
			cancelTimer();
			cancelHoldingTimer();
			dispatchToCanvas('mouseup', e.clientX, e.clientY);
			phase = 'idle';
		}

		cancelTimer();
	}

	function handlePointerCancel(e: PointerEvent) {
		if (e.pointerType !== 'touch') return;
		activePointers.delete(e.pointerId);
		twoFingerTapped = false;
		pointerDown = false;
		cancelTimer();
		cancelSingleTapTimer();

		if (phase === 'aiming_start') {
			phase = 'idle';
		} else if (phase === 'aiming_end') {
			// Cancel saat aiming release → lepas click
			dispatchToCanvas('mouseup', currentPointerX, currentPointerY);
			phase = 'idle';
		} else if (phase === 'holding') {
			cancelHoldingTimer();
			dispatchToCanvas('mouseup', currentPointerX, currentPointerY);
			phase = 'idle';
		}
	}

	function handleContextMenu(e: Event) {
		e.preventDefault();
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="crosshair-overlay"
	class:touch-active={isTouchDevice}
	bind:this={overlayEl}
	onpointerdown={handlePointerDown}
	onpointermove={handlePointerMove}
	onpointerup={handlePointerUp}
	onpointercancel={handlePointerCancel}
	oncontextmenu={handleContextMenu}
>
</div>

{#if showCrosshair}
	<svg
		class="crosshair-cursor"
		style="transform: translate({crosshairX}px, {crosshairY}px)"
		width="48"
		height="48"
		viewBox="0 0 48 48"
	>
		<circle cx="24" cy="24" r="18" fill="none" stroke="rgba(220, 53, 69, 0.8)" stroke-width="2" />
		<line x1="24" y1="2" x2="24" y2="14" stroke="rgba(220, 53, 69, 0.8)" stroke-width="1.5" />
		<line x1="24" y1="34" x2="24" y2="46" stroke="rgba(220, 53, 69, 0.8)" stroke-width="1.5" />
		<line x1="2" y1="24" x2="14" y2="24" stroke="rgba(220, 53, 69, 0.8)" stroke-width="1.5" />
		<line x1="34" y1="24" x2="46" y2="24" stroke="rgba(220, 53, 69, 0.8)" stroke-width="1.5" />
		<circle cx="24" cy="24" r="2" fill="rgba(220, 53, 69, 0.9)" />
	</svg>
{/if}

<style>
	.crosshair-overlay {
		position: absolute;
		inset: 0;
		z-index: 5;
		pointer-events: none;
		touch-action: none;
	}

	.crosshair-overlay.touch-active {
		pointer-events: auto;
	}

	.crosshair-cursor {
		position: absolute;
		top: 0;
		left: 0;
		width: 48px;
		height: 48px;
		margin-left: -24px;
		margin-top: -24px;
		pointer-events: none;
		z-index: 6;
		will-change: transform;
		filter: drop-shadow(0 0 2px rgba(0, 0, 0, 0.5));
		animation: crosshair-in 0.15s ease-out;
	}

	@keyframes crosshair-in {
		from {
			transform: scale(0.3);
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}
</style>
