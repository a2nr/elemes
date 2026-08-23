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