import { getCollection, type CollectionEntry } from 'astro:content';
import sections from '../content/sections.json';

function repoUrl() {
  const env = typeof process !== 'undefined' ? process.env : {};
  if (env.VERCEL_GIT_REPO_OWNER && env.VERCEL_GIT_REPO_SLUG) return `https://github.com/${env.VERCEL_GIT_REPO_OWNER}/${env.VERCEL_GIT_REPO_SLUG}`;
  if (env.GITHUB_REPOSITORY) return `https://github.com/${env.GITHUB_REPOSITORY}`;
  return env.PUBLIC_REPO_URL || 'https://github.com/sakshamm21/free-agent-harness-course';
}

export const SITE = {
  name: 'Free Agent Harness',
  tagline: 'Learn AI agents by building them.',
  author: 'Sak',
  // Follows the repo automatically on Vercel and GitHub Actions builds, so a rename needs no code change.
  repo: repoUrl(),
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
