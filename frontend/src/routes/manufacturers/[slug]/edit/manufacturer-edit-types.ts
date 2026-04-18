export type ManufacturerEditView = {
	name: string;
	slug: string;
	website: string | null;
	logo_url: string | null;
	description?: {
		text?: string | null;
	} | null;
};
