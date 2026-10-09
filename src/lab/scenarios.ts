import type { Scenario } from './types';
import { ScenarioSchema } from './schema';

const files = import.meta.glob('../content/scenarios/*.json', { eager: true, import: 'default' });

export const SCENARIOS: Record<string, Scenario> = Object.fromEntries(
  Object.entries(files).map(([path, json]) => {
    const parsed = ScenarioSchema.safeParse(json);
    if (!parsed.success) throw new Error(`Invalid scenario ${path}: ${parsed.error.message}`);
    return [parsed.data.id, parsed.data as Scenario];
  }),
);
