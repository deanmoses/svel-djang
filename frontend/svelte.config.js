import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	compilerOptions: {
		runes: true
	},
	preprocess: vitePreprocess(),
	kit: {
		adapter: adapter(),
		prerender: {
			origin: process.env.SITE_ORIGIN || 'http://localhost:5173',
			handleHttpError: ({ path, message }) => {
				// API endpoints are served by Django, not SvelteKit — ignore
				// them when the prerender crawler discovers <link rel="preload">
				// hints in prerendered pages.
				if (path.startsWith('/api/')) return;
				throw new Error(message);
			}
		}
	}
};

export default config;
