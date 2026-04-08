// DOM test setup — loaded only by the "dom" vitest project.

import '@testing-library/jest-dom/vitest';

// jsdom does not implement scrollIntoView
Element.prototype.scrollIntoView ??= function () {};

// jsdom stubs execCommand but it doesn't work. Override unconditionally
// to return false, which triggers MarkdownTextArea's manual fallback path.
document.execCommand = () => false;
