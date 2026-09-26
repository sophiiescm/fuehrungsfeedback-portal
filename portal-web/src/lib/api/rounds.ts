import { api } from './client';
import { auth } from '$lib/stores/auth.svelte';

export interface Round {
	id: number;
	name: string;
	survey_version_id: number;
	status: string;
	start_at: string;
	end_at: string;
	reminder_days_before_end: number[];
	report_channel: string;
	target_fachbereiche: string[] | null;
}
export interface RoundTarget {
	id: number;
	leader_name: string;
	leader_code: string;
	team_size_snapshot: number;
	evaluable: boolean;
	completed_count: number;
	open_count: number;
}
export interface Dashboard {
	round_id: number;
	status: string;
	total_invited: number;
	total_completed: number;
	response_rate: number;
	by_fachbereich: Record<string, { invited: number; completed: number; response_rate: number }>;
	targets: RoundTarget[];
}
export interface MyFeedback {
	participation_id: number;
	round_name: string;
	leader_name: string;
	status: 'offen' | 'erledigt';
	due_date: string;
	feedback_link: string | null;
	completed_date: string | null;
	survey_id: number | null;
	round_closed: boolean;
	languages: string[];
}
export interface Notification {
	id: number;
	type: string;
	title: string;
	body: string;
	read_at: string | null;
	created_at: string;
}
export interface MailTemplate {
	key: string;
	subject: string;
	body_html: string;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export async function downloadPdf(path: string, filename: string) {
	const res = await fetch(`${API_BASE}${path}`, { headers: { Authorization: `Bearer ${auth.token}` } });
	if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? 'Download fehlgeschlagen');
	const url = URL.createObjectURL(await res.blob());
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	a.click();
	URL.revokeObjectURL(url);
}

export async function downloadFile(path: string, filename: string, method: 'GET' | 'POST' = 'GET', body?: unknown) {
	const res = await fetch(`${API_BASE}${path}`, {
		method,
		headers: { Authorization: `Bearer ${auth.token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
		body: body ? JSON.stringify(body) : undefined
	});
	if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? 'Download fehlgeschlagen');
	const url = URL.createObjectURL(await res.blob());
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	a.click();
	URL.revokeObjectURL(url);
}

export const roundsApi = {
	list: () => api.get<Round[]>('/rounds'),
	create: (body: unknown) => api.post<Round>('/rounds', body),
	start: (id: number) => api.post<Round>(`/rounds/${id}/start`),
	close: (id: number) => api.post<Round>(`/rounds/${id}/close`),
	dashboard: (id: number) => api.get<Dashboard>(`/rounds/${id}/dashboard`)
};
export const feedbackApi = { mine: () => api.get<MyFeedback[]>('/feedbacks/mine') };
export const notificationsApi = {
	mine: () => api.get<Notification[]>('/notifications/mine'),
	read: (id: number) => api.post<Notification>(`/notifications/${id}/read`),
	templates: () => api.get<MailTemplate[]>('/mail-templates'),
	saveTemplate: (t: MailTemplate) =>
		api.put<MailTemplate>(`/mail-templates/${t.key}`, { subject: t.subject, body_html: t.body_html })
};
