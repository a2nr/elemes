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
