import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import react from '@astrojs/react';
import sitemap from '@astrojs/sitemap';

// SITE_URL: the public URL once deployed. BASE_PATH: set to "/free-agent-harness" for a
// GitHub Pages project site; leave unset for Cloudflare Pages or a custom domain.
const base = process.env.BASE_PATH || '/';

/** Prefix root-relative links written in Markdown/MDX (e.g. /c/agent_loop/) with the base path. */
function rehypeBaseLinks() {
  const prefix = base.replace(/\/$/, '');
  return (tree) => {
    if (!prefix) return;
    const walk = (node) => {
      if (node.type === 'element' && node.tagName === 'a' && typeof node.properties?.href === 'string' && node.properties.href.startsWith('/') && !node.properties.href.startsWith('//')) {
        node.properties.href = prefix + node.properties.href;
      }
      (node.children || []).forEach(walk);
    };
    walk(tree);
  };
}

export default defineConfig({
  site: process.env.SITE_URL || 'https://free-agent-harness.pages.dev',
  base,
  trailingSlash: 'always',
  integrations: [mdx(), react(), sitemap()],
  markdown: { rehypePlugins: [rehypeBaseLinks], shikiConfig: { theme: 'github-dark-dimmed' } },
});
