# Gordie — Marketing Website

SvelteKit site deployed to Cloudflare Pages.

## Local Development

```sh
pnpm install
pnpm dev
```

Open [http://localhost:5173](http://localhost:5173).

## Build

```sh
pnpm build
pnpm preview  # preview production build locally
```

## Blog

Add `.md` files to `src/lib/content/blog/` with frontmatter:

```yaml
---
title: "Post Title"
description: "Short description for SEO."
date: "2025-02-05"
author: "Gordie Team"
category: "Strategy"
tags: ["strategy", "tips"]
draft: false
---
```

## Project Structure

```
src/
├── routes/
│   ├── +page.svelte            # Landing page
│   ├── features/               # Features + FAQ
│   ├── how-it-works/           # Setup guide
│   ├── blog/                   # Blog index + [slug]
│   ├── signup/                 # Form action → Worker → Flask
│   ├── privacy/                # Privacy policy
│   ├── terms/                  # Terms of service
│   ├── sitemap.xml/            # Dynamic sitemap
│   └── rss.xml/                # RSS feed
├── lib/
│   ├── components/             # Header, Footer, SEOHead, SignupForm, etc.
│   ├── content/blog/           # Markdown blog posts
│   └── utils/blog.ts           # Blog loading utilities
└── app.css                     # Global styles
```
