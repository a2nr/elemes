import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
	resolve: {
		alias: {
			$components: path.resolve(__dirname, 'src/lib/components'),
			$stores: path.resolve(__dirname, 'src/lib/stores'),
			$services: path.resolve(__dirname, 'src/lib/services'),
			$types: path.resolve(__dirname, 'src/lib/types'),
			$actions: path.resolve(__dirname, 'src/lib/actions'),
			$lib: path.resolve(__dirname, 'src/lib')
		}
	},
	test: {
		environment: 'node',
		include: ['src/**/*.test.ts']
	}
});

