<script lang="ts">
	import CrosshairOverlay from './CrosshairOverlay.svelte';
	import type { CircuitJSApi } from '$lib/types/circuitjs';

	interface Props {
		initialCircuit?: string;
		storageKey?: string;
		onready?: (api: CircuitJSApi) => void;
	}

	let { initialCircuit = '', storageKey, onready }: Props = $props();

	let iframe = $state<HTMLIFrameElement>(null!);
	let ready = $state(false);
	let simApi = $state<CircuitJSApi | null>(null);
	let saving = $state(false);
	let saveTimeout: ReturnType<typeof setTimeout>;
	let autoSaveInterval: ReturnType<typeof setInterval>;
	let lastLoadedCircuit = $state('');

	function saveToStorage(text: string) {
		if (!storageKey) return;
		saving = true;
		clearTimeout(saveTimeout);
		saveTimeout = setTimeout(() => {
			localStorage.setItem(storageKey, text);
			saving = false;
		}, 1000);
	}

	export function loadCircuitToSim(text: string) {
		if (!simApi) return;
		const trimmed = text?.trim();
		if (!trimmed) return;

		try {
			simApi.importCircuit(trimmed, false);
			simApi.setSimRunning(true);
			simApi.updateCircuit();
		} catch (err) {
			console.error("CircuitEditor: Error loading circuit:", err);
		}
	}

	function initSimulator(apiFromArg?: any) {
		const win = iframe?.contentWindow as any;
		
		// Priority: Object from callback argument, then from window object
		simApi = apiFromArg || (win ? win.CircuitJS1 : null);

		if (simApi) {
			ready = true;

			// Load initial circuit or draft
			let toLoad = initialCircuit;
			if (storageKey) {
				const saved = localStorage.getItem(storageKey);
				if (saved) {
					toLoad = saved;
				}
			}

			if (toLoad) {
				lastLoadedCircuit = toLoad;
				// Give it a bit more time to be completely ready for interaction
				setTimeout(() => {
					loadCircuitToSim(toLoad);
				}, 1000);
			}

			if (onready) onready(simApi);
		} else {
			console.error("CircuitEditor: Could not find CircuitJS1 API object");
		}
	}

	function handleIframeLoad() {
		if (iframe && iframe.contentWindow) {
			const win = iframe.contentWindow as any;
			
			// Define the callback that CircuitJS1 calls internally
			win.oncircuitjsloaded = (api: any) => {
				initSimulator(api);
			};
			
			// Fallback: if already loaded or callback doesn't fire
			setTimeout(() => {
				if (!ready) {
					initSimulator();
				}
			}, 3000);
		}
	}

	// Re-apply if initialCircuit prop changes
	$effect(() => {
		if (simApi && ready && initialCircuit && initialCircuit !== lastLoadedCircuit) {
			lastLoadedCircuit = initialCircuit;
			const saved = storageKey ? localStorage.getItem(storageKey) : null;
			if (!saved) {
				loadCircuitToSim(initialCircuit);
			}
		}
	});

	// Load draft reactively when storageKey is set (fixes delayed auth problem)
	$effect(() => {
		if (storageKey && storageKey !== lastStorageKey) {
			lastStorageKey = storageKey;
			if (!ready || !simApi) return;

			const saved = localStorage.getItem(storageKey);
			if (saved) {
				loadCircuitToSim(saved);
			} else if (initialCircuit) {
				loadCircuitToSim(initialCircuit);
			}
		}
	});

	// Reactively poll to sync auto-save, ensures it gets setup even if storageKey is delayed
	$effect(() => {
		if (simApi && ready && storageKey) {
			const interval = setInterval(() => {
				const currentText = simApi.exportCircuit();
				const saved = localStorage.getItem(storageKey);
				if (currentText && currentText !== saved && currentText.trim().length > 10) {
					saveToStorage(currentText);
				}
			}, 5000);
			return () => clearInterval(interval);
		}
	});

	// Cleanup timers on destroy
	$effect(() => {
		return () => {
			clearInterval(autoSaveInterval);
			clearTimeout(saveTimeout);
		};
	});

	export function getCircuitText(): string {
		if (!simApi) return '';
		return simApi.exportCircuit();
	}

	export function setCircuitText(text: string) {
		loadCircuitToSim(text);
	}

	export function getApi(): CircuitJSApi | null {
		return simApi;
	}
</script>

<div class="circuit-container">
	<div class="circuit-wrapper">
		{#if !ready}
			<div class="editor-loading">Memuat Simulator Rangkaian...</div>
		{/if}
		
		<iframe
			bind:this={iframe}
			src="/circuitjs1/circuitjs.html"
			title="Circuit Simulator"
			onload={handleIframeLoad}
			class:visible={ready}
		></iframe>

		{#if ready}
			<CrosshairOverlay {iframe} />
		{/if}

		{#if storageKey && ready}
			<div class="storage-indicator" title={saving ? "Menyimpan draf..." : "Draf tersimpan di browser"}>
				<span class="indicator-icon" class:saving>
					{saving ? '●' : '☁'}
				</span>
				<span class="indicator-text">Auto-save</span>
			</div>
		{/if}
	</div>
</div>

<style>
	.circuit-container {
		display: flex;
		flex-direction: column;
		gap: 8px;
		width: 100%;
	}
	.circuit-wrapper {
		position: relative;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
		width: 100%;
		height: 550px;
		background: #fff;
	}
	iframe {
		width: 100%;
		height: 100%;
		border: none;
		opacity: 0;
		transition: opacity 0.3s;
	}
	iframe.visible {
		opacity: 1;
	}
	.editor-loading {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--color-text-muted);
		font-size: 0.85rem;
		background: var(--color-bg-secondary);
		z-index: 1;
	}
	.storage-indicator {
		position: absolute;
		bottom: 8px;
		right: 12px;
		z-index: 10;
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 4px 8px;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: 12px;
		font-size: 0.7rem;
		color: var(--color-text-muted);
		pointer-events: none;
		opacity: 0.8;
		box-shadow: 0 2px 4px rgba(0,0,0,0.1);
	}
	.indicator-icon {
		line-height: 1;
		font-size: 0.8rem;
		color: var(--color-success);
	}
	.indicator-icon.saving {
		color: var(--color-primary);
		animation: pulse 1s infinite;
	}
	@keyframes pulse {
		0% { opacity: 1; }
		50% { opacity: 0.4; }
		100% { opacity: 1; }
	}
	.indicator-text {
		font-weight: 500;
	}

	@media (max-width: 768px) {
		.circuit-wrapper {
			height: 450px;
		}
	}
</style>
