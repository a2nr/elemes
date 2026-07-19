/**
 * FIFO byte buffer for Web Serial reads.
 *
 * A single external pump loop is the ONLY caller of reader.read() and feeds
 * bytes here via push(). Consumers (readExact, drain, serial monitor) read
 * from this buffer and never touch reader.read() directly — eliminating the
 * orphaned-read race that dropped optiboot's INSYNC/OK replies.
 */
export class ByteStreamBuffer {
	/** Optional hook: called synchronously with every pushed chunk (serial monitor). */
	onData: ((chunk: Uint8Array) => void) | null = null;

	private chunks: Uint8Array[] = [];
	private totalLen = 0;
	/** Waiters parked in readExact, notified on push. */
	private waiters: Array<() => void> = [];

	get length(): number {
		return this.totalLen;
	}

	/** Feed bytes from the pump loop. */
	push(chunk: Uint8Array): void {
		if (chunk.length > 0) {
			this.chunks.push(chunk);
			this.totalLen += chunk.length;
			const waiters = this.waiters;
			this.waiters = [];
			for (const w of waiters) w();
		}
		/* Fire onData even for empty chunk? No — only real data. */
		if (chunk.length > 0 && this.onData) this.onData(chunk);
	}

	/** Remove and return all currently buffered bytes (non-blocking). */
	readAvailable(): Uint8Array {
		return this.take(this.totalLen);
	}

	/** Discard everything buffered. */
	clear(): void {
		this.chunks = [];
		this.totalLen = 0;
	}

	/**
	 * Resolve with exactly `len` bytes, or reject after `timeoutMs`.
	 * Bytes already buffered are consumed immediately; otherwise we park a
	 * waiter until enough arrive or the deadline passes. On timeout, any
	 * bytes shorter than `len` REMAIN buffered for the next call.
	 */
	readExact(len: number, timeoutMs: number): Promise<Uint8Array> {
		return new Promise<Uint8Array>((resolve, reject) => {
			const deadline = Date.now() + timeoutMs;

			const attempt = () => {
				if (this.totalLen >= len) {
					resolve(this.take(len));
					return;
				}
				const remaining = deadline - Date.now();
				if (remaining <= 0) {
					reject(new Error(`read timeout: got ${this.totalLen}/${len}`));
					return;
				}
				let timer: ReturnType<typeof setTimeout>;
				const onPush = () => {
					clearTimeout(timer);
					attempt();
				};
				timer = setTimeout(() => {
					/* Remove our waiter so a late push doesn't call a dead cb. */
					this.waiters = this.waiters.filter((w) => w !== onPush);
					attempt();
				}, remaining);
				this.waiters.push(onPush);
			};

			attempt();
		});
	}

	/** Pull up to `n` bytes off the front of the queue. */
	private take(n: number): Uint8Array {
		const want = Math.min(n, this.totalLen);
		const out = new Uint8Array(want);
		let filled = 0;
		while (filled < want && this.chunks.length > 0) {
			const head = this.chunks[0];
			const need = want - filled;
			if (head.length <= need) {
				out.set(head, filled);
				filled += head.length;
				this.chunks.shift();
			} else {
				out.set(head.subarray(0, need), filled);
				this.chunks[0] = head.subarray(need);
				filled += need;
			}
		}
		this.totalLen -= want;
		return out;
	}
}
