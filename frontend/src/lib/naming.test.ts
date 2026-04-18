import { describe, expect, it } from 'vitest';
import { normalizeTitleName } from './naming';
import fixture from '../../../docs/fixtures/normalize_title_name_cases.json';

// Shared parity fixture with backend/apps/catalog/tests/test_naming.py. Any
// change to the normalization rule updates the JSON once and both suites
// re-run against the new table.
const CASES = fixture.cases as [string, string][];

describe('normalizeTitleName', () => {
	it.each(CASES)('normalizes %j → %j', (raw, expected) => {
		expect(normalizeTitleName(raw)).toBe(expected);
	});
});
