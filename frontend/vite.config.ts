import { defineConfig } from 'vite';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			'/api/': {
				target: 'http://127.0.0.1:8000',
				changeOrigin: true
			},
			'/admin': {
				target: 'http://127.0.0.1:8000',
				changeOrigin: true
			},
			'/media/': {
				target: 'http://127.0.0.1:8000',
				changeOrigin: true
			},
			'/static/': {
				target: 'http://127.0.0.1:8000',
				changeOrigin: true
			}
		}
	}
});
