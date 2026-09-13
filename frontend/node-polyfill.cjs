/**
 * Polyfill worker_threads.markAsUncloneable untuk Node 20 runtime compatibility (undici/jsdom).
 *
 * Catatan:
 * File CJS ini dimuat via NODE_OPTIONS="--require /app/node-polyfill.cjs" di Docker runner
 * (require-time sebelum entrypoint Node dievaluasi).
 * Untuk penggunaan import-time di TypeScript/ESM, lihat src/lib/services/markdown/nodeCompat.ts.
 */
try {
	const wt = require('node:worker_threads');
	if (wt && typeof wt.markAsUncloneable === 'undefined') {
		wt.markAsUncloneable = () => {};
	}
} catch {
	// ignore
}

try {
	const http = require('node:http');
	const origWriteHead = http.ServerResponse.prototype.writeHead;
	http.ServerResponse.prototype.writeHead = function(statusCode, reason, obj) {
		let headers = typeof reason === 'object' && reason !== null ? reason : obj;
		if (headers && typeof headers === 'object' && !Array.isArray(headers)) {
			if (!headers['Cross-Origin-Resource-Policy'] && !headers['cross-origin-resource-policy']) {
				headers['Cross-Origin-Resource-Policy'] = 'cross-origin';
			}
			if (!headers['Cross-Origin-Embedder-Policy'] && !headers['cross-origin-embedder-policy']) {
				headers['Cross-Origin-Embedder-Policy'] = 'credentialless';
			}
			if (!headers['Cross-Origin-Opener-Policy'] && !headers['cross-origin-opener-policy']) {
				headers['Cross-Origin-Opener-Policy'] = 'same-origin';
			}
		}
		try {
			if (!this.hasHeader('cross-origin-resource-policy')) {
				this.setHeader('Cross-Origin-Resource-Policy', 'cross-origin');
			}
			if (!this.hasHeader('cross-origin-embedder-policy')) {
				this.setHeader('Cross-Origin-Embedder-Policy', 'credentialless');
			}
			if (!this.hasHeader('cross-origin-opener-policy')) {
				this.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
			}
		} catch {}
		return origWriteHead.apply(this, arguments);
	};
} catch {
	// ignore
}
