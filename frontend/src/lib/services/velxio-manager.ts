import { VelxioBridge } from './velxio-bridge';
import type { LessonContent } from '../types/lesson';

const BOARD_KIND_MAP: Record<string, string> = {
	'arduino-uno': 'arduino:avr:uno',
	'arduino-nano': 'arduino:avr:nano',
	'arduino-mega': 'arduino:avr:mega',
	'raspberry-pi-pico': 'rp2040:rp2040:rp2040',
	'rp2040-pico': 'rp2040:rp2040:rp2040',
	'esp32': 'esp32:esp32:esp32'
};

export function getVelxioState(velxioIframe: HTMLIFrameElement | null): { code: string; circuit: string } | null {
	if (!velxioIframe) return null;
	try {
		const win = velxioIframe.contentWindow as any;
		if (!win) return null;

		const editorStore = win.__VELXIO_EDITOR_STORE__?.getState?.();
		const simStore = win.__VELXIO_SIMULATOR_STORE__?.getState?.();

		if (!editorStore || !simStore) return null;

		// Extract active board and determine FQBN / board string
		const activeBoard = simStore.boards?.find((b: any) => b.id === simStore.activeBoardId) ?? simStore.boards?.[0];
		const boardKind = activeBoard?.boardKind || simStore.activeBoardId || 'arduino-uno';
		const board = BOARD_KIND_MAP[boardKind] || (typeof boardKind === 'string' && boardKind.includes(':') ? boardKind : 'arduino:avr:uno');

		// Extract code from active board file group or fallback to primary .ino / files
		const activeGroupId = activeBoard?.activeFileGroupId ?? '';
		const activeFiles = (editorStore.fileGroups?.[activeGroupId]?.length
			? editorStore.fileGroups[activeGroupId]
			: editorStore.files) ?? editorStore.files ?? [];

		const code = activeFiles.find((f: any) => f.name?.endsWith('.ino'))?.content
			?? activeFiles[0]?.content
			?? (editorStore.files as any[] || []).map((f: any) => f.content).join('\n')
			?? '';

		// Extract circuit state (Diagram format compatible with elemes:load_circuit)
		const components = (simStore.components as any[] || []).map((c: any) => ({
			type: c.metadataId,
			id: c.id,
			x: Math.round((c.x || 0) * 10) / 10,
			y: Math.round((c.y || 0) * 10) / 10,
			rotation: c.properties?.rotation || 0,
			props: { ...c.properties }
		}));

		const wires = (simStore.wires as any[] || [])
			.filter((w: any) => w && w.start && w.end)
			.map((w: any) => ({
				start: {
					componentId: w.start?.componentId,
					pinName: w.start?.pinName
				},
				end: {
					componentId: w.end?.componentId,
					pinName: w.end?.pinName
				}
			}));

		const circuit = {
			board,
			components,
			wires
		};

		return {
			code,
			circuit: JSON.stringify(circuit, null, 2)
		};
	} catch (e) {
		console.error('[velxio-manager] Error getting Velxio state:', e);
		return null;
	}
}

export function initVelxioBridge(
	iframe: HTMLIFrameElement,
	data: LessonContent | null,
	arduinoCircuitKey: string,
	arduinoCodeKey: string,
	onReady: (bridge: VelxioBridge) => void,
	onSubmit: () => void,
	onCountdown?: (msRemaining: number) => void
): () => void {
	let settled = false;
	let countdownInterval: ReturnType<typeof setInterval> | null = null;

	const onMessage = (e: MessageEvent) => {
		const type = e.data?.type;
		if (!type) return;

		if (!settled && type === 'velxio:ready') {
			settled = true;
			const velxioBridge = new VelxioBridge(iframe);
			onReady(velxioBridge);
			
			if (!data) return;
			velxioBridge.setEmbedMode({
				hideAuth: true,
				hideComponentPicker: true,
				lockComponents: true
			});
			
			// Priority: Restore from localStorage if available, otherwise use data from backend
			const savedCircuit = localStorage.getItem(arduinoCircuitKey);
			const savedCode = localStorage.getItem(arduinoCodeKey);

			if (savedCircuit) {
				console.log('[Velxio Bridge] Restoring circuit from draft');
				velxioBridge.loadCircuit(savedCircuit);
			} else if (data.velxio_circuit) {
				velxioBridge.loadCircuit(data.velxio_circuit);
			}

			if (savedCode) {
				console.log('[Velxio Bridge] Restoring code from draft');
				velxioBridge.loadCode([{ name: 'sketch.ino', content: savedCode }]);
			} else if (data.initial_code_arduino) {
				velxioBridge.loadCode([{ name: 'sketch.ino', content: data.initial_code_arduino }]);
			}
		}

		if (type === 'velxio:compile_result' && e.data.success) {
			const timeout = data?.evaluation_config?.timeout_ms ?? 8000;
			if (countdownInterval) clearInterval(countdownInterval);
			let remaining = timeout;
			if (onCountdown) {
				onCountdown(remaining);
				countdownInterval = setInterval(() => {
					remaining -= 1000;
					if (remaining <= 0) {
						if (countdownInterval) {
							clearInterval(countdownInterval);
							countdownInterval = null;
						}
					} else {
						onCountdown(remaining);
					}
				}, 1000);
			}
			setTimeout(() => {
				if (countdownInterval) {
					clearInterval(countdownInterval);
					countdownInterval = null;
				}
				onSubmit();
			}, timeout);
		}
	};
	window.addEventListener('message', onMessage);

	// Fallback: if PostMessage bridge never connects, try direct iframe access (same-origin)
	const pollReady = setInterval(() => {
		if (settled) { clearInterval(pollReady); return; }
		try {
			const win = iframe.contentWindow as any;
			if (!win || !win.document) return;
			const root = win.document.getElementById('root');
			if (!root || !root.children.length) return;

			settled = true;
			clearInterval(pollReady);
			onReady(new VelxioBridge(iframe)); // Just provide dummy or initialize

			if (data) {
				win.postMessage({
					type: 'elemes:set_embed_mode',
					hideAuth: true,
					hideComponentPicker: true,
					lockComponents: true
				}, '*');
				
				const savedCircuit = localStorage.getItem(arduinoCircuitKey);
				const savedCode = localStorage.getItem(arduinoCodeKey);

				if (savedCircuit) {
					try {
						console.log('[Velxio Fallback] Restoring circuit from draft');
						const circuitData = JSON.parse(savedCircuit);
						win.postMessage({ type: 'elemes:load_circuit', ...circuitData }, '*');
					} catch {}
				} else if (data.velxio_circuit) {
					try {
						const circuitData = JSON.parse(data.velxio_circuit);
						win.postMessage({ type: 'elemes:load_circuit', ...circuitData }, '*');
					} catch {}
				}

				if (savedCode) {
					console.log('[Velxio Fallback] Restoring code from draft');
					win.postMessage({ type: 'elemes:load_code', files: [{ name: 'sketch.ino', content: savedCode }] }, '*');
				} else if (data.initial_code_arduino) {
					win.postMessage({ type: 'elemes:load_code', files: [{ name: 'sketch.ino', content: data.initial_code_arduino }] }, '*');
				}
			}
		} catch { /* cross-origin or not ready yet */ }
	}, 1000);

	const cleanup = () => {
		window.removeEventListener('message', onMessage);
		clearInterval(pollReady);
		if (countdownInterval) {
			clearInterval(countdownInterval);
			countdownInterval = null;
		}
	};

	setTimeout(() => {
		cleanup();
	}, 30_000);

	return cleanup;
}
