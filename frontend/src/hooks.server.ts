/**
 * SvelteKit server hook — proxies /api/* requests to the Flask backend.
 *
 * Uses API_BACKEND env var (set in podman-compose.yml).
 * Falls back to http://elemes:5000, then tries container IP resolution.
 */

import type { Handle } from '@sveltejs/kit';

function resolveBackend(): string {
	const env = process.env.API_BACKEND;
	if (env) return env;
	return 'http://elemes:5000';
}

const API_BACKEND = resolveBackend();

export const handle: Handle = async ({ event, resolve }) => {
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
				init.body = await event.request.text();
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
		} catch (err) {
			console.error(`API proxy error (${backendUrl}):`, err);
			return new Response(JSON.stringify({ error: 'Backend unavailable' }), {
				status: 502,
				headers: { 'content-type': 'application/json' },
			});
		}
	}

	return resolve(event);
};
