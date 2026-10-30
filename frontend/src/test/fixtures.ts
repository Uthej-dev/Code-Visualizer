import type { TraceResponse } from '../types/trace';
import factorial from './fixtures/factorial.json';
import modifyList from './fixtures/modify-list.json';
import runtimeError from './fixtures/error.json';
import syntaxError from './fixtures/syntax-error.json';

interface Fixture {
  code: string;
  trace: TraceResponse;
}

// Real traces exported from the backend engine (backend/scripts/export_fixtures.py).
export const FIXTURES = {
  factorial: factorial as unknown as Fixture,
  modifyList: modifyList as unknown as Fixture,
  runtimeError: runtimeError as unknown as Fixture,
  syntaxError: syntaxError as unknown as Fixture,
};
