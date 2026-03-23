import type { components } from '$lib/api/schema';

type AddressSchema = components['schemas']['AddressSchema'];

export type LocationPart = {
	text: string;
	href?: string;
};

export function buildLocationParts(addr: AddressSchema): LocationPart[] {
	const parts: LocationPart[] = [];

	if (addr.city) {
		const href =
			addr.country_slug && addr.state_slug
				? `/locations/${addr.country_slug}/${addr.state_slug}/${addr.city_slug}`
				: addr.country_slug
					? `/locations/${addr.country_slug}/cities/${addr.city_slug}`
					: undefined;
		parts.push({ text: addr.city, href });
	}

	if (addr.state) {
		const href = addr.country_slug
			? `/locations/${addr.country_slug}/${addr.state_slug}`
			: undefined;
		parts.push({ text: addr.state, href });
	}

	if (addr.country) {
		parts.push({
			text: addr.country,
			href: addr.country_slug ? `/locations/${addr.country_slug}` : undefined
		});
	}

	return parts;
}
