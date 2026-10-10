// The toolkit sources, written into Pyodide's filesystem before any lab code runs.
// Kept apart from codelabs.ts so the browser bundle carries only these files, not every lab.
export const AGENTKIT = import.meta.glob('../../python/agentkit_mini/*.py', { eager: true, query: '?raw', import: 'default' }) as Record<string, string>;
