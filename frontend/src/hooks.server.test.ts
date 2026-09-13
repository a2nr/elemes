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

	it('should pass through normal page routes to resolve() and attach COOP/COEP/CORP headers', async () => {
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
		expect(response.headers.get('Cross-Origin-Opener-Policy')).toBe('same-origin');
		expect(response.headers.get('Cross-Origin-Embedder-Policy')).toBe('credentialless');
		expect(response.headers.get('Cross-Origin-Resource-Policy')).toBe('cross-origin');
	});

	it('should read body as arrayBuffer when proxying POST requests', async () => {
		const arrayBufferMock = vi.fn().mockResolvedValue(new Uint8Array([1, 2, 3]).buffer);
		const mockEvent: any = {
			request: {
				method: 'POST',
				headers: new Headers({ 'content-type': 'application/octet-stream' }),
				arrayBuffer: arrayBufferMock
			},
			url: new URL('https://sinau-c-dev.manakin-gentoo.ts.net/api/upload')
		};

		// Mock global fetch
		const origFetch = global.fetch;
		global.fetch = vi.fn().mockResolvedValue(
			new Response(JSON.stringify({ success: true }), {
				status: 200,
				headers: { 'content-type': 'application/json' }
			})
		) as any;

		try {
			const resolve = vi.fn();
			const response = await handle({ event: mockEvent, resolve });

			expect(arrayBufferMock).toHaveBeenCalled();
			expect(global.fetch).toHaveBeenCalled();
			const fetchInit = (global.fetch as any).mock.calls[0][1];
			expect(fetchInit.body).toBeInstanceOf(ArrayBuffer);
			expect(response.status).toBe(200);
		} finally {
			global.fetch = origFetch;
		}
	});
});

