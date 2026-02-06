export interface BlogPost {
	slug: string;
	title: string;
	description: string;
	date: string;
	author: string;
	category: string;
	tags: string[];
	image?: string;
	draft?: boolean;
}

import type { Component } from 'svelte';

export interface BlogPostWithContent extends BlogPost {
	content: Component;
}

type MdModule = {
	default: Component;
	metadata: Omit<BlogPost, 'slug'>;
};

export async function getAllPosts(): Promise<BlogPost[]> {
	const modules = import.meta.glob<MdModule>('/src/lib/content/blog/*.md', { eager: true });

	const posts = Object.entries(modules)
		.map(([path, module]) => {
			const slug = path.split('/').pop()?.replace('.md', '') ?? '';
			return {
				slug,
				...module.metadata
			};
		})
		.filter((post) => !post.draft)
		.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

	return posts;
}

export async function getPost(slug: string): Promise<BlogPostWithContent | null> {
	try {
		const module = (await import(`../content/blog/${slug}.md`)) as MdModule;
		return {
			slug,
			content: module.default,
			...module.metadata
		};
	} catch {
		return null;
	}
}

export function formatDate(dateString: string): string {
	return new Date(dateString).toLocaleDateString('en-US', {
		year: 'numeric',
		month: 'long',
		day: 'numeric'
	});
}
