import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const lessons = defineCollection({
  loader: glob({ pattern: '*.mdx', base: './src/content/lessons' }),
  schema: z.object({
    title: z.string(),
    section: z.enum(['foundations', 'tools', 'harness', 'memory', 'patterns', 'reliability', 'operate', 'cases']),
    order: z.number().int().min(1).max(54),
    tagline: z.string(),
    realWorld: z.string(),
    build: z.object({ type: z.enum(['lab', 'code', 'none']), scenario: z.string().optional() }),
    terms: z.array(z.object({ term: z.string(), def: z.string() })).default([]),
    usedIn: z.array(z.string()).default([]),
    readingMinutes: z.number().int().positive(),
    updated: z.coerce.date(),
    quiz: z.array(z.object({ q: z.string(), options: z.array(z.string()).min(2), answer: z.number().int().min(0), why: z.string() })).length(3),
    reading: z.array(z.object({ title: z.string(), url: z.string().url() })).default([]),
  }).strict(),
});

const projects = defineCollection({
  loader: glob({ pattern: '**/*.mdx', base: './src/content/projects' }),
  schema: z.object({
    title: z.string(),
    project: z.enum(['nanoharness', 'supportbot', 'deepresearch']),
    part: z.number().int().min(0),           // 0 = overview page
    tagline: z.string(),
    goal: z.string().optional(),
    lessons: z.array(z.string()).default([]), // lesson slugs this part draws on
    test: z.string().optional(),              // the command that proves you passed
    updated: z.coerce.date(),
  }).strict(),
});

export const collections = { lessons, projects };
