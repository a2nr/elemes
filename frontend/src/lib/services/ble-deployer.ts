import {
	BLE_SERVICE_UUID,
	BLE_CHAR_FLASHING_UUID,
	BLE_CHAR_SERIAL_UUID,
	CMD_INIT, CMD_DATA, CMD_END, CMD_ACK, CMD_ERR,
	CHUNK_SIZE, BLE_TIMEOUT_MS, END_TIMEOUT_MS, END_ACK_INDEX, MAX_RETRIES,
	type DeployProgress, type BLEACKResponse
} from '$types/deployer';

let _ackNotificationCount = 0;
function logAck(tag: string, msg: string) {
	console.log(`[BLE-ACK#${++_ackNotificationCount}] ${tag}: ${msg}`);
}

export class BLEHardwareDeployer {
	private server: BluetoothRemoteGATTServer | null = null;
	private service: BluetoothRemoteGATTService | null = null;
	private flashingChar: BluetoothRemoteGATTCharacteristic | null = null;
	private serialChar: BluetoothRemoteGATTCharacteristic | null = null;
	private device: BluetoothDevice | null = null;

	private onSerialData: ((text: string) => void) | null = null;

	/** Map of expected ACK index → resolver pair. Supports concurrent waits. */
	private ackResolvers = new Map<number, {
		resolve: (value: BLEACKResponse) => void;
		reject: (reason: Error) => void;
		timer: ReturnType<typeof setTimeout>;
	}>();

	/** ACKs that arrived before waitForAck was called, keyed by index. */
	private pendingAcks = new Map<number, BLEACKResponse>();

	private _onDisconnected: (() => void) | null = null;

	/** Bound handler refs so we can removeEventListener on cleanup/re-pair. */
	private _onDeviceDisconnect: (() => void) | null = null;
	private _onFlashingNotification: ((event: Event) => void) | null = null;
	private _onSerialNotification: ((event: Event) => void) | null = null;

	checkSupport(): boolean {
		return typeof navigator !== 'undefined' && 'bluetooth' in navigator;
	}

	get isConnected(): boolean {
		return this.server?.connected ?? false;
	}

	private withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
		return Promise.race([
			promise,
			new Promise<T>((_, reject) => {
				setTimeout(() => reject(new Error(`Timeout: ${label} (${ms}ms)`)), ms);
			})
		]);
	}

	async pair(): Promise<void> {
		if (!this.checkSupport()) {
			throw new Error('Web Bluetooth tidak didukung di browser ini. Gunakan Chrome Android.');
		}

		// Clean up any previous session's listeners before re-pairing
		this.cleanup();

		console.log('[BLE] step 1: requestDevice...');
		this.device = await navigator.bluetooth.requestDevice({
			filters: [{ namePrefix: 'Velxio' }],
			optionalServices: [BLE_SERVICE_UUID]
		});
		console.log('[BLE] step 1: device selected:', this.device.name);

		this._onDeviceDisconnect = () => {
			console.log('[BLE] gattserverdisconnected event');
			this._onDisconnected?.();
			this.cleanup();
		};
		this.device.addEventListener('gattserverdisconnected', this._onDeviceDisconnect);

		console.log('[BLE] step 2: gatt.connect...');
		this.server = await this.withTimeout(
			this.device.gatt!.connect(),
			10000,
			'gatt.connect'
		);
		console.log('[BLE] step 2: connected, mtu=' + this.server.mtu);

		console.log('[BLE] step 3: getPrimaryService...');
		this.service = await this.withTimeout(
			this.server.getPrimaryService(BLE_SERVICE_UUID),
			5000,
			'getPrimaryService'
		);
		console.log('[BLE] step 3: service found');

		console.log('[BLE] step 4: getCharacteristic flashing...');
		this.flashingChar = await this.withTimeout(
			this.service.getCharacteristic(BLE_CHAR_FLASHING_UUID),
			5000,
			'getCharacteristic(flashing)'
		);
		console.log('[BLE] step 4: flashing char found');

		console.log('[BLE] step 5: getCharacteristic serial...');
		this.serialChar = await this.withTimeout(
			this.service.getCharacteristic(BLE_CHAR_SERIAL_UUID),
			5000,
			'getCharacteristic(serial)'
		);
		console.log('[BLE] step 5: serial char found');

		console.log('[BLE] step 6: requestMTU(255)...');
		try {
			await this.withTimeout(
				this.server.requestMTU(255),
				3000,
				'requestMTU'
			);
			console.log('[BLE] step 6: MTU negotiated, now ' + this.server.mtu);
		} catch (e) {
			console.log('[BLE] step 6: MTU fallback, mtu=' + this.server.mtu, e);
		}

		console.log('[BLE] step 7: startNotifications...');
		await this.withTimeout(
			this.flashingChar.startNotifications(),
			5000,
			'startNotifications'
		);
		console.log('[BLE] step 7: notifications subscribed');

		this._onFlashingNotification = (event: Event) => {
			const target = event.target as BluetoothRemoteGATTCharacteristic;
			const dv = target.value!;
			const value = new Uint8Array(dv.buffer, dv.byteOffset, dv.byteLength);
			this.handleFlashingNotification(value);
		};
		this.flashingChar.addEventListener('characteristicvaluechanged', this._onFlashingNotification);
		console.log('[BLE] pair() completed successfully');
	}

	private handleFlashingNotification(value: Uint8Array) {
		const cmd = value[0];
		const index = value[1] | (value[2] << 8);
		const cmdName = cmd === CMD_ACK ? 'ACK' : cmd === CMD_ERR ? 'ERR' : 'UNKNOWN';
		logAck(cmdName, `index=${index} len=${value.length}`);

		if (cmd === CMD_ACK) {
			const ack: BLEACKResponse = { command: cmd, index, status: 'OK' };

			// Check if someone is waiting for this exact index
			const pending = this.ackResolvers.get(index);
			if (pending) {
				logAck(cmdName, `Found resolver for index=${index} — resolving`);
				this.ackResolvers.delete(index);
				clearTimeout(pending.timer);
				pending.resolve(ack);
			} else if (this.ackResolvers.has(0xFFFF) && index !== 0xFFFF) {
				// No one waiting for this specific index right now,
				// but someone IS waiting for END (0xFFFF) — don't
				// let a stale chunk ACK resolve it.
				logAck(cmdName, `index=${index} no resolver, END waitForAck(0xFFFF) active — dropping stale ACK`);
			} else {
				// Cache for a future waitForAck call
				logAck(cmdName, `index=${index} no resolver — caching as pendingAck`);
				this.pendingAcks.set(index, ack);
			}
		} else if (cmd === CMD_ERR) {
			const msgLen = value[3];
			const msg = msgLen > 0
				? new TextDecoder().decode(value.slice(4, 4 + msgLen))
				: 'Unknown error';
			logAck(cmdName, `index=${index} ERR: ${msg}`);

			const pending = this.ackResolvers.get(index);
			if (pending) {
				logAck(cmdName, `Found rejecter for index=${index} — rejecting`);
				this.ackResolvers.delete(index);
				clearTimeout(pending.timer);
				pending.reject(new Error(`ERR: ${msg}`));
			} else {
				logAck(cmdName, `index=${index} no rejecter — ERR lost: ${msg}`);
			}
		}
	}

	async deployHex(hexContent: string, onProgress: (p: DeployProgress) => void): Promise<void> {
		if (!this.flashingChar) throw new Error('Belum terhubung ke perangkat');

		const binaryData = this.hexToBinary(hexContent);
		const totalChunks = Math.ceil(binaryData.length / CHUNK_SIZE);
		const totalCRC = this.crc32(binaryData);

		console.log(`[BLE] deployHex: ${binaryData.length} bytes, ${totalChunks} chunks, CRC=0x${totalCRC.toString(16)}`);

		onProgress({ state: 'transferring', message: 'Mengirim INIT...', totalChunks, completedChunks: 0 });
		console.log('[BLE] D: sending INIT...');
		await this.sendCommand(CMD_INIT, 0, this.uint32ToBytes(totalCRC));
		console.log('[BLE] D: INIT done');

		for (let i = 0; i < totalChunks; i++) {
			const start = i * CHUNK_SIZE;
			const end = Math.min(start + CHUNK_SIZE, binaryData.length);
			const chunk = binaryData.slice(start, end);
			const chunkCRC = this.crc32(chunk);

			await this.sendCommandWithRetry(CMD_DATA, i, chunk, chunkCRC);

			onProgress({
				state: 'transferring',
				message: `Mengirim chunk ${i + 1}/${totalChunks}`,
				totalChunks,
				completedChunks: i + 1
			});
		}
		console.log('[BLE] D: all DATA chunks done');

		onProgress({ state: 'flashing', message: 'Verifikasi & flashing...', totalChunks, completedChunks: totalChunks });
		console.log('[BLE] D: END starting (30s timeout)...');
		const startTime = Date.now();
		try {
			await this.sendCommand(CMD_END, END_ACK_INDEX, this.uint32ToBytes(totalCRC), END_TIMEOUT_MS);
			const elapsed = Date.now() - startTime;
			console.log(`[BLE] D: END ACK received after ${elapsed}ms, flash success!`);
		} catch (err) {
			const elapsed = Date.now() - startTime;
			console.log(`[BLE] D: END FAILED after ${elapsed}ms:`, err);
			throw err;
		}

		onProgress({ state: 'serial_bridge', message: 'Flash berhasil! Membuka Serial Monitor...', totalChunks, completedChunks: totalChunks });
	}

	private async sendCommand(cmd: number, index: number, data: Uint8Array, timeoutMs?: number): Promise<void> {
		const cmdName = cmd === CMD_INIT ? 'INIT' : cmd === CMD_DATA ? 'DATA' : cmd === CMD_END ? 'END' : `0x${cmd.toString(16)}`;
		const payload = new Uint8Array(4 + data.length + 4);
		payload[0] = cmd;
		payload[1] = index & 0xFF;
		payload[2] = (index >> 8) & 0xFF;
		payload[3] = data.length;
		payload.set(data, 4);

		const crc = this.crc32(data);
		payload.set([
			crc & 0xFF, (crc >> 8) & 0xFF, (crc >> 16) & 0xFF, (crc >> 24) & 0xFF
		], 4 + data.length);

		const ackTimeout = timeoutMs ?? BLE_TIMEOUT_MS;
		console.log(`[BLE-CMD] ${cmdName} idx=${index}: waitForAck timeout=${ackTimeout}ms start`);
		const ackPromise = this.waitForAck(index, ackTimeout);
		try {
			console.log(`[BLE-CMD] ${cmdName} idx=${index}: writing payload (${payload.length} bytes)...`);
			await this.withTimeout(
				this.flashingChar!.writeValueWithResponse(payload),
				3000,
				'writeValueWithResponse'
			);
			console.log(`[BLE-CMD] ${cmdName} idx=${index}: write done, now waiting for ACK...`);
		} catch (e) {
			console.log(`[BLE-CMD] ${cmdName} idx=${index}: write failed, still waiting for ACK`, e);
		}

		/* END (flash ~8s): Android BLE stack (Qualcomm) drops
		 * characteristicvaluechanged events after ~8s idle, so ACK
		 * notification is unreliable.  Use readValue() to poll the
		 * firmware's state machine instead — GATT Read is client-
		 * initiated and NOT affected by the notify idle-drop bug.
		 *
		 * CCCD refresh is fire-and-forget as a belt-and-suspenders:
		 * it didn't solve the issue on Qualcomm, but may help on
		 * other devices. */
		if (cmd === CMD_END) {
			/* Fire-and-forget CCCD refresh (don't await — non-blocking). */
			this.flashingChar!.stopNotifications().catch(() => {});
			this.flashingChar!.startNotifications().then(
				() => console.log('[BLE-CMD] END: CCCD re-subscribed (fire-and-forget)'),
				(e) => console.log('[BLE-CMD] END: CCCD refresh failed (non-critical)', e)
			);

			/* Read-based state poll — the RELIABLE path.
			 * State values from state_machine.h:
			 *   0=IDLE, 1=RECEIVING, 2=VERIFYING, 3=FLASHING (keep polling),
			 *   4=SERIAL_BRIDGE (success), 5=ERROR_TARGET, 6=ERROR_CHECKSUM */
			const STATE_SERIAL_BRIDGE = 4;
			const STATE_ERROR_TARGET = 5;
			const STATE_ERROR_CHECKSUM = 6;

			const readPoll = (async () => {
				const deadline = Date.now() + ackTimeout;
				let firstPoll = true;
				while (Date.now() < deadline) {
					try {
						const dv = await this.withTimeout(
							this.flashingChar!.readValue(),
							3000,
							'readValue(state)'
						);
						const state = dv.getUint8(0);
						console.log(`[BLE-CMD] END: readValue state=${state}`);

						if (state === STATE_SERIAL_BRIDGE) {
							console.log('[BLE-CMD] END: state=SERIAL_BRIDGE — flash success via read poll');
							return 'ok' as const;
						}
						if (state === STATE_ERROR_TARGET || state === STATE_ERROR_CHECKSUM) {
							console.log(`[BLE-CMD] END: state=ERROR(${state}) — flash failed via read poll`);
							throw new Error('Flash gagal di sisi firmware (state=' + state + ')');
						}
						/* state=FLASHING or VERIFYING — keep polling */
					} catch (e) {
						/* readValue failed (GATT error or timeout) — keep
						 * retrying unless the connection itself is dead. */
						if (!this.isConnected) {
							throw new Error('Koneksi BLE terputus saat menunggu flash');
						}
						console.log('[BLE-CMD] END: readValue retry...', e);
					}
					/* First poll at 200ms (fast check if flash already done),
					 * then every 500ms. ~16 polls during 8s flash. */
					await new Promise<void>(r => setTimeout(r, firstPoll ? 200 : 500));
					firstPoll = false;
				}
				console.log('[BLE-CMD] END: readPoll deadline passed (30s)');
				return 'timeout' as const;
			})();

			/* Race: ACK notify (fast path — works on some devices) vs
			 * readValue poll (reliable path — works everywhere). */
			const ackWithLabel = ackPromise.then(() => 'ack' as const);
			const result = await Promise.race([ackWithLabel, readPoll]);
			console.log(`[BLE-CMD] END idx=${index}: resolved via ${result}`);

			/* Clean up the ackPromise resolver if readPoll won —
			 * prevents a dangling 30s timer. */
			if (result !== 'ack') {
				const entry = this.ackResolvers.get(index);
				if (entry) {
					clearTimeout(entry.timer);
					this.ackResolvers.delete(index);
					console.log(`[BLE-CMD] END: cleaned up ackPromise resolver (won via ${result})`);
				}
			}

			if (result === 'timeout') {
				throw new Error(`Timeout menunggu ACK untuk chunk ${index}`);
			}
			return;
		}

		/* INIT/DATA: Same Android notify idle-drop bug affects these too.
		 * Race ackPromise against readValue() state poll as fallback.
		 * INIT success: firmware state >= RECEIVING(1) (not IDLE/ERROR).
		 * DATA success: firmware state == RECEIVING(1). */
		if (cmd === CMD_INIT || cmd === CMD_DATA) {
			const readPoll = (async () => {
				const deadline = Date.now() + ackTimeout;
				while (Date.now() < deadline) {
					try {
						const dv = await this.withTimeout(
							this.flashingChar!.readValue(),
							3000,
							'readValue(state)'
						);
						const state = dv.getUint8(0);
						console.log(`[BLE-CMD] ${cmdName}: readValue state=${state}`);

						/* INIT: any non-IDLE(0), non-ERROR(5/6) state means command was processed.
						 * DATA: state must stay RECEIVING(1) — error if >=5. */
						if (cmd === CMD_INIT) {
							if (state >= 1 && state <= 4) {
								console.log(`[BLE-CMD] ${cmdName}: state=${state} — INIT confirmed via read poll`);
								return 'ok' as const;
							}
						} else { /* DATA */
							if (state === 1) {
								console.log(`[BLE-CMD] ${cmdName}: state=1 (RECEIVING) — DATA confirmed via read poll`);
								return 'ok' as const;
							}
						}
						if (state >= 5) {
							throw new Error(`Firmware error (state=${state})`);
						}
					} catch (e) {
						if (!this.isConnected) {
							throw new Error('Koneksi BLE terputus');
						}
						console.log(`[BLE-CMD] ${cmdName}: readValue retry...`, e);
					}
					await new Promise<void>(r => setTimeout(r, 200));
				}
				console.log(`[BLE-CMD] ${cmdName}: readPoll deadline passed (${ackTimeout}ms)`);
				return 'timeout' as const;
			})();

			const ackWithLabel = ackPromise.then(() => 'ack' as const);
			const result = await Promise.race([ackWithLabel, readPoll]);
			console.log(`[BLE-CMD] ${cmdName} idx=${index}: resolved via ${result}`);

			if (result !== 'ack') {
				const entry = this.ackResolvers.get(index);
				if (entry) {
					clearTimeout(entry.timer);
					this.ackResolvers.delete(index);
				}
			}
			if (result === 'timeout') {
				throw new Error(`Timeout menunggu ACK untuk chunk ${index}`);
			}
			return;
		}
	}

	private async sendCommandWithRetry(cmd: number, index: number, data: Uint8Array, chunkCRC: number): Promise<void> {
		const payload = new Uint8Array(4 + data.length + 4);
		payload[0] = cmd;
		payload[1] = index & 0xFF;
		payload[2] = (index >> 8) & 0xFF;
		payload[3] = data.length;
		payload.set(data, 4);
		payload.set([
			chunkCRC & 0xFF, (chunkCRC >> 8) & 0xFF, (chunkCRC >> 16) & 0xFF, (chunkCRC >> 24) & 0xFF
		], 4 + data.length);

		for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
			try {
				const ackPromise = this.waitForAck(index);
				await this.flashingChar!.writeValueWithResponse(payload);
				await ackPromise;
				return;
			} catch (err) {
				if (attempt === MAX_RETRIES - 1) throw err;
				await new Promise(r => setTimeout(r, 500));
			}
		}
	}

	private waitForAck(expectedIndex: number, timeoutMs: number = BLE_TIMEOUT_MS): Promise<BLEACKResponse> {
		return new Promise((resolve, reject) => {
			// Check for a cached ACK that arrived before we started waiting
			const cached = this.pendingAcks.get(expectedIndex);
			if (cached) {
				this.pendingAcks.delete(expectedIndex);
				logAck('WAIT', `pendingAcks hit for index=${expectedIndex} actual=${cached.index} — resolving immediately`);
				resolve(cached);
				return;
			}

			logAck('WAIT', `Registering resolver for index=${expectedIndex} timeout=${timeoutMs}ms`);

			const timer = setTimeout(() => {
				const entry = this.ackResolvers.get(expectedIndex);
				if (entry) {
					this.ackResolvers.delete(expectedIndex);
					logAck('WAIT', `TIMEOUT after ${timeoutMs}ms for index=${expectedIndex} — rejecting`);
					reject(new Error(`Timeout menunggu ACK untuk chunk ${expectedIndex}`));
				} else {
					logAck('WAIT', `Timeout fired but resolver already consumed for index=${expectedIndex} — ignoring`);
				}
			}, timeoutMs);

			this.ackResolvers.set(expectedIndex, { resolve, reject, timer });
		});
	}

	async startSerialMonitor(onData: (text: string) => void): Promise<void> {
		if (!this.serialChar) throw new Error('Belum terhubung ke perangkat');

		this.onSerialData = onData;

		await this.serialChar.startNotifications();
		this._onSerialNotification = (event: Event) => {
			const target = event.target as BluetoothRemoteGATTCharacteristic;
			const dv = target.value!;
			const value = new Uint8Array(dv.buffer, dv.byteOffset, dv.byteLength);
			const text = new TextDecoder().decode(value);
			this.onSerialData?.(text);
		};
		this.serialChar.addEventListener('characteristicvaluechanged', this._onSerialNotification);
	}

	async sendSerialInput(text: string): Promise<void> {
		if (!this.serialChar) throw new Error('Belum terhubung ke perangkat');
		const encoder = new TextEncoder();
		await this.serialChar.writeValueWithoutResponse(encoder.encode(text));
	}

	stopSerialMonitor(): void {
		if (this.serialChar && this._onSerialNotification) {
			this.serialChar.removeEventListener('characteristicvaluechanged', this._onSerialNotification);
			this.serialChar.stopNotifications();
		}
		this._onSerialNotification = null;
		this.onSerialData = null;
	}

	disconnect(): void {
		this.stopSerialMonitor();
		if (this.flashingChar) {
			this.flashingChar.stopNotifications();
		}
		this.server?.disconnect();
		this.cleanup();
	}

	onDisconnected(callback: () => void): void {
		this._onDisconnected = callback;
	}

	private cleanup(): void {
		// Remove device-level event listeners
		if (this.device && this._onDeviceDisconnect) {
			this.device.removeEventListener('gattserverdisconnected', this._onDeviceDisconnect);
		}
		this._onDeviceDisconnect = null;

		// Remove flashing notification listener
		if (this.flashingChar && this._onFlashingNotification) {
			this.flashingChar.removeEventListener('characteristicvaluechanged', this._onFlashingNotification);
		}
		this._onFlashingNotification = null;

		// Remove serial notification listener
		if (this.serialChar && this._onSerialNotification) {
			this.serialChar.removeEventListener('characteristicvaluechanged', this._onSerialNotification);
		}
		this._onSerialNotification = null;

		this.server = null;
		this.service = null;
		this.flashingChar = null;
		this.serialChar = null;
		this.device = null;
		// Clear all pending ACK resolvers
		for (const [idx, entry] of this.ackResolvers) {
			clearTimeout(entry.timer);
		}
		this.ackResolvers.clear();
		this.pendingAcks.clear();
		this.onSerialData = null;
	}

	private hexToBinary(hexContent: string): Uint8Array {
		const bytes: number[] = [];
		let extendedAddress = 0;

		for (const line of hexContent.split('\n')) {
			const trimmed = line.trim();
			if (!trimmed || trimmed[0] !== ':') continue;

			const byteCount = parseInt(trimmed.substring(1, 3), 16);
			const address = parseInt(trimmed.substring(3, 7), 16) + extendedAddress;
			const recordType = parseInt(trimmed.substring(7, 9), 16);

			if (recordType === 0x00) {
				for (let i = 0; i < byteCount; i++) {
					const byteOffset = 9 + i * 2;
					if (byteOffset + 2 <= trimmed.length) {
						const byteVal = parseInt(trimmed.substring(byteOffset, byteOffset + 2), 16);
						bytes[address + i] = byteVal;
					}
				}
			} else if (recordType === 0x04) {
				extendedAddress = parseInt(trimmed.substring(9, 13), 16) << 16;
			} else if (recordType === 0x01) {
				break;
			}
		}

		const result = new Uint8Array(bytes.length);
		for (let i = 0; i < bytes.length; i++) {
			result[i] = bytes[i] ?? 0;
		}
		return result;
	}

	private crc32Table: Uint32Array | null = null;

	private crc32(data: Uint8Array): number {
		if (!this.crc32Table) {
			this.crc32Table = new Uint32Array(256);
			for (let i = 0; i < 256; i++) {
				let c = i;
				for (let j = 0; j < 8; j++) {
					c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
				}
				this.crc32Table[i] = c;
			}
		}
		let crc = 0xFFFFFFFF;
		for (let i = 0; i < data.length; i++) {
			crc = this.crc32Table[(crc ^ data[i]) & 0xFF] ^ (crc >>> 8);
		}
		return (crc ^ 0xFFFFFFFF) >>> 0;
	}

	private uint32ToBytes(value: number): Uint8Array {
		return new Uint8Array([
			value & 0xFF,
			(value >> 8) & 0xFF,
			(value >> 16) & 0xFF,
			(value >> 24) & 0xFF
		]);
	}
}
