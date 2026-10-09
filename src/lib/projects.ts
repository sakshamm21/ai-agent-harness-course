import { getCollection, type CollectionEntry } from 'astro:content';
export type ProjectPage = CollectionEntry<'projects'>;
export async function projectPages(slug?: string): Promise<ProjectPage[]> {
  const all = await getCollection('projects');
  return all.filter((p) => !slug || p.data.project === slug).sort((a, b) => a.data.part - b.data.part);
}
