<script lang="ts">
	import { onDestroy } from 'svelte';
	import { BLEHardwareDeployer } from '$services/ble-deployer';
	import { USBHardwareDeployer } from '$services/usb-deployer';
	import { getHexContent } from '$services/api';
	import { getVelxioState } from '$services/velxio-manager';
	import {
		SUPPORTED_BAUD_RATES,
		DEFAULT_BAUD_RATE,
		type DeployState,
		type DeployProgress,
		type HardwareDeployer
	} from '$types/deployer';

	let {
		velxioIframe,
		arduinoCodeKey,
		slug,
		authLoggedIn
	}: {
		velxioIframe: HTMLIFrameElement | null;
		arduinoCodeKey: string;
		slug: string;
		authLoggedIn: boolean;
	} = $props();

	let deployer = $state<HardwareDeployer | null>(null);
	let isPaired = $state(false);
	let deployState = $state<DeployState>('idle');
	let deployMessage = $state('');
	let totalChunks = $state(0);
	let completedChunks = $state(0);
	let progressPercent = $derived(totalChunks > 0 ? Math.round((completedChunks / totalChunks) * 100) : 0);
	let bleSupported = $state(true);

	type DeployMode = 'ble' | 'usb';
	let deployMode: DeployMode = $state('ble');
	let usbSupported = $state(false);
	let isDesktop = $state(false);
	let serialLog = $state<string[]>([]);
	let serialInput = $state('');
	let serialActive = $state(false);
	let serialPendingBaud: number | null = null;
	let baudRate = $state(DEFAULT_BAUD_RATE);
	let errorMessage = $state('');
	let logsEnd = $state<HTMLDivElement | null>(null);

	$effect(() => {
		if (serialLog.length > 0 && logsEnd) {
			logsEnd.scrollIntoView({ behavior: 'smooth' });
		}
	});

	$effect(() => {
		if (typeof window === 'undefined') return;
		const mq = window.matchMedia('(min-width: 1024px)');
		isDesktop = mq.matches;
		const handler = (e: MediaQueryListEvent) => { isDesktop = e.matches; };
		mq.addEventListener('change', handler);
		return () => mq.removeEventListener('change', handler);
	});

	function detectDeviceMode(): DeployMode {
		const hasWebSerial = typeof navigator !== 'undefined' && 'serial' in navigator;
		const isDesktop = typeof window !== 'undefined' && window.matchMedia('(hover: hover)').matches;
		return hasWebSerial && isDesktop ? 'usb' : 'ble';
	}

	function createDeployer(mode: DeployMode): HardwareDeployer {
		if (mode === 'usb') return new USBHardwareDeployer();
		return new BLEHardwareDeployer();
	}

	function initDeployer() {
		deployMode = detectDeviceMode();
		usbSupported = typeof navigator !== 'undefined' && 'serial' in navigator;
		deployer = createDeployer(deployMode);
		bleSupported = deployer.checkSupport();
		if (!bleSupported) {
			deployState = 'error';
			errorMessage = deployMode === 'usb' 
				? 'Web Serial tidak didukung. Gunakan Chrome desktop.' 
				: 'Web Bluetooth tidak didukung. Gunakan Chrome Android.';
		}
		deployer.onDisconnected(() => {
			deployState = 'error';
			errorMessage = deployMode === 'usb' ? 'Koneksi USB terputus.' : 'Koneksi BLE terputus.';
			serialActive = false;
		});
	}

	function handleModeChange(mode: DeployMode) {
		if (deployer?.isConnected) {
			deployer.disconnect();
		}
		resetState();
		deployMode = mode;
		deployer = createDeployer(mode);
		bleSupported = deployer.checkSupport();
		if (!bleSupported) {
			deployState = 'error';
			errorMessage = mode === 'usb' 
				? 'Web Serial tidak didukung. Gunakan Chrome desktop.' 
				: 'Web Bluetooth tidak didukung. Gunakan Chrome Android.';
		}
	}

	function resetState() {
		deployState = 'idle';
		deployMessage = '';
		totalChunks = 0;
		completedChunks = 0;
		errorMessage = '';
		serialLog = [];
		serialActive = false;
		isPaired = false;
	}

	async function handlePair() {
		if (!deployer) initDeployer();
		if (!deployer) return;

		try {
			deployState = 'pairing';
			deployMessage = 'Pilih perangkat Velxio Deployer...';
			await deployer.pair();
			isPaired = true;
			deployState = 'idle';
			deployMessage = 'Perangkat terhubung';
		} catch (err: any) {
			deployState = 'error';
			errorMessage = err.message || 'Gagal pairing';
		}
	}

	async function handleDeploy() {
		if (!deployer) {
			errorMessage = 'Deployer belum diinisialisasi';
			return;
		}

		// Auto re-pair if BLE connection is lost
		if (!deployer.isConnected || !isPaired) {
			console.log('[DEPLOY] Connection lost, attempting re-pair...');
			try {
				deployState = 'pairing';
				deployMessage = 'Re-connecting to device...';
				await deployer.pair();
				isPaired = true;
				deployState = 'idle';
				console.log('[DEPLOY] Re-pair successful!');
			} catch (err: any) {
				deployState = 'error';
				errorMessage = 'Re-pair gagal: ' + err.message;
				return;
			}
		}

		serialActive = false;

		try {
			deployState = 'compiling';
			deployMessage = 'Mengompilasi kode...';

			let code = '';

			if (velxioIframe) {
				const state = getVelxioState(velxioIframe);
				if (state?.code) {
					code = state.code;
				}
			}

			if (!code) {
				code = localStorage.getItem(arduinoCodeKey) || '';
			}

			if (!code) {
				throw new Error('Tidak ada kode Arduino untuk di-deploy');
			}

			const res = await getHexContent({ code, board_fqbn: 'arduino:avr:uno' });

			if (!res.success || !res.hex_content) {
				throw new Error(res.error || 'Kompilasi gagal');
			}

			deployState = 'transferring';
			deployMessage = 'Mengirim data ke Velxio Deployer...';

			const onProgress = (p: DeployProgress) => {
				deployState = p.state;
				deployMessage = p.message;
				totalChunks = p.totalChunks;
				completedChunks = p.completedChunks;
			};

			if (deployMode === 'usb' && res.binary_content && typeof deployer.deployBinary === 'function') {
				await deployer.deployBinary(res.binary_content, onProgress);
			} else {
				await deployer.deployHex(res.hex_content, onProgress);
			}

			deployState = 'success';
			deployMessage = 'Upload berhasil! LED Hijau.';
			await handleOpenSerial();
		} catch (err: any) {
			deployState = 'error';
			errorMessage = err.message || 'Deploy gagal';
		}
	}

	async function handleOpenSerial() {
		if (!deployer || !isPaired) return;

		try {
			// Auto-reset Arduino before opening serial monitor
			console.log('[DEPLOY] Auto-resetting Arduino before serial monitor...');
			await deployer.resetArduino();

			if (serialPendingBaud !== null) {
				await deployer.setBaudRate(serialPendingBaud);
				baudRate = serialPendingBaud;
				serialPendingBaud = null;
			}
			serialActive = true;
			serialLog = [];
			await deployer.startSerialMonitor((text) => {
				serialLog = [...serialLog, text];
			});
		} catch (err: any) {
			serialActive = false;
			errorMessage = 'Gagal membuka Serial Monitor: ' + err.message;
		}
	}

	function handleCloseSerial() {
		deployer?.stopSerialMonitor();
		serialActive = false;
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

	async function handleSendSerial() {
		if (!deployer || !serialInput.trim()) return;
		try {
			await deployer.sendSerialInput(serialInput + '\n');
			serialInput = '';
		} catch (err: any) {
			errorMessage = 'Gagal mengirim: ' + err.message;
		}
	}

	function handleDisconnect() {
		deployer?.disconnect();
		resetState();
	}

	function handleRetry() {
		resetState();
	}

	function handleCancel() {
		deployState = 'idle';
		deployMessage = '';
		errorMessage = 'Deploy dibatalkan';
	}

	initDeployer();

	onDestroy(() => {
		if (isPaired) {
			deployer?.disconnect();
		}
	});
</script>

<div class="deploy-tab">
	<div class="deploy-toolbar">
		<h3 class="deploy-title">
			{deployMode === 'usb' ? 'USB Deployer' : 'BLE Deployer'}
		</h3>
		<div class="deploy-status" class:connected={isPaired}>
			<span class="status-dot"></span>
			{isPaired ? (deployer?.deviceName ? `Terhubung (${deployer.deviceName})` : 'Terhubung') : 'Terputus'}
		</div>
	</div>

	<div class="deploy-connection">
		{#if !isPaired}
			<button class="btn btn-primary" onclick={handlePair} disabled={deployState === 'pairing'}>
				{deployState === 'pairing' ? 'Menghubungkan...' : (deployMode === 'usb' ? 'Pilih Port USB' : 'Pair Device')}
			</button>
		{:else}
			<div class="deploy-actions">
				<button class="btn btn-success" onclick={handleDeploy} disabled={deployState === 'compiling' || deployState === 'transferring' || deployState === 'flashing'}>
					{deployState === 'compiling' ? 'Mengompilasi...' : deployState === 'transferring' ? 'Mengirim...' : deployState === 'flashing' ? 'Flashing...' : 'Compile & Deploy'}
				</button>
				{#if deployState === 'transferring' || deployState === 'flashing'}
					<button class="btn btn-outline" onclick={handleCancel}>Batal</button>
				{:else}
					<button class="btn btn-outline" onclick={handleDisconnect}>Putuskan</button>
				{/if}
			</div>
		{/if}
	</div>

	{#if deployState !== 'idle' && deployState !== 'error'}
		<div class="deploy-progress">
			<div class="progress-message">{deployMessage}</div>
			{#if totalChunks > 0}
				<div class="progress-bar-container">
					<div class="progress-bar-fill" style="width: {progressPercent}%"></div>
				</div>
				<div class="progress-text">
					Chunk {completedChunks}/{totalChunks} ({progressPercent}%)
				</div>
			{:else if deployState === 'compiling'}
				<div class="progress-spinner"></div>
			{/if}
		</div>
	{/if}

	{#if isPaired}
		<div class="serial-monitor">
			<div class="serial-header">
				<span>Serial Monitor</span>
				{#if usbSupported && bleSupported && deployState === 'idle'}
				<div class="mode-toggle-inline">
					<button 
						class="mode-chip" 
						class:active={deployMode === 'ble'}
						onclick={() => handleModeChange('ble')}
					>BLE</button>
					<button 
						class="mode-chip" 
						class:active={deployMode === 'usb'}
						onclick={() => handleModeChange('usb')}
					>USB</button>
				</div>
				{/if}
				<select class="baud-select" bind:value={baudRate} onchange={handleBaudChange}>
					{#each SUPPORTED_BAUD_RATES as b}
						<option value={b}>{b}</option>
					{/each}
				</select>
				<span class="baud-label">baud</span>
				<button class="btn btn-sm btn-outline" onclick={serialActive ? handleCloseSerial : handleOpenSerial}>
					{serialActive ? 'Tutup' : 'Mulai'}
				</button>
				{#if isPaired && deployState === 'idle'}
				<button class="deploy-fab" onclick={handleDeploy} title="Compile & Deploy">
					⚡
				</button>
				{/if}
			</div>
			<div class="serial-output">
				{#if !serialActive}
					<div class="serial-line serial-muted">Klik "Mulai" untuk membuka serial monitor ({baudRate} baud).</div>
				{:else}
					{#each serialLog as line, i}
						<div class="serial-line">{line}</div>
					{/each}
				{/if}
				<div bind:this={logsEnd}></div>
			</div>
			<form class="serial-input-area" onsubmit={(e) => { e.preventDefault(); handleSendSerial(); }}>
				<input
					type="text"
					bind:value={serialInput}
					placeholder="Kirim perintah ke Arduino..."
					class="serial-input"
				/>
				<button type="submit" class="btn btn-sm btn-primary">Kirim</button>
			</form>
		</div>
	{/if}

	{#if deployState === 'error'}
		<div class="deploy-error">
			<div class="error-icon">&#9888;</div>
			<div class="error-message">{errorMessage}</div>
			<button class="btn btn-outline" onclick={handleRetry}>Coba Lagi</button>
		</div>
	{/if}

	{#if !bleSupported && deployState !== 'error'}
		<div class="deploy-error">
			<div class="error-message">{deployMode === 'usb' ? 'Web Serial tidak didukung di browser ini. Gunakan Chrome desktop.' : 'Web Bluetooth tidak didukung di browser ini. Gunakan Chrome Android.'}</div>
		</div>
	{/if}
</div>

<style>
	.deploy-tab {
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 16px;
		height: 100%;
		box-sizing: border-box;
	}

	.deploy-toolbar {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.deploy-title {
		margin: 0;
		font-size: 1.1rem;
	}

	.deploy-status {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 0.85rem;
		color: #888;
	}

	.deploy-status.connected {
		color: #22c55e;
	}

	.status-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #888;
	}

	.deploy-status.connected .status-dot {
		background: #22c55e;
	}

	.deploy-connection {
		display: flex;
		gap: 8px;
	}

	.deploy-actions {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}

	.deploy-progress {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.progress-message {
		font-size: 0.9rem;
		color: #666;
	}

	.progress-bar-container {
		width: 100%;
		height: 12px;
		background: #e5e7eb;
		border-radius: 6px;
		overflow: hidden;
	}

	.progress-bar-fill {
		height: 100%;
		background: linear-gradient(90deg, #3b82f6, #22c55e);
		border-radius: 6px;
		transition: width 0.3s ease;
	}

	.progress-text {
		font-size: 0.8rem;
		color: #888;
		text-align: center;
	}

	.progress-spinner {
		width: 24px;
		height: 24px;
		border: 3px solid #e5e7eb;
		border-top-color: #3b82f6;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
		margin: 8px auto;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.serial-monitor {
		display: flex;
		flex-direction: column;
		gap: 8px;
		flex: 1;
		min-height: 0;
	}

	.serial-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-size: 0.9rem;
		font-weight: 600;
	}

	.serial-output {
		flex: 1;
		background: #1a1a2e;
		color: #22c55e;
		font-family: 'Courier New', monospace;
		font-size: 0.8rem;
		padding: 12px;
		border-radius: 6px;
		overflow-y: auto;
		min-height: 120px;
		line-height: 1.5;
	}

	.serial-line {
		white-space: pre-wrap;
		word-break: break-all;
	}

	.serial-muted {
		color: #6b7280;
		font-style: italic;
	}

	.baud-select {
		font-size: 0.8rem;
		padding: 2px 6px;
		border: 1px solid #d1d5db;
		border-radius: 4px;
		background: #fff;
		margin: 0 4px;
	}

	.baud-label {
		font-size: 0.75rem;
		color: #888;
		margin-right: 8px;
	}

	.serial-input-area {
		display: flex;
		gap: 8px;
	}

	.serial-input {
		flex: 1;
		padding: 8px 12px;
		border: 1px solid #d1d5db;
		border-radius: 6px;
		font-size: 0.85rem;
		font-family: 'Courier New', monospace;
	}

	.deploy-error {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
		padding: 16px;
		background: #fef2f2;
		border: 1px solid #fecaca;
		border-radius: 8px;
		text-align: center;
	}

	.error-icon {
		font-size: 1.5rem;
		color: #ef4444;
	}

	.error-message {
		font-size: 0.9rem;
		color: #991b1b;
	}

	.deploy-mode-toggle {
		display: flex;
		gap: 0;
		border-radius: 6px;
		overflow: hidden;
		border: 1px solid #d1d5db;
	}

	.mode-btn {
		padding: 4px 12px;
		font-size: 0.8rem;
		background: #f9fafb;
		border: none;
		cursor: pointer;
		transition: all 0.2s;
	}

	.mode-btn.active {
		background: #3b82f6;
		color: white;
	}

	.mode-btn:not(.active):hover {
		background: #e5e7eb;
	}

	.mode-toggle-inline {
		display: flex;
		gap: 2px;
		border-radius: 4px;
		overflow: hidden;
		border: 1px solid #d1d5db;
		padding: 2px;
	}

	.mode-chip {
		padding: 2px 8px;
		font-size: 0.7rem;
		background: #f9fafb;
		border: none;
		cursor: pointer;
		transition: all 0.15s;
		color: #374151;
	}

	.mode-chip.active {
		background: #3b82f6;
		color: white;
	}

	.mode-chip:not(.active):hover {
		background: #e5e7eb;
	}

	.deploy-fab {
		background: #22c55e;
		border: none;
		border-radius: 50%;
		width: 28px;
		height: 28px;
		cursor: pointer;
		font-size: 14px;
		color: white;
		display: flex;
		align-items: center;
		justify-content: center;
		margin-left: auto;
		transition: all 0.2s;
		flex-shrink: 0;
	}

	.deploy-fab:hover {
		background: #16a34a;
		transform: scale(1.05);
	}
</style>
