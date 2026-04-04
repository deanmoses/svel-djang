import { describe, expect, it } from 'vitest';
import { formatValue, isDiffable } from './change-display';

describe('formatValue', () => {
	it('returns em-dash for null', () => {
		expect(formatValue(null)).toBe('\u2014');
	});

	it('returns em-dash for undefined', () => {
		expect(formatValue(undefined)).toBe('\u2014');
	});

	it('returns em-dash for empty string', () => {
		expect(formatValue('')).toBe('\u2014');
	});

	it('returns short strings verbatim', () => {
		expect(formatValue('hello')).toBe('hello');
	});

	it('truncates strings longer than 120 characters', () => {
		const long = 'a'.repeat(150);
		const result = formatValue(long);
		expect(result).toBe('a'.repeat(120) + '...');
		expect(result.length).toBe(123);
	});

	it('preserves strings of exactly 120 characters', () => {
		const exact = 'b'.repeat(120);
		expect(formatValue(exact)).toBe(exact);
	});

	it('JSON-serializes non-string values', () => {
		expect(formatValue(42)).toBe('42');
		expect(formatValue(true)).toBe('true');
		expect(formatValue({ key: 'val' })).toBe('{"key":"val"}');
	});

	it('truncates long JSON-serialized values', () => {
		const obj = { data: 'x'.repeat(200) };
		const result = formatValue(obj);
		expect(result.length).toBe(123);
		expect(result.endsWith('...')).toBe(true);
	});
});

describe('isDiffable', () => {
	it('returns true when old_value is a long string', () => {
		const change = {
			field_name: 'description',
			claim_key: 'k',
			old_value: 'a'.repeat(81),
			new_value: 'short'
		};
		expect(isDiffable(change)).toBe(true);
	});

	it('returns true when new_value is a long string', () => {
		const change = {
			field_name: 'description',
			claim_key: 'k',
			old_value: 'short',
			new_value: 'b'.repeat(81)
		};
		expect(isDiffable(change)).toBe(true);
	});

	it('returns false when both strings are short', () => {
		const change = {
			field_name: 'name',
			claim_key: 'k',
			old_value: 'short old',
			new_value: 'short new'
		};
		expect(isDiffable(change)).toBe(false);
	});

	it('returns false when old_value is null', () => {
		const change = {
			field_name: 'name',
			claim_key: 'k',
			old_value: null,
			new_value: 'a'.repeat(100)
		};
		expect(isDiffable(change)).toBe(false);
	});

	it('returns false when new_value is a number', () => {
		const change = {
			field_name: 'year',
			claim_key: 'k',
			old_value: 'a'.repeat(100),
			new_value: 1990
		};
		expect(isDiffable(change)).toBe(false);
	});

	it('returns false at exactly the 80-character boundary', () => {
		const change = {
			field_name: 'desc',
			claim_key: 'k',
			old_value: 'a'.repeat(80),
			new_value: 'b'.repeat(80)
		};
		expect(isDiffable(change)).toBe(false);
	});

	it('returns true when one string is exactly 81 characters', () => {
		const change = {
			field_name: 'desc',
			claim_key: 'k',
			old_value: 'a'.repeat(81),
			new_value: 'short'
		};
		expect(isDiffable(change)).toBe(true);
	});
});
