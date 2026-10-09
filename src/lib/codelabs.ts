// Code labs live in src/content/codelabs/<id>/ with README.md, starter.py, solution.py and check.py.
const raw = import.meta.glob('../content/codelabs/*/*.py', { eager: true, query: '?raw', import: 'default' }) as Record<string, string>;
const readmes = import.meta.glob('../content/codelabs/*/README.md', { eager: true }) as Record<string, { compiledContent: () => string; frontmatter: Record<string, any> }>;

export interface CodeLabDef { id: string; title: string; html: string; starter: string; solution: string; check: string; realModel: boolean }

const ids = new Set(Object.keys(readmes).map((p) => p.split('/').at(-2)!));
export const CODELABS: Record<string, CodeLabDef> = {};
for (const id of ids) {
  const get = (f: string) => raw[`../content/codelabs/${id}/${f}`];
  const md = readmes[`../content/codelabs/${id}/README.md`];
  for (const f of ['starter.py', 'solution.py', 'check.py']) if (get(f) === undefined) throw new Error(`codelab ${id}: missing ${f}`);
  CODELABS[id] = {
    id, title: md.frontmatter.title ?? id, html: md.compiledContent(),
    starter: get('starter.py'), solution: get('solution.py'), check: get('check.py'),
    realModel: md.frontmatter.realModel !== false,
  };
}

// The toolkit sources, written into Pyodide's filesystem before any lab code runs.
export const AGENTKIT = import.meta.glob('../../python/agentkit_mini/*.py', { eager: true, query: '?raw', import: 'default' }) as Record<string, string>;
