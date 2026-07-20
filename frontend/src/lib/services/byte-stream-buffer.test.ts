import { describe, it, expect } from 'vitest';
import { ByteStreamBuffer } from './byte-stream-buffer';

describe('ByteStreamBuffer', () => {
	it('readExact resolves when enough bytes already buffered', async () => {
		const buf = new ByteStreamBuffer();
		buf.push(new Uint8Array([0x14, 0x10]));
		const out = await buf.readExact(2, 100);
		expect(Array.from(out)).toEqual([0x14, 0x10]);
	});

	it('readExact resolves when bytes arrive after the call', async () => {
		const buf = new ByteStreamBuffer();
		const p = buf.readExact(2, 200);
		setTimeout(() => buf.push(new Uint8Array([0x14])), 20);
		setTimeout(() => buf.push(new Uint8Array([0x10])), 40);
		const out = await p;
		expect(Array.from(out)).toEqual([0x14, 0x10]);
	});

	it('readExact rejects on timeout without consuming future bytes', async () => {
		const buf = new ByteStreamBuffer();
		await expect(buf.readExact(1, 30)).rejects.toThrow(/timeout/);
		// Byte yang datang setelah timeout tetap tersimpan, tidak hilang.
		buf.push(new Uint8Array([0x14]));
		const out = await buf.readExact(1, 50);
		expect(Array.from(out)).toEqual([0x14]);
	});

	it('partial bytes before timeout remain buffered for next read', async () => {
		const buf = new ByteStreamBuffer();
		buf.push(new Uint8Array([0x14]));
		await expect(buf.readExact(2, 30)).rejects.toThrow(/timeout/);
		buf.push(new Uint8Array([0x10]));
		// 0x14 yang belum terpakai harus masih ada → total [0x14,0x10].
		const out = await buf.readExact(2, 50);
		expect(Array.from(out)).toEqual([0x14, 0x10]);
	});

	it('readAvailable drains everything currently buffered', () => {
		const buf = new ByteStreamBuffer();
		buf.push(new Uint8Array([1, 2, 3]));
		const out = buf.readAvailable();
		expect(Array.from(out)).toEqual([1, 2, 3]);
		expect(buf.length).toBe(0);
	});

	it('clear empties the buffer', () => {
		const buf = new ByteStreamBuffer();
		buf.push(new Uint8Array([1, 2, 3]));
		buf.clear();
		expect(buf.length).toBe(0);
	});

	it('onData fires for each pushed chunk', () => {
		const buf = new ByteStreamBuffer();
		const seen: number[] = [];
		buf.onData = (chunk) => seen.push(...chunk);
		buf.push(new Uint8Array([5, 6]));
		buf.push(new Uint8Array([7]));
		expect(seen).toEqual([5, 6, 7]);
	});
});
