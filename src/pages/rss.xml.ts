import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import { lessons, SITE } from '../lib/site';

export async function GET(context: APIContext) {
  const all = await lessons();
  return rss({
    title: SITE.name,
    description: SITE.tagline,
    site: context.site!,
    items: all.map((l) => ({ title: `${l.data.order}. ${l.data.title}`, description: l.data.tagline, link: `/c/${l.id}/`, pubDate: l.data.updated })),
  });
}
