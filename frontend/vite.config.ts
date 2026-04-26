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
				target: 'http://elemes:5000',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, '')
			},
			'/velxio/api/compile': {
				target: 'http://elemes:5000',
				changeOrigin: true,
				rewrite: (path) => '/velxio-compile'
			},
			'/assets': {
				target: 'http://elemes:5000',
				changeOrigin: true
			}
		}
	}
});
