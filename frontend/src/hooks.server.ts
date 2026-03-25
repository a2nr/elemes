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
	if (event.url.pathname.startsWith('/api/')) {
		const backendPath = event.url.pathname.replace(/^\/api/, '');
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
			const body = await res.text();

			return new Response(body, {
				status: res.status,
				headers: {
					'content-type': res.headers.get('content-type') ?? 'application/json',
				},
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
