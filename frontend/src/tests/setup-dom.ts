// DOM test setup — loaded only by the "dom" vitest project.

import '@testing-library/jest-dom/vitest';

// jsdom does not implement scrollIntoView
Element.prototype.scrollIntoView ??= function () {};

// jsdom stubs execCommand but it doesn't work. Override unconditionally
// to return false, which triggers MarkdownTextArea's manual fallback path.
document.execCommand = () => false;

// jsdom doesn't implement matchMedia. `createIsMobileFlag` reads it at
// module-eval time for a correct first-paint value, so any test that
// touches a detail layout needs it defined.
window.matchMedia ??= (() => ({
	matches: false,
	addEventListener: () => {},
	removeEventListener: () => {},
	addListener: () => {},
	removeListener: () => {},
	dispatchEvent: () => false,
	media: '',
	onchange: null
})) as unknown as typeof window.matchMedia;
