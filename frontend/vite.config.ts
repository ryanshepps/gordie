import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

const extraHosts = (process.env.VITE_ALLOWED_HOSTS ?? '')
	.split(',')
	.map((h) => h.trim())
	.filter(Boolean);

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		allowedHosts: extraHosts.length > 0 ? extraHosts : undefined
	}
});
