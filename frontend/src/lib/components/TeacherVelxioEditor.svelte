<script lang="ts">
	import { onMount } from 'svelte';
	import { getVelxioState } from '$services/velxio-manager';

	let {
		initialCode = '',
		initialCircuit = '',
		onSave
	}: {
		initialCode?: string;
		initialCircuit?: string;
		onSave?: (state: { code: string; circuit: string }) => void;
	} = $props();

	let iframeRef = $state<HTMLIFrameElement | null>(null);
	let isReady = $state(false);
	let saveFeedback = $state<string | null>(null);
	let feedbackTimeout: ReturnType<typeof setTimeout> | null = null;

	const velxioSrc = '/velxio/editor?embed=true&desktopLayout=true';

	export function getCurrentState(): { code: string; circuit: string } | null {
		return getVelxioState(iframeRef);
	}

	export function loadStateToSimulator(code: string, circuit: string) {
		if (!iframeRef?.contentWindow) return;
		const win = iframeRef.contentWindow;

		// Teacher mode: embed mode with components and editor fully editable
		win.postMessage(
			{
				type: 'elemes:set_embed_mode',
				hideAuth: true,
				hideComponentPicker: false,
				lockComponents: false
			},
			'*'
		);

		if (circuit) {
			try {
				const circuitData = typeof circuit === 'string' ? JSON.parse(circuit) : circuit;
				win.postMessage({ type: 'elemes:load_circuit', ...circuitData }, '*');
			} catch (err) {
				console.error('[TeacherVelxioEditor] Error parsing circuit JSON:', err);
			}
		}

		if (code) {
			win.postMessage(
				{
					type: 'elemes:load_code',
					files: [{ name: 'sketch.ino', content: code }]
				},
				'*'
			);
		}
	}

	export function reloadFromDocument() {
		loadStateToSimulator(initialCode, initialCircuit);
		showFeedback('Dimuat ulang dari dokumen');
	}

	function handleSave() {
		const state = getCurrentState();
		if (!state) {
			showFeedback('Gagal membaca state simulator');
			return;
		}

		if (onSave) {
			onSave(state);
		}
		showFeedback('Tersimpan ke dokumen!');
	}

	function showFeedback(msg: string) {
		saveFeedback = msg;
		if (feedbackTimeout) clearTimeout(feedbackTimeout);
		feedbackTimeout = setTimeout(() => {
			saveFeedback = null;
		}, 2500);
	}

	function handleIframeLoad() {
		checkIframeReady();
	}

	function checkIframeReady() {
		try {
			const win = iframeRef?.contentWindow as any;
			if (!win || !win.document) return;
			const root = win.document.getElementById('root');
			if (root && root.children.length > 0) {
				if (!isReady) {
					isReady = true;
					loadStateToSimulator(initialCode, initialCircuit);
				}
			}
		} catch {
			// Cross-origin fallback or not yet loaded
		}
	}

	onMount(() => {
		const onMessage = (e: MessageEvent) => {
			if (e.data?.type === 'velxio:ready') {
				isReady = true;
				loadStateToSimulator(initialCode, initialCircuit);
			}
		};

		window.addEventListener('message', onMessage);

		const poll = setInterval(() => {
			if (isReady) {
				clearInterval(poll);
				return;
			}
			checkIframeReady();
		}, 600);

		const pollTimeout = setTimeout(() => {
			clearInterval(poll);
		}, 15000);

		return () => {
			window.removeEventListener('message', onMessage);
			clearInterval(poll);
			clearTimeout(pollTimeout);
			if (feedbackTimeout) clearTimeout(feedbackTimeout);
		};
	});
</script>

<div class="teacher-velxio-container">
	<div class="teacher-velxio-toolbar">
		<div class="toolbar-status">
			<span class="status-dot" class:ready={isReady}></span>
			<span class="status-text">
				{isReady ? 'Simulator Siap (Mode Lengkap)' : 'Menghubungkan Simulator...'}
			</span>
			{#if saveFeedback}
				<span class="save-feedback">{saveFeedback}</span>
			{/if}
		</div>

		<div class="toolbar-actions">
			<button
				type="button"
				class="toolbar-btn btn-reload"
				onclick={reloadFromDocument}
				title="Muat ulang rangkaian & kode dari dokumen markdown"
				disabled={!isReady}
			>
				<svg class="icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M23 4v6h-6"></path>
					<path d="M1 20v-6h6"></path>
					<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
				</svg>
				<span>Muat Ulang</span>
			</button>

			<button
				type="button"
				class="toolbar-btn btn-save"
				onclick={handleSave}
				title="Simpan rangkaian dan kode saat ini langsung ke dokumen markdown"
				disabled={!isReady}
			>
				<svg class="icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
					<polyline points="17 21 17 13 7 13 7 21"></polyline>
					<polyline points="7 3 7 8 15 8"></polyline>
				</svg>
				<span>Simpan ke Dokumen</span>
			</button>
		</div>
	</div>

	<iframe
		bind:this={iframeRef}
		class="velxio-iframe"
		src={velxioSrc}
		title="Velxio Arduino Simulator & Editor"
		onload={handleIframeLoad}
		allow="cross-origin-isolated; fullscreen"
		allowfullscreen
	></iframe>
</div>

<style>
	.teacher-velxio-container {
		display: flex;
		flex-direction: column;
		width: 100%;
		height: 100%;
		overflow: hidden;
		background: var(--color-bg, #ffffff);
	}

	.teacher-velxio-toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px 14px;
		background: var(--color-bg-secondary, #f8f9fa);
		border-bottom: 1px solid var(--color-border, #dee2e6);
		font-size: 0.82rem;
		min-height: 40px;
		gap: 12px;
		flex-wrap: wrap;
	}

	.toolbar-status {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.status-dot {
		width: 9px;
		height: 9px;
		border-radius: 50%;
		background: #ffc107;
		display: inline-block;
		transition: background-color 0.2s ease;
	}

	.status-dot.ready {
		background: #198754;
		box-shadow: 0 0 6px rgba(25, 135, 84, 0.4);
	}

	.status-text {
		color: var(--color-text-muted, #555555);
		font-weight: 500;
	}

	.save-feedback {
		margin-left: 8px;
		padding: 2px 8px;
		background: rgba(25, 135, 84, 0.12);
		color: #198754;
		border-radius: 4px;
		font-size: 0.78rem;
		font-weight: 600;
		animation: fadeIn 0.2s ease;
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
			transform: translateY(-2px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.toolbar-actions {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.toolbar-btn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 4px 10px;
		border-radius: 6px;
		font-size: 0.8rem;
		font-weight: 500;
		cursor: pointer;
		border: 1px solid var(--color-border, #dee2e6);
		background: var(--color-bg, #ffffff);
		color: var(--color-text, #111111);
		transition: all 0.15s ease;
	}

	.toolbar-btn:hover:not(:disabled) {
		background: var(--color-bg-secondary, #f0f0f0);
	}

	.toolbar-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-save {
		background: var(--color-primary, #0d6efd);
		color: #ffffff;
		border-color: var(--color-primary, #0d6efd);
	}

	.btn-save:hover:not(:disabled) {
		background: var(--color-primary-dark, #0a58ca);
		border-color: var(--color-primary-dark, #0a58ca);
	}

	.icon {
		flex-shrink: 0;
	}

	.velxio-iframe {
		flex: 1;
		width: 100%;
		height: 100%;
		border: none;
		display: block;
	}
</style>
