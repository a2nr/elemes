import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	ssr: {
		noExternal: ['katex']
	},
	server: {
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
	}
});
