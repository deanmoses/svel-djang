import { defineConfig } from 'vitest/config';
import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';

export default defineConfig({
	plugins: [sveltekit(), svelteTesting()],
	resolve: process.env.VITEST ? { conditions: ['browser'] } : undefined,
	test: {
		projects: [
			{
				extends: true,
				test: {
					name: 'unit',
					include: ['src/**/*.{test,spec}.{js,ts}'],
					exclude: ['src/**/*.dom.test.ts']
				}
			},
			{
				extends: true,
				test: {
					name: 'dom',
					environment: 'jsdom',
					include: ['src/**/*.dom.test.ts'],
					setupFiles: ['src/tests/setup-dom.ts']
				}
			}
		]
	}
});
