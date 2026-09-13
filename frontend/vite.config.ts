import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	worker: {
		format: 'es'
	},
	build: {
		target: 'esnext'
	},
	ssr: {
		noExternal: ['katex']
	},
	server: {
		headers: {
			'Cross-Origin-Opener-Policy': 'same-origin',
			'Cross-Origin-Embedder-Policy': 'credentialless'
		},
		proxy: {
			'/api': {
				target: 'http://127.0.0.1:5000',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, '')
			},
			'/velxio/api/compile': {
				target: 'http://127.0.0.1:5000',
				changeOrigin: true,
				rewrite: (path) => '/velxio-compile'
			},
			'/assets': {
				target: 'http://127.0.0.1:5000',
				changeOrigin: true
			}
		}
	},
	preview: {
		headers: {
			'Cross-Origin-Opener-Policy': 'same-origin',
			'Cross-Origin-Embedder-Policy': 'credentialless'
		}
	}
});
