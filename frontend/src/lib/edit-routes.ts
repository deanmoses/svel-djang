export function getEditRedirectHref(
	resource: string,
	currentSlug: string,
	updatedSlug: string,
	section?: string
): string | null {
	if (!updatedSlug || updatedSlug === currentSlug) return null;
	const base = `/${resource}/${updatedSlug}/edit`;
	return section ? `${base}/${section}` : base;
}
