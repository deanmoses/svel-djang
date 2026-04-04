import { describe, it, expect } from 'vitest';
import { computeWordDiff } from './diff';

describe('computeWordDiff', () => {
	it('returns a single unchanged segment for identical strings', () => {
		const segments = computeWordDiff('hello world', 'hello world');
		expect(segments.every((s) => s.type === 'unchanged')).toBe(true);
		expect(segments.map((s) => s.text).join('')).toBe('hello world');
	});

	it('detects a word insertion', () => {
		const segments = computeWordDiff('hello world', 'hello brave world');
		const added = segments.filter((s) => s.type === 'added');
		expect(added.length).toBeGreaterThan(0);
		expect(added.map((s) => s.text).join('')).toContain('brave');
	});

	it('detects a word deletion', () => {
		const segments = computeWordDiff('hello brave world', 'hello world');
		const removed = segments.filter((s) => s.type === 'removed');
		expect(removed.length).toBeGreaterThan(0);
		expect(removed.map((s) => s.text).join('')).toContain('brave');
	});

	it('detects a word replacement', () => {
		const segments = computeWordDiff('the quick fox', 'the slow fox');
		const removed = segments.filter((s) => s.type === 'removed');
		const added = segments.filter((s) => s.type === 'added');
		expect(removed.map((s) => s.text).join('')).toContain('quick');
		expect(added.map((s) => s.text).join('')).toContain('slow');
	});

	it('handles empty old string (full insertion)', () => {
		const segments = computeWordDiff('', 'new content');
		expect(segments.every((s) => s.type === 'added')).toBe(true);
		expect(segments.map((s) => s.text).join('')).toBe('new content');
	});

	it('handles empty new string (full deletion)', () => {
		const segments = computeWordDiff('old content', '');
		expect(segments.every((s) => s.type === 'removed')).toBe(true);
		expect(segments.map((s) => s.text).join('')).toBe('old content');
	});

	it('preserves newline characters in segment text', () => {
		const old = 'line one\nline two';
		const next = 'line one\nline two\nline three';
		const segments = computeWordDiff(old, next);
		const allText = segments.map((s) => s.text).join('');
		expect(allText).toContain('\n');
		expect(allText).toBe('line one\nline two\nline three');
	});

	it('detects whitespace-only edits (added paragraph break)', () => {
		const old = 'paragraph one\nparagraph two';
		const next = 'paragraph one\n\nparagraph two';
		const segments = computeWordDiff(old, next);
		const added = segments.filter((s) => s.type === 'added');
		expect(added.length).toBeGreaterThan(0);
	});

	it('handles a realistic markdown description change', () => {
		const old =
			'The Gorgar was a groundbreaking machine released by Williams in 1979. It was the first pinball machine to feature synthesized speech.';
		const next =
			'The Gorgar was a groundbreaking machine released by Williams in 1979. It was the first pinball machine to feature synthesized speech, using a vocabulary of seven words.';
		const segments = computeWordDiff(old, next);
		const added = segments.filter((s) => s.type === 'added');
		expect(added.map((s) => s.text).join('')).toContain('vocabulary');
		// Original text is still present in unchanged segments
		const unchanged = segments.filter((s) => s.type === 'unchanged');
		expect(unchanged.map((s) => s.text).join('')).toContain('groundbreaking');
	});
});
