import { VelxioBridge } from '$services/velxio-bridge';
import type { LessonContent } from '$types/lesson';

export function getVelxioState(velxioIframe: HTMLIFrameElement | null): { code: string; circuit: string } | null {
	if (!velxioIframe) return null;
	try {
		const win = velxioIframe.contentWindow as any;
		if (!win) return null;
		
		const editorStore = win.__VELXIO_EDITOR_STORE__?.getState?.();
		const simStore = win.__VELXIO_SIMULATOR_STORE__?.getState?.();
		
		if (!editorStore || !simStore) return null;
		
		// Extract code
		const code = (editorStore.files as any[] || []).map((f: any) => f.content).join('\n');
		
		// Extract circuit state (Diagram format compatible with elemes:load_circuit)
		const circuit = {
			board: simStore.activeBoardId,
			components: (simStore.components as any[] || []).map((c: any) => ({
				type: c.metadataId,
				id: c.id,
				x: c.x,
				y: c.y,
				rotation: c.properties?.rotation || 0,
				props: { ...c.properties }
			})),
			wires: simStore.wires || []
		};
		
		return {
			code,
			circuit: JSON.stringify(circuit)
		};
	} catch {
		return null;
	}
}

export function initVelxioBridge(
	iframe: HTMLIFrameElement,
	data: LessonContent | null,
	arduinoCircuitKey: string,
	arduinoCodeKey: string,
	onReady: (bridge: VelxioBridge) => void,
	onSubmit: () => void
) {
	let settled = false;
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
			const timeout = data?.evaluation_config?.timeout_ms ?? 5000;
			setTimeout(() => onSubmit(), timeout);
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

	setTimeout(() => {
		clearInterval(pollReady);
		if (settled) return;
		settled = true;
		window.removeEventListener('message', onMessage);
	}, 30_000);
}
