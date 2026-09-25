import { api } from './client';

export interface PersonListItem {
	id: number;
	personalnummer: string;
	full_name: string;
	email: string | null;
	fachbereich: string | null;
	org_einheit: string | null;
	roles: string[];
	aktiv: boolean;
}

export interface PersonList {
	items: PersonListItem[];
	total: number;
}

export interface OrgPathEntry {
	personalnummer: string;
	full_name: string;
}

export interface PersonDetail {
	id: number;
	personalnummer: string;
	vorname: string;
	nachname: string;
	email: string | null;
	fachbereich: string | null;
	org_einheit: string | null;
	standort: string | null;
	aktiv: boolean;
	roles: string[];
	team_size: number;
	org_path: OrgPathEntry[];
}

export interface FieldChange {
	field: string;
	old: unknown;
	new: unknown;
}

export interface ChangedPerson {
	personalnummer: string;
	changes: FieldChange[];
}

export interface NewPerson {
	personalnummer: string;
	vorname: string;
	nachname: string;
	org_einheit: string;
	fachbereich: string;
}

export interface ImportDiff {
	new: NewPerson[];
	changed: ChangedPerson[];
	deactivated: string[];
	unchanged_count: number;
	issues: string[];
}

export interface ImportLog {
	id: number;
	started_at: string;
	finished_at: string | null;
	dry_run: boolean;
	status: string;
	triggered_by: string;
	summary: Record<string, unknown> | null;
}

export interface OrgTreeNode {
	personalnummer: string;
	full_name: string;
	fachbereich: string | null;
	team_size: number;
	team_too_small: boolean;
	children: OrgTreeNode[];
}

export interface ImportSchedule {
	enabled: boolean;
	cron: string;
	csv_path: string | null;
}

function buildQuery(params: Record<string, string | boolean | undefined>): string {
	const search = new URLSearchParams();
	for (const [key, value] of Object.entries(params)) {
		if (value !== undefined && value !== '') search.set(key, String(value));
	}
	const qs = search.toString();
	return qs ? `?${qs}` : '';
}

export const organisationApi = {
	listPersons: (filters: {
		q?: string;
		fachbereich?: string;
		role?: string;
		has_email?: boolean;
		only_active?: boolean;
	}) => api.get<PersonList>(`/organisation/persons${buildQuery(filters)}`),

	getPerson: (id: number) => api.get<PersonDetail>(`/organisation/persons/${id}`),

	setAdminRole: (id: number, isAdmin: boolean) =>
		api.post<PersonDetail>(`/organisation/persons/${id}/admin-role`, { is_admin: isAdmin }),

	deactivatePerson: (id: number) => api.post<PersonDetail>(`/organisation/persons/${id}/deactivate`),

	listFachbereiche: () => api.get<string[]>('/organisation/fachbereiche'),

	getTree: () => api.get<OrgTreeNode[]>('/organisation/tree'),

	listImportLogs: () => api.get<ImportLog[]>('/organisation/import/logs'),

	getImportSchedule: () => api.get<ImportSchedule>('/organisation/import/schedule'),

	setImportSchedule: (schedule: ImportSchedule) =>
		api.put<ImportSchedule>('/organisation/import/schedule', schedule)
};

async function uploadCsv(path: string, file: File): Promise<ImportDiff> {
	const formData = new FormData();
	formData.append('file', file);
	const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
	const token = localStorage.getItem('ffp_token');
	const response = await fetch(`${apiBase}${path}`, {
		method: 'POST',
		headers: token ? { Authorization: `Bearer ${token}` } : undefined,
		body: formData
	});
	if (!response.ok) {
		const body = await response.json().catch(() => ({}));
		throw new Error(body.detail ?? `Import fehlgeschlagen (${response.status})`);
	}
	return response.json();
}

export const importApi = {
	dryRun: (file: File) => uploadCsv('/organisation/import/dry-run', file),
	apply: (file: File) => uploadCsv('/organisation/import/apply', file)
};
