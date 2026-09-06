import { describe, it, expect, vi } from 'vitest';
import { deleteEntry, renameEntry } from './contentEditor';

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