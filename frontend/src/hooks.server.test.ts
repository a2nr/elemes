import { describe, it, expect, vi } from 'vitest';
import { handle } from './hooks.server';

describe('hooks.server handle', () => {
	it('should redirect /editor to /velxio/editor with 302', async () => {
		const mockEvent: any = {
			request: {
				method: 'GET',
				headers: new Headers()
			},
			url: new URL('https://sinau-c-dev.manakin-gentoo.ts.net/editor')
		};

		const resolve = vi.fn();
		const response = await handle({ event: mockEvent, resolve });

		expect(response.status).toBe(302);
		expect(response.headers.get('location')).toBe('https://sinau-c-dev.manakin-gentoo.ts.net/velxio/editor');
		expect(resolve).not.toHaveBeenCalled();
	});

	it('should redirect /editor/ with query parameters to /velxio/editor?foo=bar with 302', async () => {
		const mockEvent: any = {
			request: {
				method: 'GET',
				headers: new Headers()
			},
			url: new URL('https://sinau-c-dev.manakin-gentoo.ts.net/editor/?embed=true&desktopLayout=true')
		};

		const resolve = vi.fn();
		const response = await handle({ event: mockEvent, resolve });

		expect(response.status).toBe(302);
		expect(response.headers.get('location')).toBe('https://sinau-c-dev.manakin-gentoo.ts.net/velxio/editor?embed=true&desktopLayout=true');
		expect(resolve).not.toHaveBeenCalled();
	});

	it('should pass through normal page routes to resolve()', async () => {
		const mockEvent: any = {
			request: {
				method: 'GET',
				headers: new Headers()
			},
			url: new URL('https://sinau-c-dev.manakin-gentoo.ts.net/teacher/content')
		};

		const mockResponse = new Response('ok');
		const resolve = vi.fn().mockResolvedValue(mockResponse);

		const response = await handle({ event: mockEvent, resolve });

		expect(resolve).toHaveBeenCalledWith(mockEvent);
		expect(response).toBe(mockResponse);
	});
});
