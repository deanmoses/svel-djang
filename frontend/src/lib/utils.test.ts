import { describe, it, expect } from 'vitest';
import { formatYearRange, normalizeText } from './utils';

describe('normalizeText', () => {
	it('lowercases text', () => {
		expect(normalizeText('Hello World')).toBe('hello world');
	});

	it('strips diacritics', () => {
		expect(normalizeText('café')).toBe('cafe');
		expect(normalizeText('naïve')).toBe('naive');
	});

	it('strips punctuation so colon-separated words match', () => {
		expect(normalizeText('Ultraman: Kaiju Rumble')).toBe('ultraman kaiju rumble');
	});

	it('strips hyphens', () => {
		expect(normalizeText('Spider-Man')).toBe('spiderman');
	});

	it('strips apostrophes', () => {
		expect(normalizeText("Ripley's Believe It or Not")).toBe('ripleys believe it or not');
	});

	it('collapses multiple spaces', () => {
		expect(normalizeText('foo   bar')).toBe('foo bar');
	});

	it('trims leading and trailing whitespace', () => {
		expect(normalizeText('  hello  ')).toBe('hello');
	});

	it('handles empty string', () => {
		expect(normalizeText('')).toBe('');
	});
});

describe('formatYearRange', () => {
	it('returns range when both years present', () => {
		expect(formatYearRange(1927, 1983)).toBe('1927\u20131983');
	});

	it('returns open-ended range when only start', () => {
		expect(formatYearRange(1999, null)).toBe('1999\u2013present');
	});

	it('returns leading dash when only end', () => {
		expect(formatYearRange(null, 1950)).toBe('\u20131950');
	});

	it('returns null when neither year present', () => {
		expect(formatYearRange(null, null)).toBeNull();
		expect(formatYearRange(undefined, undefined)).toBeNull();
	});
});
