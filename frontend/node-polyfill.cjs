// Polyfill markAsUncloneable on node:worker_threads for Node 20 runtime compatibility (undici/jsdom)
try {
	const wt = require('node:worker_threads');
	if (wt && typeof wt.markAsUncloneable === 'undefined') {
		wt.markAsUncloneable = () => {};
	}
} catch {
	// ignore
}
