import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import react from '@astrojs/react';
import sitemap from '@astrojs/sitemap';

// SITE_URL: the public URL (Vercel's production URL is picked up automatically; set it for a custom domain).
// BASE_PATH: only if the site is ever served under a sub-path.
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
  site: process.env.SITE_URL || (process.env.VERCEL_PROJECT_PRODUCTION_URL && `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`) || 'https://free-agent-harness.vercel.app',
  base,
  trailingSlash: 'always',
  integrations: [mdx(), react(), sitemap()],
  markdown: { rehypePlugins: [rehypeBaseLinks], shikiConfig: { theme: 'github-dark-dimmed' } },
});
