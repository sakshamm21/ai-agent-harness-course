import { getCollection, type CollectionEntry } from 'astro:content';
import sections from '../content/sections.json';

export const SITE = {
  name: 'Free Agent Harness',
  tagline: 'Learn AI agents by building them.',
  author: 'Sak',
  repo: 'https://github.com/sakshamm21/free-agent-harness-course',
};

export type Lesson = CollectionEntry<'lessons'>;
export { sections };

export async function lessons(): Promise<Lesson[]> {
  const all = await getCollection('lessons');
  return all.sort((a, b) => a.data.order - b.data.order);
}

export const href = (p: string) => `${import.meta.env.BASE_URL.replace(/\/$/, '')}${p}`;
export const lessonUrl = (slug: string) => href(`/c/${slug}/`);

export const PROJECTS = [
  { slug: 'nanoharness', title: 'Build Your Own Coding Agent Harness', kicker: 'Capstone 1 · flagship', blurb: 'An ~800-line Python CLI coding agent: loop, tools, permissions, sandbox, compaction, hooks, sessions, subagents and evals.' },
  { slug: 'supportbot', title: 'Customer Support Agent with RAG', kicker: 'Capstone 2', blurb: 'RAG over a help center, order and refund tools, routing, guardrails, human approval, injection tests and evals.' },
  { slug: 'deepresearch', title: 'Multi-Agent Research Assistant', kicker: 'Capstone 3', blurb: 'An orchestrator plans, parallel workers search, a verifier checks citations, a writer produces the report.' },
] as const;

/** "nanoharness/5" -> { label, url } */
export function usedInLink(ref: string) {
  const [slug, part] = ref.split('/');
  const p = PROJECTS.find((x) => x.slug === slug);
  return { label: `${slug} part ${part}`, url: href(`/p/${slug}/${part}/`), title: p?.title ?? slug };
}
