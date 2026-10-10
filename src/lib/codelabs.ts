// Code labs live in src/content/codelabs/<id>/ with README.md (or README.mdx, which may use the figure
// components), starter.py, solution.py and check.py. Server side only: the browser gets each lab as props.
const raw = import.meta.glob('../content/codelabs/*/*.py', { eager: true, query: '?raw', import: 'default' }) as Record<string, string>;
const readmes = import.meta.glob('../content/codelabs/*/README.md', { eager: true }) as Record<string, { compiledContent: () => Promise<string> | string; frontmatter: Record<string, any> }>;
const mdxReadmes = import.meta.glob('../content/codelabs/*/README.mdx', { eager: true }) as Record<string, { default: any; frontmatter: Record<string, any> }>;

export interface CodeLabDef { id: string; title: string; html: string; starter: string; solution: string; check: string; realModel: boolean }

const ids = new Set([...Object.keys(readmes), ...Object.keys(mdxReadmes)].map((p) => p.split('/').at(-2)!));
export const CODELABS: Record<string, CodeLabDef> = {};
for (const id of ids) {
  const get = (f: string) => raw[`../content/codelabs/${id}/${f}`];
  const md = readmes[`../content/codelabs/${id}/README.md`] ?? mdxReadmes[`../content/codelabs/${id}/README.mdx`];
  for (const f of ['starter.py', 'solution.py', 'check.py']) if (get(f) === undefined) throw new Error(`codelab ${id}: missing ${f}`);
  CODELABS[id] = {
    id, title: md.frontmatter.title ?? id, html: '', // filled by codelabHtml(): compiledContent() is async since Astro 5
    starter: get('starter.py'), solution: get('solution.py'), check: get('check.py'),
    realModel: md.frontmatter.realModel !== false,
  };
}

/** The lab's README.md rendered to HTML, for the instructions pane ('' when the lab uses README.mdx). */
export async function codelabHtml(id: string): Promise<string> {
  const md = readmes[`../content/codelabs/${id}/README.md`];
  return md ? await md.compiledContent() : '';
}

/** The README.mdx component, when the lab has one; the page renders it with the figure components. */
export const codelabContent = (id: string) => mdxReadmes[`../content/codelabs/${id}/README.mdx`]?.default;

export { AGENTKIT } from './agentkit';
