import { describe, it, expect } from 'vitest';
import { normalizeText } from './util';

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
