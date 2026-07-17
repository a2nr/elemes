export type DeployState =
	| 'idle'
	| 'compiling'
	| 'pairing'
	| 'transferring'
	| 'flashing'
	| 'serial_bridge'
	| 'success'
	| 'error';

export interface DeployProgress {
	state: DeployState;
	message: string;
	totalChunks: number;
	completedChunks: number;
	bytesPerSecond?: number;
}

/**
 * Abstraction untuk hardware deployer (BLE atau USB).
 * DeployTab menggunakan interface ini, switching instance berdasarkan mode.
 */
export interface HardwareDeployer {
	checkSupport(): boolean;
	readonly isConnected: boolean;
	readonly deviceName: string | null;
	pair(): Promise<void>;
	deployHex(hexContent: string, onProgress: (p: DeployProgress) => void): Promise<void>;
	deployBinary?(base64Binary: string, onProgress: (p: DeployProgress) => void): Promise<void>;
	startSerialMonitor(onData: (text: string) => void): Promise<void>;
	stopSerialMonitor(): void;
	sendSerialInput(text: string): Promise<void>;
	setBaudRate(baud: number): Promise<void>;
	resetArduino(): Promise<void>;
	disconnect(): void;
	onDisconnected(cb: () => void): void;
}

export interface BLEACKResponse {
	command: number;
	index: number;
	status: 'OK' | 'ERROR';
	message?: string;
}

export const BLE_SERVICE_UUID = '56454c58-494f-0000-0000-000000000001';
export const BLE_CHAR_FLASHING_UUID = '56454c58-494f-0000-0000-000000000002';
export const BLE_CHAR_SERIAL_UUID = '56454c58-494f-0000-0000-000000000003';

export const CMD_INIT = 0x01;
export const CMD_DATA = 0x02;
export const CMD_END = 0x03;
export const CMD_ACK = 0x04;
export const CMD_ERR = 0x05;
export const CMD_SET_BAUD = 0x06;
export const CMD_RESET = 0x07;

export const SUPPORTED_BAUD_RATES = [9600, 19200, 38400];
export const DEFAULT_BAUD_RATE = 9600;

export const CHUNK_SIZE = 240;
export const BLE_TIMEOUT_MS = 5000;
export const END_TIMEOUT_MS = 30000;
export const MAX_RETRIES = 3;
/** Unique ACK index for INIT (disambiguates from DATA chunk index 0). */
export const INIT_ACK_INDEX = 0xFFFE;
/** Unique ACK index sent by firmware after flash completes (disambiguates from INIT ACK). */
export const END_ACK_INDEX = 0xFFFF;
