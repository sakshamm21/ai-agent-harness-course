import { describe, expect, it } from 'vitest';
import { buildExport, mergeProgress, planImport, FORMAT } from './progress-transfer';

describe('progress transfer', () => {
  it('exports only course keys', () => {
    const f = buildExport({ 'fah-progress': '{"llm":5}', 'fah-code-x': 'print(1)', 'fah-theme': 'light', other: '1' }, new Date(0));
    expect(f.data).toEqual({ 'fah-progress': '{"llm":5}', 'fah-code-x': 'print(1)' });
    expect(f.format).toBe(FORMAT);
  });
  it('merges progress, keeping the earliest real completion time', () => {
    expect(JSON.parse(mergeProgress('{"a":200,"b":1}', '{"a":100,"b":300,"c":5}'))).toEqual({ a: 100, b: 300, c: 5 });
  });
  it('imports: merges progress, replaces code, drops unknown keys', () => {
    const file = JSON.stringify(buildExport({ 'fah-progress': '{"tokens":20}', 'fah-code-x': 'new' }));
    const tampered = file.replace('"data":{', '"data":{"evil":"x","fah-theme":"dark",');
    const { writes, completed } = planImport(tampered, { 'fah-progress': '{"llm":10}', 'fah-code-x': 'old' });
    expect(JSON.parse(writes['fah-progress'])).toEqual({ llm: 10, tokens: 20 });
    expect(writes['fah-code-x']).toBe('new');
    expect(Object.keys(writes).sort()).toEqual(['fah-code-x', 'fah-progress']);
    expect(completed).toBe(2);
  });
  it('rejects files that are not progress files', () => {
    expect(() => planImport('nope', {})).toThrow(/isn't JSON/);
    expect(() => planImport('{"data":{}}', {})).toThrow(/isn't a Free Agent Harness/);
  });
});
