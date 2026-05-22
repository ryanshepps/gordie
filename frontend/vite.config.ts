import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
	const env = loadEnv(mode, '.', '');
	const extraHosts = (env.VITE_ALLOWED_HOSTS ?? '')
		.split(',')
		.map((host) => host.trim())
		.filter(Boolean);

	return {
		plugins: [sveltekit()],
		server: {
			allowedHosts: extraHosts.length > 0 ? extraHosts : undefined
		}
	};
});
