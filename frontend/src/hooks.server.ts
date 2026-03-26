/**
 * SvelteKit server hook — proxies /api/* requests to the Flask backend.
 *
 * Uses API_BACKEND env var (set in podman-compose.yml).
 * Falls back to http://elemes:5000, then tries container IP resolution.
 */

import type { Handle } from '@sveltejs/kit';
import { execSync } from 'child_process';

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

	if (isApi || isAsset) {
		const backendPath = isApi
			? event.url.pathname.replace(/^\/api/, '')
			: event.url.pathname; // /assets/* kept as-is
		const backendUrl = `${API_BACKEND}${backendPath}${event.url.search}`;

		try {
			const headers: Record<string, string> = {};
			const contentType = event.request.headers.get('content-type');
			if (contentType) headers['content-type'] = contentType;
			const accept = event.request.headers.get('accept');
			if (accept) headers['accept'] = accept;

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

			return new Response(body, {
				status: res.status,
				headers: { 'content-type': resContentType },
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
