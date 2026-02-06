import type { PageLoad } from './$types';
import { getPost } from '$lib/utils/blog';
import { error } from '@sveltejs/kit';

export const load: PageLoad = async ({ params }) => {
	const post = await getPost(params.slug);

	if (!post) {
		throw error(404, 'Post not found');
	}

	return { post };
};
