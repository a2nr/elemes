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

	it('should return 413 with size message when body exceeds adapter limit', async () => {
		// SvelteKitError dari adapter-node saat body POST melebihi BODY_SIZE_LIMIT.
		// Proxy harus balas 413 dengan pesan ukuran — bukan 502 "Backend tidak tersedia".
		const arrayBufferMock = vi.fn().mockRejectedValue(
			Object.assign(new Error('Content-length of 947488 exceeds limit of 524288 bytes.'), { status: 413 })
		);
		const mockEvent: any = {
			request: {
				method: 'POST',
				headers: new Headers({ 'content-type': 'application/json' }),
				arrayBuffer: arrayBufferMock
			},
			url: new URL('https://sinau-c-dev.manakin-gentoo.ts.net/api/content/assets/upload')
		};

		const origFetch = global.fetch;
		global.fetch = vi.fn() as any;

		try {
			const resolve = vi.fn();
			const response = await handle({ event: mockEvent, resolve });

			expect(response.status).toBe(413);
			const body = await response.json();
			expect(body.success).toBe(false);
			expect(body.message).toMatch(/terlalu besar/i);
			// Tidak boleh dikirim ke backend sama sekali
			expect(global.fetch).not.toHaveBeenCalled();
		} finally {
			global.fetch = origFetch;
		}
	});

	it('should still return 502 for ordinary network errors (not 413)', async () => {
		// Regression guard: error jaringan biasa (fetch failed) TIDAK Boleh
		// diklasifikasikan 413 — harus tetap 502 "Backend tidak tersedia".
		const arrayBufferMock = vi.fn().mockRejectedValue(new TypeError('fetch failed'));
		const mockEvent: any = {
			request: {
				method: 'POST',
				headers: new Headers({ 'content-type': 'application/json' }),
				arrayBuffer: arrayBufferMock
			},
			url: new URL('https://sinau-c-dev.manakin-gentoo.ts.net/api/content/assets/upload')
		};

		const origFetch = global.fetch;
		global.fetch = vi.fn() as any;

		try {
			const resolve = vi.fn();
			const response = await handle({ event: mockEvent, resolve });

			expect(response.status).toBe(502);
			const body = await response.json();
			expect(body.success).toBe(false);
			expect(body.message).toBe('Backend tidak tersedia');
			expect(global.fetch).not.toHaveBeenCalled();
		} finally {
			global.fetch = origFetch;
		}
	});

	it('should return 413 when error has status 413 even without "exceeds limit" message', async () => {
		// Deteksi via err.status === 413 harus bekerja tanpa regex pesan
		// (pesan library bisa berubah; status code adalah kontrak).
		const arrayBufferMock = vi.fn().mockRejectedValue(
			Object.assign(new Error('request body too large'), { status: 413 })
		);
		const mockEvent: any = {
			request: {
				method: 'POST',
				headers: new Headers({ 'content-type': 'application/json' }),
				arrayBuffer: arrayBufferMock
			},
			url: new URL('https://sinau-c-dev.manakin-gentoo.ts.net/api/content/assets/upload')
		};

		const origFetch = global.fetch;
		global.fetch = vi.fn() as any;

		try {
			const resolve = vi.fn();
			const response = await handle({ event: mockEvent, resolve });

			expect(response.status).toBe(413);
			const body = await response.json();
			expect(body.success).toBe(false);
			expect(body.message).toMatch(/terlalu besar/i);
		} finally {
			global.fetch = origFetch;
		}
	});

	it('should add restrictive CSP when proxying SVG assets (stored-XSS mitigasi)', async () => {
		// SVG bisa memuat <script>. Saat SVG dibuka langsung di tab browser,
		// script-nya jalan same-origin → bisa baca localStorage (token).
		// Proxy HARUS memberi CSP ketat — backend juga mengirim header ini,
		// tapi proxy sebelumnya hanya meneruskan content-type/set-cookie.
		const mockEvent: any = {
			request: { method: 'GET', headers: new Headers() },
			url: new URL('https://sinau-c-dev.manakin-gentoo.ts.net/assets/malware.svg')
		};
		const origFetch = global.fetch;
		global.fetch = vi.fn().mockResolvedValue(
			new Response('<svg><script>alert(1)</script></svg>', {
				status: 200,
				headers: { 'content-type': 'image/svg+xml' }
			})
		) as any;

		try {
			const resolve = vi.fn();
			const response = await handle({ event: mockEvent, resolve });
			expect(response.status).toBe(200);
			expect(response.headers.get('content-security-policy')).toBe("default-src 'none'; sandbox");
		} finally {
			global.fetch = origFetch;
		}
	});

	it('should NOT add CSP for non-SVG assets', async () => {
		const mockEvent: any = {
			request: { method: 'GET', headers: new Headers() },
			url: new URL('https://sinau-c-dev.manakin-gentoo.ts/assets/diagram.png')
		};
		const origFetch = global.fetch;
		global.fetch = vi.fn().mockResolvedValue(
			new Response('binary', { status: 200, headers: { 'content-type': 'image/png' } })
		) as any;

		try {
			const resolve = vi.fn();
			const response = await handle({ event: mockEvent, resolve });
			expect(response.status).toBe(200);
			expect(response.headers.get('content-security-policy')).toBeNull();
		} finally {
			global.fetch = origFetch;
		}
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

