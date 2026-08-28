/**
 * Polyfill worker_threads.markAsUncloneable untuk kompatibilitas Node 20
 * dengan isomorphic-dompurify/jsdom/undici.
 *
 * Root Cause:
 * isomorphic-dompurify@3.23.0 -> jsdom@30.0.1 -> undici@8.10.0 memanggil
 * `markAsUncloneable` dari `node:worker_threads`. Pada Node 20 runtime (v20.20.2),
 * method ini belum ada (ditambahkan pada Node 22+), menyebabkan
 * `TypeError: webidl.util.markAsUncloneable is not a function` saat SSR.
 *
 * Catatan:
 * File ini adalah helper TypeScript/ESM (import-time). Terdapat juga salinan CJS di
 * `frontend/node-polyfill.cjs` yang digunakan khusus untuk `NODE_OPTIONS="--require ..."`
 * pada Docker container (require-time sebelum entrypoint Node).
 *
 * TODO: hapus polyfill ini kalau isomorphic-dompurify/jsdom sudah rilis versi
 * yang kompatibel penuh dengan Node 20 tanpa markAsUncloneable, atau base image
 * Docker sudah di-upgrade ke Node 22+.
 */
export function patchWorkerThreadsCompat(): void {
	try {
		// eslint-disable-next-line @typescript-eslint/no-require-imports
		const wt = require('node:worker_threads');
		if (wt && typeof wt.markAsUncloneable === 'undefined') {
			wt.markAsUncloneable = () => {};
		}
	} catch {
		// ignore - bukan environment Node (misal di browser runtime)
	}
}
