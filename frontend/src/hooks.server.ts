/**
 * SvelteKit server hook — proxies /api/* requests to the Flask backend.
 *
 * Uses API_BACKEND env var (set in podman-compose.yml).
 * Falls back to http://127.0.0.1:5000 — all services share the
 * elemes-ts network namespace, so the backend lives on localhost.
 */

import { patchWorkerThreadsCompat } from '$lib/services/markdown/nodeCompat';
patchWorkerThreadsCompat();

import type { Handle } from '@sveltejs/kit';

function resolveBackend(): string {
	const env = process.env.API_BACKEND;
	if (env) return env;
	return 'http://127.0.0.1:5000';
}

const API_BACKEND = resolveBackend();

export const handle: Handle = async ({ event, resolve }) => {
	console.log(`[hooks] ${event.request.method} ${event.url.pathname} (referer: ${event.request.headers.get('referer')})`);

	// Redirect /editor or /editor/ to /velxio/editor
	if (event.url.pathname === '/editor' || event.url.pathname === '/editor/' || event.url.pathname.startsWith('/editor/')) {
		return Response.redirect(`${event.url.origin}/velxio/editor${event.url.search}`, 302);
	}

	// Proxy /api/* and /assets/* to Flask backend
	const isApi = event.url.pathname.startsWith('/api/');
	const isAsset = event.url.pathname.startsWith('/assets/');
	const isVelxioCompile = event.url.pathname === '/velxio/api/compile' || event.url.pathname === '/velxio/api/compile/';

	if (isApi || isAsset || isVelxioCompile) {
		let backendPath = '';
		if (isVelxioCompile) {
			backendPath = '/velxio-compile/';
		} else if (isApi) {
			backendPath = event.url.pathname.replace(/^\/api/, '');
		} else {
			backendPath = event.url.pathname;
		}

		const backendUrl = `${API_BACKEND}${backendPath}${event.url.search}`;

		try {
			const headers: Record<string, string> = {};
			const contentType = event.request.headers.get('content-type');
			if (contentType) headers['content-type'] = contentType;
			const accept = event.request.headers.get('accept');
			if (accept) headers['accept'] = accept;
			const cookie = event.request.headers.get('cookie');
			if (cookie) headers['cookie'] = cookie;

			const init: RequestInit = {
				method: event.request.method,
				headers,
			};

			if (event.request.method !== 'GET' && event.request.method !== 'HEAD') {
				init.body = await event.request.arrayBuffer();
			}

			const res = await fetch(backendUrl, init);

			// Use arrayBuffer for binary content (images), text for API JSON
			const resContentType = res.headers.get('content-type') ?? 'application/json';
			const isBinary = !resContentType.startsWith('text/') && !resContentType.includes('json');
			const body = isBinary ? await res.arrayBuffer() : await res.text();

			const resHeaders: Record<string, string> = { 'content-type': resContentType };
			const setCookie = res.headers.get('set-cookie');
			if (setCookie) resHeaders['set-cookie'] = setCookie;

			return new Response(body, {
				status: res.status,
				headers: resHeaders,
			});
		} catch (err: any) {
			// adapter-node melempar SvelteKitError saat body POST melebihi
			// BODY_SIZE_LIMIT — bukan berarti backend mati. Laporkan sebagai 413
			// dengan pesan yang jelas, jangan 502 "Backend tidak tersedia".
			const isBodyTooLarge =
				err?.status === 413 || /exceeds limit/i.test(String(err?.message ?? ''));
			if (isBodyTooLarge) {
				console.warn(`[hooks] Body too large for ${event.request.method} ${event.url.pathname}`);
				return new Response(
					JSON.stringify({
						success: false,
						error: 'Payload too large',
						message: 'Ukuran file terlalu besar (maksimum 5 MiB per asset)'
					}),
					{
						status: 413,
						headers: { 'content-type': 'application/json' }
					}
				);
			}
			console.error(`API proxy error (${backendUrl}):`, err);
			return new Response(JSON.stringify({ success: false, error: 'Backend unavailable', message: 'Backend tidak tersedia' }), {
				status: 502,
				headers: { 'content-type': 'application/json' },
			});
		}
	}

	const response = await resolve(event);
	response.headers.set('Cross-Origin-Opener-Policy', 'same-origin');
	response.headers.set('Cross-Origin-Embedder-Policy', 'credentialless');
	response.headers.set('Cross-Origin-Resource-Policy', 'cross-origin');
	return response;
};
