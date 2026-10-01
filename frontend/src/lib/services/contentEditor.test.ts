import { describe, it, expect, vi } from 'vitest';
import { deleteEntry, renameEntry } from './contentEditor';
import { zipSync, strToU8 } from 'fflate';

// FileReader tidak tersedia di environment 'node' vitest; uploadAsset
// menggunakannya via fileToBase64. Polyfill minimal agar test jalan.
class MockFileReader {
	result: string | null = null;
	onload: (() => void) | null = null;
	onerror: (() => void) | null = null;
	readAsDataURL(file: Blob) {
		file.arrayBuffer().then((buf) => {
			const bytes = new Uint8Array(buf);
			let bin = '';
			bytes.forEach((b) => (bin += String.fromCharCode(b)));
			this.result = `data:application/octet-stream;base64,${btoa(bin)}`;
			this.onload?.();
		});
	}
}
if (typeof globalThis.FileReader === 'undefined') {
	(globalThis as unknown as { FileReader: unknown }).FileReader = MockFileReader;
}

describe('deleteEntry', () => {
	it('mengirim force=true saat dipanggil dengan argumen force', async () => {
		const fetchMock = vi.fn().mockResolvedValue({ json: async () => ({ success: true }) });
		global.fetch = fetchMock;

		await deleteEntry('content', 'folder_x', false, true);

		const url = fetchMock.mock.calls[0][0] as string;
		expect(url).toContain('force=true');
		expect(url).toContain('confirm_critical=false');
	});

	it('mengirim confirm_critical=true untuk file navigasi kritis', async () => {
		const fetchMock = vi.fn().mockResolvedValue({ json: async () => ({ success: true }) });
		global.fetch = fetchMock;

		await deleteEntry('content', 'home.md', true);

		const url = fetchMock.mock.calls[0][0] as string;
		expect(url).toContain('confirm_critical=true');
		expect(url).toContain('force=false');
	});

	it('mengirim query string yang benar untuk folder biasa', async () => {
		const fetchMock = vi.fn().mockResolvedValue({ json: async () => ({ success: true }) });
		global.fetch = fetchMock;

		await deleteEntry('content', 'some_folder');

		const url = fetchMock.mock.calls[0][0] as string;
		expect(url).toContain('force=false');
		expect(url).toContain('confirm_critical=false');
	});
});

describe('renameEntry', () => {
	it('mengirim rename dengan argumen standar', async () => {
		const fetchMock = vi.fn().mockResolvedValue({ json: async () => ({ success: true }) });
		global.fetch = fetchMock;

		await renameEntry('content', 'old.md', 'new.md', false);

		expect(fetchMock.mock.calls[0][1]).toMatchObject({
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
		});
	});

	it('mengirim confirm_critical=true untuk filename kritis', async () => {
		const fetchMock = vi.fn().mockResolvedValue({ json: async () => ({ success: true }) });
		global.fetch = fetchMock;

		await renameEntry('content', 'home.md', 'renamed.md', true);

		const body = JSON.parse(fetchMock.mock.calls[0][1]?.body ?? '{}');
		expect(body.confirm_critical).toBe(true);
	});
});

describe('saveDraft and publishDraft API', () => {
	it('mengirim saveDraft dengan target_path dan body', async () => {
		const { saveDraft } = await import('./contentEditor');
		const fetchMock = vi.fn().mockResolvedValue({ json: async () => ({ success: true, draft_id: 'draft-1' }) });
		global.fetch = fetchMock;

		await saveDraft('arduino/led_blink_arduino.md', 'modified body', 12345);

		expect(fetchMock).toHaveBeenCalled();
		const call = fetchMock.mock.calls[0];
		expect(call[0]).toBe('/api/content/drafts');
		expect(JSON.parse(call[1].body)).toEqual({
			target_path: 'arduino/led_blink_arduino.md',
			body: 'modified body',
			base_mtime: 12345
		});
	});

	it('mengirim publishDraft dengan draft_id ke endpoint publish', async () => {
		const { publishDraft } = await import('./contentEditor');
		const fetchMock = vi.fn().mockResolvedValue({ json: async () => ({ success: true, published_path: 'arduino/led_blink_arduino.md' }) });
		global.fetch = fetchMock;

		await publishDraft('draft-1');

		expect(fetchMock).toHaveBeenCalled();
		const call = fetchMock.mock.calls[0];
		expect(call[0]).toBe('/api/content/drafts/draft-1/publish');
		expect(call[1].method).toBe('POST');
	});
});

describe('exportBundle', () => {
	it('memanggil /api/content/export dengan credentials dan mengembalikan blob', async () => {
		const { exportBundle } = await import('./contentEditor');
		const blob = new Blob(['zip-bytes'], { type: 'application/zip' });
		global.fetch = vi.fn().mockResolvedValue(
			new Response(blob, { status: 200, headers: { 'Content-Type': 'application/zip' } }),
		);

		const result = await exportBundle();

		expect(global.fetch).toHaveBeenCalledWith('/api/content/export', { credentials: 'include' });
		expect(result.size).toBeGreaterThan(0);
	});

	it('mengirim scope param saat diberikan', async () => {
		const { exportBundle } = await import('./contentEditor');
		global.fetch = vi.fn().mockResolvedValue(
			new Response(new Blob(['x']), { status: 200 }),
		);

		await exportBundle('content');

		expect(global.fetch).toHaveBeenCalledWith('/api/content/export?scope=content', { credentials: 'include' });
	});

	it('melempar error pada respons non-ok', async () => {
		const { exportBundle } = await import('./contentEditor');
		global.fetch = vi.fn().mockResolvedValue(
			new Response(JSON.stringify({ success: false }), { status: 401 }),
		);

		await expect(exportBundle()).rejects.toThrow();
	});
});

describe('importBundle — orkestrasi per-file', () => {
	it('mengirim .md baru via tree/file, .md existing via drafts+publish, asset via upload', async () => {
		const { importBundle } = await import('./contentEditor');
		global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
			if (url.includes('/api/content/tree/folder')) {
				return Promise.resolve(new Response(JSON.stringify({ success: true }), { status: 200 }));
			}
			if (url.includes('/api/content/tree/file')) {
				return Promise.resolve(new Response(JSON.stringify({ success: true }), { status: 200 }));
			}
			if (url.includes('/publish')) {
				return Promise.resolve(new Response(JSON.stringify({ success: true }), { status: 200 }));
			}
			if (url.includes('/api/content/drafts')) {
				return Promise.resolve(new Response(JSON.stringify({ success: true, draft_id: 'd-1' }), { status: 200 }));
			}
			if (url.includes('/api/content/assets/upload')) {
				return Promise.resolve(new Response(JSON.stringify({ success: true }), { status: 200 }));
			}
			return Promise.resolve(new Response(JSON.stringify({ success: false }), { status: 404 }));
		});

		const result = await importBundle({
			contentFiles: [
				{ path: 'lesson/new.md', body: '# New\n' },
				{ path: 'lesson/existing.md', body: '# Overwrite\n' },
			],
			assetFiles: [{ path: 'img/diag.png', bytes: new Uint8Array([1, 2, 3]) }],
			mode: 'overwrite',
			existingPaths: new Set(['lesson/existing.md']),
		});

		const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls as [string, RequestInit?][];
		const bodies = calls.map(([u, i]) => [u, i?.body ? JSON.parse(String(i.body)) : null] as const);

		// folder dibuat dulu sebelum file di dalamnya
		const folderIdx = calls.findIndex(([u]) => u.includes('/api/content/tree/folder'));
		const newFileIdx = calls.findIndex(([u]) => u.includes('/api/content/tree/file'));
		expect(folderIdx).toBeGreaterThanOrEqual(0);
		expect(folderIdx).toBeLessThan(newFileIdx);

		// .md baru → tree/file dengan body sebagai template
		expect(bodies.some(([u, b]) => u.includes('/api/content/tree/file') && b?.path === 'lesson/new.md' && b?.template === '# New\n')).toBe(true);
		// .md existing → drafts lalu publish
		expect(bodies.some(([u, b]) => u.includes('/api/content/drafts') && b?.target_path === 'lesson/existing.md' && b?.base_mtime === null)).toBe(true);
		expect(calls.some(([u, i]) => u === '/api/content/drafts/d-1/publish' && i?.method === 'POST')).toBe(true);
		// asset → upload dengan folder relatif
		expect(bodies.some(([u, b]) => u.includes('/api/content/assets/upload') && b?.filename === 'diag.png' && b?.folder === 'img')).toBe(true);

		expect(result.success).toBe(true);
		expect(result.imported).toBe(3);
	});

	it('mode skip tidak menyentuh file yang sudah ada (cek client-side via existingPaths)', async () => {
		const { importBundle } = await import('./contentEditor');
		global.fetch = vi.fn().mockResolvedValue(
			new Response(JSON.stringify({ success: true }), { status: 200 }),
		);

		const result = await importBundle({
			contentFiles: [{ path: 'lesson/existing.md', body: '# x\n' }],
			assetFiles: [],
			mode: 'skip',
			existingPaths: new Set(['lesson/existing.md']),
		});

		expect(global.fetch).not.toHaveBeenCalled();
		expect(result.skipped).toBe(1);
	});

	it('berhenti pada kegagalan pertama dan melaporkan path yang gagal', async () => {
		const { importBundle } = await import('./contentEditor');
		global.fetch = vi.fn().mockResolvedValue(
			new Response(JSON.stringify({ success: false, message: 'Permission denied' }), { status: 403 }),
		);

		const result = await importBundle({
			contentFiles: [{ path: 'lesson/a.md', body: '# a\n' }],
			assetFiles: [],
			mode: 'overwrite',
		});

		expect(result.success).toBe(false);
		expect(result.failedPath).toBe('lesson/a.md');
	});
});

describe('extractBundle', () => {
	it('memisahkan content .md dan asset biner, menandai entry tidak valid', async () => {
		const { extractBundle } = await import('./contentEditor');
		const zipBytes = zipSync({
			'content/lesson/a.md': strToU8('# A\n'),
			'assets/img/diag.png': new Uint8Array([1, 2, 3]),
			'evil.sh': strToU8('#!/bin/sh\n'),
			'content/bad.txt': strToU8('x'),
			'content/../../evil.md': strToU8('# evil\n'),
		});
		const result = await extractBundle(new File([zipBytes], 'b.zip'));
		expect(result.contentFiles.map((f) => f.path)).toEqual(['lesson/a.md']);
		expect(result.assetFiles.map((f) => f.path)).toEqual(['img/diag.png']);
		expect(result.invalidEntries.sort()).toEqual(['content/../../evil.md', 'content/bad.txt', 'evil.sh']);
	});

	it('menolak bytes zip yang tidak valid', async () => {
		const { extractBundle } = await import('./contentEditor');
		await expect(extractBundle(new File([new Uint8Array([1, 2, 3])], 'b.zip'))).rejects.toThrow();
	});
});