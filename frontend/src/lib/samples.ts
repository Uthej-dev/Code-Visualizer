import type { Sample } from '../types/trace';
import manifest from '@shared/samples/manifest.json';

// Samples are bundled from shared/samples so the app works before the backend
// answers; the backend serves the same files for its own tests.
const sources = import.meta.glob('@shared/samples/*.py', { query: '?raw', import: 'default', eager: true }) as Record<
  string,
  string
>;

interface ManifestEntry {
  id: string;
  file: string;
  title: string;
  description: string;
  concepts: string[];
}

export const SAMPLES: Sample[] = (manifest as ManifestEntry[]).map((entry) => {
  const key = Object.keys(sources).find((path) => path.endsWith(`/${entry.file}`));
  return {
    id: entry.id,
    title: entry.title,
    description: entry.description,
    concepts: entry.concepts,
    code: key ? sources[key] : '',
  };
});

export const DEFAULT_SAMPLE = SAMPLES.find((s) => s.id === 'add') ?? SAMPLES[0];
