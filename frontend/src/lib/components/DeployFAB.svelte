<script lang="ts">
	import { onDestroy } from 'svelte';
	import { BLEHardwareDeployer } from '$services/ble-deployer';
	import {
		SUPPORTED_BAUD_RATES,
		DEFAULT_BAUD_RATE,
		type DeployState,
		type DeployProgress
	} from '$types/deployer';

	let {
		velxioIframe,
		onPushSerial,
		onSerialStart,
		onStopSerial
	}: {
		velxioIframe: HTMLIFrameElement | null;
		onPushSerial: (text: string) => void;
		onSerialStart: () => void;
		onStopSerial: () => void;
	} = $props();

	let deployer = $state<BLEHardwareDeployer | null>(null);
	let isPaired = $state(false);
	let cancelled = $state(false);
	let deployState = $state<DeployState>('idle');
	let deployMessage = $state('');
	let totalChunks = $state(0);
	let completedChunks = $state(0);
	let progressPercent = $derived(totalChunks > 0 ? Math.round((completedChunks / totalChunks) * 100) : 0);
	let bleSupported = $state(true);
	let errorMessage = $state('');
	let panelOpen = $state(false);
	let pendingHex = $state<string | null>(null);
	let serialActive = $state(false);
	let serialPendingBaud: number | null = null;
	let baudRate = $state(DEFAULT_BAUD_RATE);

	export function setHex(hex: string | null) {
		pendingHex = hex;
	}

	function initDeployer() {
		deployer = new BLEHardwareDeployer();
		bleSupported = deployer.checkSupport();
		if (!bleSupported) {
			deployState = 'error';
			errorMessage = 'Web Bluetooth tidak didukung. Gunakan Chrome Android.';
		}
		deployer.onDisconnected(() => {
			deployState = 'error';
			errorMessage = 'Koneksi BLE terputus.';
			serialActive = false;
		});
	}

	function resetState() {
		deployState = 'idle';
		deployMessage = '';
		totalChunks = 0;
		completedChunks = 0;
		errorMessage = '';
		serialActive = false;
		isPaired = false;
	}

	function handlePair() {
		try {
			deployState = 'pairing';
			deployMessage = 'Pilih perangkat Velxio Deployer...';
			deployer!.pair().then(() => {
				isPaired = true;
				deployState = 'idle';
				deployMessage = 'Perangkat terhubung';
			}).catch((err: any) => {
				deployState = 'error';
				errorMessage = err.message || 'Gagal pairing';
			});
		} catch (err: any) {
			deployState = 'error';
			errorMessage = err.message || 'Gagal pairing';
		}
	}

	async function handleDeploy() {
		if (!deployer || !isPaired) {
			errorMessage = 'Hubungkan perangkat dulu';
			return;
		}
		if (!pendingHex) {
			errorMessage = 'Tidak ada HEX untuk di-deploy. Compile dulu di editor.';
			return;
		}

		serialActive = false;

		cancelled = false;
		try {
			deployState = 'transferring';
			deployMessage = 'Mengirim data ke Velxio Deployer...';

			const onProgress = (p: DeployProgress) => {
				deployState = p.state;
				deployMessage = p.message;
				totalChunks = p.totalChunks;
				completedChunks = p.completedChunks;
			};

			await deployer.deployHex(pendingHex, onProgress);

			if (cancelled) return;

			deployState = 'success';
			deployMessage = 'Upload berhasil! LED Hijau.';
			handleOpenSerial();
		} catch (err: any) {
			if (cancelled) return;
			deployState = 'error';
			errorMessage = err.message || 'Deploy gagal';
		}
	}

	async function handleOpenSerial() {
		if (!deployer || !isPaired) return;

		try {
			// Auto-reset Arduino before opening serial monitor
			console.log('[DEPLOY-FAB] Auto-resetting Arduino before serial monitor...');
			await deployer.resetArduino();

			if (serialPendingBaud !== null) {
				await deployer.setBaudRate(serialPendingBaud);
				baudRate = serialPendingBaud;
				serialPendingBaud = null;
			}
			serialActive = true;
			onSerialStart();
			await deployer.startSerialMonitor((text) => {
				onPushSerial(text);
			});
		} catch (err: any) {
			serialActive = false;
			errorMessage = 'Gagal membuka Serial Monitor: ' + err.message;
		}
	}

	function handleCloseSerial() {
		deployer?.stopSerialMonitor();
		serialActive = false;
		onStopSerial();
	}

	async function handleBaudChange(e: Event) {
		const newBaud = parseInt((e.target as HTMLSelectElement).value);
		if (serialActive && deployer) {
			try {
				await deployer.setBaudRate(newBaud);
				baudRate = newBaud;
			} catch (err: any) {
				errorMessage = 'Gagal mengubah baud: ' + err.message;
			}
		} else {
			serialPendingBaud = newBaud;
			baudRate = newBaud;
		}
	}

	function handleDisconnect() {
		deployer?.disconnect();
		resetState();
	}

	function handleRetry() {
		resetState();
		pendingHex = null;
	}

	function handleCancel() {
		cancelled = true;
		deployState = 'idle';
		deployMessage = '';
		errorMessage = 'Deploy dibatalkan';
	}

	function togglePanel() {
		panelOpen = !panelOpen;
	}

	function closePanel() {
		panelOpen = false;
	}

	initDeployer();

	onDestroy(() => {
		if (isPaired) {
			deployer?.disconnect();
		}
	});
</script>

<!-- FAB trigger button -->
<button
	class="fab-trigger"
	class:panel-open={panelOpen}
	onclick={togglePanel}
	aria-label={panelOpen ? 'Tutup panel deploy' : 'Buka panel deploy'}
	title="BLE Deployer"
>
	<svg class="fab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
		<path d="M6 9a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9z"/>
		<path d="M12 15v3"/>
		<path d="M8 21h8"/>
		<path d="M12 3L9 6h6l-3-3z"/>
	</svg>
</button>

<!-- Deploy panel -->
{#if panelOpen}
	<div class="fab-panel-backdrop" onclick={closePanel}></div>
	<div class="fab-panel">
		<div class="fab-panel-header">
			<h3 class="panel-title">BLE Deployer</h3>
			<div class="panel-status" class:connected={isPaired}>
				<span class="status-dot"></span>
				{isPaired ? 'Terhubung' : 'Terputus'}
			</div>
			<button class="panel-close" onclick={closePanel} aria-label="Tutup">&times;</button>
		</div>

		<div class="panel-body">
			<!-- Connection -->
			<div class="panel-section">
				{#if !isPaired}
					<button class="btn btn-primary btn-full" onclick={handlePair} disabled={deployState === 'pairing'}>
						{deployState === 'pairing' ? 'Menghubungkan...' : 'Pair Device'}
					</button>
				{:else}
					<div class="btn-row">
						<button class="btn btn-success btn-full" onclick={handleDeploy}
							disabled={deployState === 'transferring' || deployState === 'flashing' || !pendingHex}>
							{deployState === 'transferring' ? 'Mengirim...' : deployState === 'flashing' ? 'Flashing...' : 'Deploy'}
						</button>
					</div>
					<div class="btn-row">
						{#if deployState === 'transferring' || deployState === 'flashing'}
							<button class="btn btn-outline btn-sm" onclick={handleCancel}>Batal</button>
						{:else}
							<button class="btn btn-outline btn-sm" onclick={handleDisconnect}>Putuskan</button>
						{/if}
					</div>
				{/if}
			</div>

			<!-- Hex status -->
			<div class="hex-status">
				<span class="hex-label">HEX:</span>
				<span class="hex-value" class:hex-loaded={!!pendingHex}>
					{pendingHex ? `${Math.round(pendingHex.length / 1024)} KB siap` : 'Belum ada (compile di editor)'}
				</span>
			</div>

			<!-- Progress -->
			{#if deployState !== 'idle' && deployState !== 'error'}
				<div class="panel-section">
					<div class="progress-message">{deployMessage}</div>
					{#if totalChunks > 0}
						<div class="progress-bar-container">
							<div class="progress-bar-fill" style="width: {progressPercent}%"></div>
						</div>
						<div class="progress-text">
							Chunk {completedChunks}/{totalChunks} ({progressPercent}%)
						</div>
					{/if}
				</div>
			{/if}

			<!-- Serial controls -->
			{#if isPaired}
				<div class="panel-section">
					<div class="serial-header">
						<span>Serial Monitor</span>
						<div class="serial-controls">
							<select class="baud-select" bind:value={baudRate} onchange={handleBaudChange}>
								{#each SUPPORTED_BAUD_RATES as b}
									<option value={b}>{b}</option>
								{/each}
							</select>
							<span class="baud-label">baud</span>
							<button class="btn btn-sm btn-outline" onclick={serialActive ? handleCloseSerial : handleOpenSerial}>
								{serialActive ? 'Tutup' : 'Mulai'}
							</button>
						</div>
					</div>
					{#if !serialActive}
						<div class="serial-hint">Serial data akan dikirim ke editor ({baudRate} baud).</div>
					{:else}
						<div class="serial-active-hint">Serial monitor aktif — data dikirim ke editor.</div>
					{/if}
				</div>
			{/if}

			<!-- Info / Cancel message -->
			{#if deployState === 'idle' && errorMessage}
				<div class="panel-info">
					<div class="info-message">{errorMessage}</div>
				</div>
			{/if}

			<!-- Error -->
			{#if deployState === 'error'}
				<div class="panel-error">
					<div class="error-icon">&#9888;</div>
					<div class="error-message">{errorMessage}</div>
					<button class="btn btn-outline btn-sm" onclick={handleRetry}>Coba Lagi</button>
				</div>
			{/if}

			{#if !bleSupported && deployState !== 'error'}
				<div class="panel-error">
					<div class="error-message">Web Bluetooth tidak didukung di browser ini. Gunakan Chrome Android.</div>
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	/* ─── FAB Button ─── */
	.fab-trigger {
		position: fixed;
		bottom: 20px;
		right: 20px;
		width: 56px;
		height: 56px;
		border-radius: 50%;
		background: linear-gradient(135deg, #3b82f6, #1d4ed8);
		color: #fff;
		border: none;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		box-shadow: 0 4px 16px rgba(59, 130, 246, 0.4);
		z-index: 1000;
		transition: transform 0.2s ease, box-shadow 0.2s ease;
	}

	.fab-trigger:hover {
		transform: scale(1.08);
		box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5);
	}

	.fab-trigger:active {
		transform: scale(0.96);
	}

	.fab-trigger.panel-open {
		background: linear-gradient(135deg, #ef4444, #dc2626);
		box-shadow: 0 4px 16px rgba(239, 68, 68, 0.4);
	}

	.fab-icon {
		width: 26px;
		height: 26px;
	}

	/* ─── Panel Backdrop ─── */
	.fab-panel-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.3);
		z-index: 998;
	}

	/* ─── Panel ─── */
	.fab-panel {
		position: fixed;
		bottom: 84px;
		right: 20px;
		width: 320px;
		max-height: 80vh;
		background: #1e1e2e;
		color: #e0e0e0;
		border-radius: 12px;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
		z-index: 999;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		animation: panelSlideUp 0.2s ease;
	}

	@keyframes panelSlideUp {
		from {
			opacity: 0;
			transform: translateY(12px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.fab-panel-header {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 12px 16px;
		background: #181825;
		border-bottom: 1px solid #313244;
	}

	.panel-title {
		margin: 0;
		font-size: 0.95rem;
		font-weight: 600;
		flex: 1;
	}

	.panel-status {
		display: flex;
		align-items: center;
		gap: 5px;
		font-size: 0.75rem;
		color: #888;
	}

	.panel-status.connected {
		color: #22c55e;
	}

	.status-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: #888;
	}

	.panel-status.connected .status-dot {
		background: #22c55e;
	}

	.panel-close {
		background: none;
		border: none;
		color: #888;
		font-size: 1.3rem;
		cursor: pointer;
		padding: 0 0 0 4px;
		line-height: 1;
	}

	.panel-close:hover {
		color: #fff;
	}

	.panel-body {
		padding: 12px 16px;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.panel-section {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	/* ─── Buttons ─── */
	.btn {
		font-size: 0.85rem;
		padding: 8px 14px;
		border-radius: 6px;
		cursor: pointer;
		transition: background 0.2s, opacity 0.2s;
		font-family: inherit;
	}

	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-full {
		width: 100%;
	}

	.btn-sm {
		padding: 5px 10px;
		font-size: 0.78rem;
	}

	.btn-primary {
		background: #3b82f6;
		color: #fff;
		border: none;
	}

	.btn-primary:hover:not(:disabled) {
		background: #2563eb;
	}

	.btn-success {
		background: #22c55e;
		color: #fff;
		border: none;
	}

	.btn-success:hover:not(:disabled) {
		background: #16a34a;
	}

	.btn-outline {
		background: transparent;
		color: #e0e0e0;
		border: 1px solid #555;
	}

	.btn-outline:hover:not(:disabled) {
		background: #313244;
	}

	.btn-row {
		margin-top: 2px;
	}

	/* ─── Hex Status ─── */
	.hex-status {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 0.78rem;
		padding: 6px 10px;
		background: #11111b;
		border-radius: 6px;
	}

	.hex-label {
		color: #888;
		font-weight: 600;
	}

	.hex-value {
		color: #888;
	}

	.hex-value.hex-loaded {
		color: #22c55e;
	}

	/* ─── Progress ─── */
	.progress-message {
		font-size: 0.8rem;
		color: #aaa;
	}

	.progress-bar-container {
		width: 100%;
		height: 8px;
		background: #313244;
		border-radius: 4px;
		overflow: hidden;
	}

	.progress-bar-fill {
		height: 100%;
		background: linear-gradient(90deg, #3b82f6, #22c55e);
		border-radius: 4px;
		transition: width 0.3s ease;
	}

	.progress-text {
		font-size: 0.72rem;
		color: #888;
		text-align: center;
	}

	.progress-spinner {
		width: 20px;
		height: 20px;
		border: 2px solid #313244;
		border-top-color: #3b82f6;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
		margin: 6px auto;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	/* ─── Serial ─── */
	.serial-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-size: 0.82rem;
		font-weight: 600;
	}

	.serial-controls {
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.baud-select {
		font-size: 0.75rem;
		padding: 2px 4px;
		border: 1px solid #555;
		border-radius: 4px;
		background: #313244;
		color: #e0e0e0;
	}

	.baud-label {
		font-size: 0.7rem;
		color: #888;
		margin-right: 4px;
	}

	.serial-hint,
	.serial-active-hint {
		font-size: 0.72rem;
		color: #6b7280;
		font-style: italic;
		padding: 2px 0;
	}

	.serial-active-hint {
		color: #22c55e;
	}

	/* ─── Info / Cancel message ─── */
	.panel-info {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
		padding: 8px 10px;
		background: #1a1a2e;
		border: 1px solid #3b3b6e;
		border-radius: 8px;
		text-align: center;
	}

	.info-message {
		font-size: 0.8rem;
		color: #93c5fd;
	}

	/* ─── Error ─── */
	.panel-error {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
		padding: 10px;
		background: #2e1a1a;
		border: 1px solid #5c2a2a;
		border-radius: 8px;
		text-align: center;
	}

	.error-icon {
		font-size: 1.2rem;
		color: #ef4444;
	}

	.error-message {
		font-size: 0.8rem;
		color: #fca5a5;
	}
</style>
