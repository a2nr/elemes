/* Ambient declarations for Web Serial API (not in TS 5.9 lib.dom.d.ts). */
/* Minimal subset needed by USBHardwareDeployer.                      */
/* Wrapped in declare global because the file is a module (has imports)  */
/* and we need these types to be globally visible.                       */
declare global {
	class SerialPort {
		readonly readable: ReadableStream<Uint8Array> | null;
		readonly writable: WritableStream<Uint8Array> | null;
		open(options: SerialPortOpenOptions): Promise<void>;
		close(): Promise<void>;
		getInfo(): SerialPortInfo;
		setSignals(signals: SerialPortSignals): Promise<void>;
		addEventListener(
			type: 'connect' | 'disconnect',
			listener: (event: SerialConnectionEvent) => void
		): void;
		removeEventListener(
			type: 'connect' | 'disconnect',
			listener: (event: SerialConnectionEvent) => void
		): void;
	}

	interface SerialPortOpenOptions {
		baudRate: number;
		dataBits: 8 | 7 | 6 | 5;
		stopBits: 1 | 2;
		parity: 'none' | 'even' | 'odd';
		flowControl: 'none' | 'hardware';
	}

	interface SerialPortInfo {
		usbVendorId: number;
		usbProductId: number;
	}

	interface SerialPortSignals {
		dataTerminalReady?: boolean;
		requestToSend?: boolean;
	}

	interface SerialConnectionEvent extends Event {
		readonly port: SerialPort;
	}

	interface SerialPortRequestOptions {
		filters?: SerialPortFilter[];
	}

	interface SerialPortFilter {
		usbVendorId?: number;
		usbProductId?: number;
	}

	interface Serial {
		readonly onconnect: ((event: SerialConnectionEvent) => void) | null;
		readonly ondisconnect: ((event: SerialConnectionEvent) => void) | null;
		requestPort(options?: SerialPortRequestOptions): Promise<SerialPort>;
		addEventListener(
			type: 'connect' | 'disconnect',
			listener: (event: SerialConnectionEvent) => void
		): void;
		removeEventListener(
			type: 'connect' | 'disconnect',
			listener: (event: SerialConnectionEvent) => void
		): void;
	}

	interface Navigator {
		readonly serial: Serial;
	}
}

import type { HardwareDeployer, DeployProgress } from '$types/deployer';

/* ── STK500v1 protocol constants ────────────────────────────────────── */
const CRC_EOP = 0x20;
const STK_GET_SYNC = 0x30;
const STK_READ_SIGN = 0x75;
const STK_ENTER_PROGMODE = 0x50;
const STK_LOAD_ADDRESS = 0x55;
const STK_PROG_PAGE = 0x64;
const STK_LEAVE_PROGMODE = 0x51;

const STK_INSYNC = 0x14;
const STK_OK = 0x10;
const STK_NOSYNC = 0x15;

const ATMEGA328P_SIG_0 = 0x1e;
const ATMEGA328P_SIG_1 = 0x95;
const ATMEGA328P_SIG_2 = 0x0f;
const ATMEGA328P_FLASH_SIZE = 32768;
const ATMEGA328P_PAGE_SIZE = 128;

const STK_SYNC_RETRIES = 6;
const STK_SYNC_TIMEOUT_MS = 300; /* Per-attempt read timeout during initial sync */
const STK_CMD_TIMEOUT_MS = 200;
const STK_PAGE_TIMEOUT_MS = 500;
const STK_LEAVE_TIMEOUT_MS = 100;

const BOOTLOADER_SETTLE_MS = 100; /* Wait after DTR release for optiboot to start */
const DRAIN_BYTE_TIMEOUT_MS = 10; /* How long to wait for the next stray byte */
const DRAIN_TOTAL_MS = 50; /* Max total time to spend draining */

/* ── Arduino VID/PID pairs for port filter ─────────────────────────── */
const ARDUINO_VID_PIDS: SerialPortFilter[] = [
	{ usbVendorId: 0x2341, usbProductId: 0x0043 },
	{ usbVendorId: 0x2341, usbProductId: 0x0001 },
	{ usbVendorId: 0x2341, usbProductId: 0x0243 },
	{ usbVendorId: 0x2a03, usbProductId: 0x0043 },
	{ usbVendorId: 0x0403, usbProductId: 0x6001 },
	{ usbVendorId: 0x1a86, usbProductId: 0x7523 },
	{ usbVendorId: 0x1a86, usbProductId: 0x5523 }
];

const FLASH_BAUD = 115200;
const SERIAL_MONITOR_BAUD = 9600;

/* ── Helpers ──────────────────────────────────────────────────────────── */
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function decodeBase64(base64: string): Uint8Array {
	try {
		const binary = atob(base64);
		const bytes = new Uint8Array(binary.length);
		for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
		return bytes;
	} catch {
		throw new Error('Invalid base64 input: expected a valid base64-encoded string');
	}
}

/* ── USBHardwareDeployer ─────────────────────────────────────────────── */
export class USBHardwareDeployer implements HardwareDeployer {
	private port: SerialPort | null = null;
	private reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
	private writer: WritableStreamDefaultWriter<Uint8Array> | null = null;
	private keepReading = false;
	private _onDisconnected: (() => void) | null = null;
	private _deviceName: string | null = null;

	/* Bound handler so we can removeEventListener on cleanup */
	private _boundDisconnectHandler: ((event: SerialConnectionEvent) => void) | null = null;

	/* ── HardwareDeployer interface ────────────────────────────── */

	checkSupport(): boolean {
		return typeof navigator !== 'undefined' && 'serial' in navigator;
	}

	get isConnected(): boolean {
		return this.port !== null;
	}

	get deviceName(): string | null {
		return this._deviceName;
	}

	/* ── Pair / connect ────────────────────────────────────────── */

	async pair(): Promise<void> {
		if (!this.checkSupport()) {
			throw new Error(
				'Web Serial tidak didukung di browser ini. Gunakan Chrome/Edge.'
			);
		}

		/* Clean up any previous session first */
		await this.cleanup();

		let port: SerialPort;
		try {
			port = await navigator.serial.requestPort({
				filters: ARDUINO_VID_PIDS
			});
		} catch {
			throw new Error('Pemilihan port dibatalkan');
		}
		this.port = port;

		const info = port.getInfo();
		this._deviceName = `USB ${info.usbVendorId.toString(16)}:${info.usbProductId.toString(16)}`;
		console.log('[USB] paired:', this._deviceName);

		await this.port.open({
			baudRate: FLASH_BAUD,
			dataBits: 8,
			stopBits: 1,
			parity: 'none',
			flowControl: 'none'
		});
		console.log('[USB] port opened at', FLASH_BAUD);

		this.writer = this.port.writable!.getWriter();
		this.reader = this.port.readable!.getReader();

		/* Listen for disconnect on navigator.serial */
		this._boundDisconnectHandler = async (event: SerialConnectionEvent) => {
			if (event.port === this.port) {
				console.log('[USB] port disconnected event');
				await this.cleanup();
				this._onDisconnected?.();
			}
		};
		navigator.serial.addEventListener('disconnect', this._boundDisconnectHandler);
	}

	/* ── DTR auto-reset ─────────────────────────────────────────── */

	async resetArduino(): Promise<void> {
		if (!this.port) throw new Error('Belum terhubung ke perangkat');

		console.log('[USB] resetArduino: DTR/RTS pulse');
		/* DTR low + RTS low → 10ms → both high → wait 50ms for optiboot */
		await this.port.setSignals({
			dataTerminalReady: false,
			requestToSend: false
		});
		await sleep(10);
		await this.port.setSignals({
			dataTerminalReady: true,
			requestToSend: true
		});
		/* Wait for optiboot to initialize (~100ms is safe, gives us ~900ms for sync) */
		await sleep(100);
		console.log('[USB] resetArduino: DTR pulse done');
	}

	/* ── Deploy ─────────────────────────────────────────────────── */

	async deployBinary(
		base64Binary: string,
		onProgress: (p: DeployProgress) => void
	): Promise<void> {
		const buffer = decodeBase64(base64Binary);
		if (buffer.length === 0) throw new Error('Buffer kosong');
		if (buffer.length > ATMEGA328P_FLASH_SIZE) {
			throw new Error(
				`Buffer ${buffer.length} bytes melebihi flash ${ATMEGA328P_FLASH_SIZE}`
			);
		}
		await this.flashBuffer(buffer, onProgress);
	}

	async deployHex(
		_hexContent: string,
		_onProgress: (p: DeployProgress) => void
	): Promise<void> {
		throw new Error(
			'USB deployer uses deployBinary. Use deployBinary(base64) instead.'
		);
	}

	/* ── Serial monitor ─────────────────────────────────────────── */

	async startSerialMonitor(onData: (text: string) => void): Promise<void> {
		if (!this.port) throw new Error('Belum terhubung ke perangkat');

		/* Release flash-mode reader/writer, then close port */
		await this.stopReaderWriter();
		await this.port.close();

		/* Reopen at serial-monitor baud rate (9600 default) */
		await this.port.open({
			baudRate: SERIAL_MONITOR_BAUD,
			dataBits: 8,
			stopBits: 1,
			parity: 'none',
			flowControl: 'none'
		});
		console.log('[USB-SERIAL] port opened at', SERIAL_MONITOR_BAUD);

		this.writer = this.port.writable!.getWriter();
		this.reader = this.port.readable!.getReader();
		this.keepReading = true;

		const decoder = new TextDecoder();
		this.readLoop(onData, decoder).catch((e) =>
			console.error('[USB-SERIAL] read loop error:', e)
		);
	}

	private async readLoop(
		onData: (text: string) => void,
		decoder: TextDecoder
	): Promise<void> {
		while (this.keepReading && this.reader) {
			try {
				const { value, done } = await this.reader.read();
				if (done) break;
				if (value && value.length > 0) {
					const text = decoder.decode(value, { stream: true });
					onData(text);
				}
			} catch (e) {
				if (this.keepReading) {
					console.error('[USB-SERIAL] read error:', e);
				}
				break;
			}
		}
	}

	stopSerialMonitor(): void {
		console.log('[USB-SERIAL] stopSerialMonitor');
		this.keepReading = false;
	}

	async sendSerialInput(text: string): Promise<void> {
		if (!this.writer) throw new Error('Belum terhubung ke perangkat');
		const encoder = new TextEncoder();
		await this.writer.write(encoder.encode(text));
	}

	async setBaudRate(baud: number): Promise<void> {
		if (!this.port) throw new Error('Belum terhubung ke perangkat');
		/* Web Serial cannot change baud without close+reopen */
		await this.stopReaderWriter();
		await this.port.close();
		await this.port.open({
			baudRate: baud,
			dataBits: 8,
			stopBits: 1,
			parity: 'none',
			flowControl: 'none'
		});
		this.writer = this.port.writable!.getWriter();
		this.reader = this.port.readable!.getReader();
		console.log('[USB-SERIAL] baud rate changed to', baud);
	}

	/* ── Disconnect / lifecycle ─────────────────────────────────── */

	async disconnect(): Promise<void> {
		this.stopSerialMonitor();
		await this.cleanup();
	}

	onDisconnected(callback: () => void): void {
		this._onDisconnected = callback;
	}

	/* ── Private helpers ──────────────────────────────────────────── */

	private async stopReaderWriter(): Promise<void> {
		this.keepReading = false;
		try {
			await this.reader?.cancel();
		} catch {
			/* ignore */
		}
		this.reader = null;
		try {
			await this.writer?.close();
		} catch {
			/* ignore */
		}
		this.writer = null;
	}

	private async cleanup(): Promise<void> {
		if (this._boundDisconnectHandler) {
			navigator.serial.removeEventListener(
				'disconnect',
				this._boundDisconnectHandler
			);
			this._boundDisconnectHandler = null;
		}
		this.keepReading = false;
		await this.stopReaderWriter();
		try {
			await this.port?.close();
		} catch {
			/* ignore */
		}
		this.port = null;
		this._deviceName = null;
	}

	/* ── Timeout race helper ──────────────────────────────────────── */

	private withTimeout<T>(
		promise: Promise<T>,
		ms: number,
		label: string
	): Promise<T> {
		return Promise.race([
			promise,
			new Promise<T>((_, reject) =>
				setTimeout(() => reject(new Error(`Timeout: ${label} (${ms}ms)`)), ms)
			)
		]);
	}

	/* ── STK500v1 protocol ───────────────────────────────────────── */
	/*                                                               */
	/* Every command is terminated with CRC_EOP=0x20.  optiboot      */
	/* replies with STK_INSYNC=0x14 immediately, then optional       */
	/* payload bytes, then STK_OK=0x10.                              */
	/* ─────────────────────────────────────────────────────────────── */

	/**
	 * Write a command, then expect: STK_INSYNC, optional payload, optional STK_OK.
	 * Returns the payload bytes (if any).
	 */
	private async sendAndExpect(
		cmd: Uint8Array,
		respLen: number,
		timeoutMs: number,
		strictOk: boolean
	): Promise<Uint8Array> {
		if (!this.writer) throw new Error('Writer not available');

		console.log(
			`[USB] send: ${Array.from(cmd)
				.map((b) => '0x' + b.toString(16).padStart(2, '0'))
				.join(' ')}`
		);

		await this.withTimeout(this.writer.write(cmd), timeoutMs, 'write');
		console.log('[USB] write done');

		/* Read STK_INSYNC (1 byte) */
		const insync = await this.readExact(1, timeoutMs);
		console.log(`[USB] INSYNC: 0x${insync[0].toString(16).padStart(2, '0')}`);

		if (insync[0] === STK_NOSYNC) {
			console.log('[USB] optiboot replied NOSYNC');
			throw new Error('optiboot replied NOSYNC');
		}
		if (insync[0] !== STK_INSYNC) {
			console.log(
				`[USB] expected INSYNC 0x${STK_INSYNC.toString(16)}, got 0x${insync[0].toString(16)}`
			);
			throw new Error(
				`expected INSYNC 0x14, got 0x${insync[0].toString(16)}`
			);
		}

		/* Read optional payload */
		let resp: Uint8Array = new Uint8Array(0);
		if (respLen > 0) {
			resp = await this.readExact(respLen, timeoutMs);
		}

		/* Read optional STK_OK */
		if (strictOk) {
			const ok = await this.readExact(1, timeoutMs);
			console.log(`[USB] STK_OK: 0x${ok[0].toString(16).padStart(2, '0')}`);
			if (ok[0] !== STK_OK) {
				throw new Error(`expected OK 0x10, got 0x${ok[0].toString(16)}`);
			}
		}

		return resp;
	}

	/**
	 * Read exactly `len` bytes from the serial stream, with a deadline.
	 *
	 * On timeout, any stray bytes that arrive from the orphaned `reader.read()`
	 * promise are drained so the protocol stream stays synchronised (C1).
	 */
	private async readExact(len: number, timeoutMs: number): Promise<Uint8Array> {
		const result = new Uint8Array(len);
		let got = 0;
		const deadline = Date.now() + timeoutMs;
		while (got < len) {
			const remaining = deadline - Date.now();
			if (remaining <= 0)
				throw new Error(`read timeout: got ${got}/${len}`);
			try {
				const { value, done } = await Promise.race([
					this.reader!.read(),
					new Promise<never>((_, reject) =>
						setTimeout(
							() => reject(new Error('read timeout')),
							remaining
						)
					)
				]);
				if (done) throw new Error('stream closed');
				const copyLen = Math.min(value.length, len - got);
				result.set(value.subarray(0, copyLen), got);
				got += copyLen;
			} catch (e) {
				const reason = (e as Error).message || 'unknown';
				console.log(`[USB] readExact failed at ${got}/${len}: ${reason}`);
				/* Drain stale bytes from orphaned reader.read() promise (C1) */
				await this.drainStray();
				throw e;
			}
		}
		return result;
	}

	/**
	 * Drain any stray bytes from the serial input.
	 * Keeps reading until no bytes arrive for DRAIN_BYTE_TIMEOUT_MS,
	 * or DRAIN_TOTAL_MS has elapsed.
	 */
	private async drainStray(): Promise<void> {
		const deadline = Date.now() + DRAIN_TOTAL_MS;
		let totalDrained = 0;

		while (Date.now() < deadline) {
			try {
				const { value, done } = await Promise.race([
					this.reader!.read(),
					new Promise<never>((_, reject) =>
						setTimeout(() => reject(new Error('timeout')), DRAIN_BYTE_TIMEOUT_MS)
					)
				]);
				if (done) break;
				if (value && value.length > 0) {
					totalDrained += value.length;
					/* Got bytes; keep looping inside the same deadline window. */
					continue;
				}
				/* Empty chunk: treat same as a quiet window. */
				break;
			} catch {
				/* No bytes available for DRAIN_BYTE_TIMEOUT_MS -> channel is clean. */
				break;
			}
		}

		if (totalDrained > 0) {
			console.log(`[USB] drained ${totalDrained} stray bytes`);
		}
	}

	/* ── STK500v1 command implementations ─────────────────────────── */

	private async getSync(): Promise<void> {
		const cmd = new Uint8Array([STK_GET_SYNC, CRC_EOP]);

		for (let attempt = 0; attempt < STK_SYNC_RETRIES; attempt++) {
			try {
				/* Drain before sending to ensure clean channel */
				await this.drainStray();
				await this.sendAndExpect(cmd, 0, STK_SYNC_TIMEOUT_MS, true);
				console.log(`[USB] get_sync OK (attempt ${attempt + 1})`);
				return;
			} catch (e) {
				console.log(`[USB] get_sync attempt ${attempt + 1} failed:`, e);
				/* Drain stray bytes before retry */
				await this.drainStray();
				/* Exponential backoff: 20ms, 40ms, 80ms, ... max 200ms */
				const delay = Math.min(20 * Math.pow(2, attempt), 200);
				await sleep(delay);
			}
		}
		throw new Error(
			`get_sync failed after ${STK_SYNC_RETRIES} attempts`
		);
	}

	private async getSignature(): Promise<Uint8Array> {
		const cmd = new Uint8Array([STK_READ_SIGN, CRC_EOP]);
		const resp = await this.sendAndExpect(cmd, 3, STK_CMD_TIMEOUT_MS, true);
		if (resp.length < 3) {
			throw new Error(
				`signature response too short: got ${resp.length} bytes, expected 3`
			);
		}
		console.log(
			`[USB] signature: ${Array.from(resp)
				.map((b) => '0x' + b.toString(16).padStart(2, '0'))
				.join(' ')}`
		);
		return resp;
	}

	private async enterProgmode(): Promise<void> {
		const cmd = new Uint8Array([STK_ENTER_PROGMODE, CRC_EOP]);
		await this.sendAndExpect(cmd, 0, STK_CMD_TIMEOUT_MS, true);
		console.log('[USB] entered programming mode');
	}

	private async loadAddress(wordAddr: number): Promise<void> {
		const cmd = new Uint8Array([
			STK_LOAD_ADDRESS,
			wordAddr & 0xff,
			(wordAddr >> 8) & 0xff,
			CRC_EOP
		]);
		await this.sendAndExpect(cmd, 0, STK_CMD_TIMEOUT_MS, true);
	}

	private async progPage(data: Uint8Array): Promise<void> {
		const len = data.length;
		/* Header: 0x64, len_hi, len_lo, memtype 'F'(0x46). Then data, then EOP. */
		const pkt = new Uint8Array(4 + len + 1);
		pkt[0] = STK_PROG_PAGE;
		pkt[1] = (len >> 8) & 0xff;
		pkt[2] = len & 0xff;
		pkt[3] = 0x46; /* 'F' = flash */
		pkt.set(data, 4);
		pkt[4 + len] = CRC_EOP;

		await this.sendAndExpect(pkt, 0, STK_PAGE_TIMEOUT_MS, true);
	}

	private async leaveProgmode(): Promise<void> {
		const cmd = new Uint8Array([STK_LEAVE_PROGMODE, CRC_EOP]);
		/* optiboot shortens WDT and resets; STK_OK may be absent */
		try {
			await this.sendAndExpect(cmd, 0, STK_LEAVE_TIMEOUT_MS, false);
		} catch (e) {
			console.log(
				'[USB] leave_progmode did not reply (expected on optiboot):',
				e
			);
			/* Treat as success — optiboot intentionally WDT-resets */
		}
	}

	/* ── Flash ─────────────────────────────────────────────────── */

	private async flashBuffer(
		buffer: Uint8Array,
		onProgress: (p: DeployProgress) => void
	): Promise<void> {
		const pageSize = ATMEGA328P_PAGE_SIZE;
		const totalPages = Math.ceil(buffer.length / pageSize);

		onProgress({
			state: 'pairing',
			message: 'Merestart Arduino ke mode bootloader...',
			totalChunks: totalPages,
			completedChunks: 0
		});

		/* ── Ensure port is at flash baud rate (I4) ── */
		this.stopSerialMonitor();
		await this.stopReaderWriter();
		if (!this.port) {
			throw new Error('Port tidak tersedia — hubungkan perangkat terlebih dahulu');
		}
		try {
			await this.port.close();
		} catch {
			/* may already be closed */
		}
		await this.port.open({
			baudRate: FLASH_BAUD,
			dataBits: 8,
			stopBits: 1,
			parity: 'none',
			flowControl: 'none'
		});
		console.log('[USB] flashBuffer: port reopened at', FLASH_BAUD);
		this.writer = this.port.writable!.getWriter();
		this.reader = this.port.readable!.getReader();

		/* 1. Auto-reset → optiboot */
		await this.resetArduino();

		/* 2. Get sync (retry within optiboot ~1s window) */
		onProgress({
			state: 'flashing',
			message: 'Sinkronisasi dengan bootloader...',
			totalChunks: totalPages,
			completedChunks: 0
		});
		await this.getSync();

		/* 3. Read & validate signature */
		const sig = await this.getSignature();
		if (
			sig[0] !== ATMEGA328P_SIG_0 ||
			sig[1] !== ATMEGA328P_SIG_1 ||
			sig[2] !== ATMEGA328P_SIG_2
		) {
			throw new Error(
				`signature mismatch: got ${sig[0].toString(16)} ${sig[1].toString(16)} ${sig[2].toString(16)}, ` +
					`want ${ATMEGA328P_SIG_0.toString(16)} ${ATMEGA328P_SIG_1.toString(16)} ${ATMEGA328P_SIG_2.toString(16)}`
			);
		}

		/* Track progmode for safe error recovery (I2) */
		let inProgmode = false;

		try {
			/* 4. Enter programming mode */
			await this.enterProgmode();
			inProgmode = true;

			/* 5. Program pages (word addresses = byte/2) */
			for (let page = 0; page < totalPages; page++) {
				const byteAddr = page * pageSize;
				const remaining = buffer.length - byteAddr;
				const thisLen = remaining > pageSize ? pageSize : remaining;
				const wordAddr = byteAddr / 2;

				await this.loadAddress(wordAddr);
				await this.progPage(buffer.subarray(byteAddr, byteAddr + thisLen));

				onProgress({
					state: 'flashing',
					message: `Flashing page ${page + 1}/${totalPages}`,
					totalChunks: totalPages,
					completedChunks: page + 1
				});
			}

			/* 6. Leave programming mode */
			await this.leaveProgmode();
			inProgmode = false;

			onProgress({
				state: 'success',
				message: 'Flash berhasil!',
				totalChunks: totalPages,
				completedChunks: totalPages
			});
		} catch (e) {
			/* Best-effort leave progmode to unstick the device (I2) */
			if (inProgmode) {
				try {
					await this.leaveProgmode();
				} catch {
					/* give up */
				}
			}
			onProgress({
				state: 'error',
				message: `Flash gagal: ${(e as Error).message}`,
				totalChunks: totalPages,
				completedChunks: 0
			});
			throw e;
		}
	}
}
