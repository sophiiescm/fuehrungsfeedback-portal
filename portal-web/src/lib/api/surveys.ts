import { api } from './client';

export type QuestionType = 'likert' | 'freitext' | 'choice' | 'nps';
export type SurveyVersionStatus = 'entwurf' | 'gesperrt';

export interface Dimension {
	id: number;
	name: string;
	sort_order: number;
	translations: Record<string, { name?: string }> | null;
}

export interface Question {
	id: number;
	dimension_id: number | null;
	type: QuestionType;
	text: string;
	scale_min: number | null;
	scale_max: number | null;
	pole_label_min: string | null;
	pole_label_max: string | null;
	scale_labels: string[] | null;
	mandatory: boolean;
	sort_order: number;
	help_text: string | null;
	options: string[] | null;
	allow_multiple: boolean;
	show_if_question_id: number | null;
	show_if_operator: string | null;
	show_if_value: string | null;
	translations: Record<string, QuestionTranslation> | null;
}

export interface QuestionTranslation {
	text?: string;
	help_text?: string;
	options?: string[];
	scale_labels?: string[];
	pole_label_min?: string;
	pole_label_max?: string;
}

export interface SurveyVersionSummary {
	id: number;
	version_number: number;
	status: SurveyVersionStatus;
	limesurvey_template_sid: number | null;
}

export interface SurveyTemplate {
	id: number;
	name: string;
	versions: SurveyVersionSummary[];
}

export interface SurveyVersionDetail {
	id: number;
	survey_template_id: number;
	survey_template_name: string;
	version_number: number;
	status: SurveyVersionStatus;
	limesurvey_template_sid: number | null;
	languages: string[];
	dimensions: Dimension[];
	questions: Question[];
}

export interface QuestionInput {
	type: QuestionType;
	text: string;
	dimension_id?: number | null;
	scale_min?: number;
	scale_max?: number;
	pole_label_min?: string;
	pole_label_max?: string;
	scale_labels?: string[];
	mandatory?: boolean;
	help_text?: string | null;
	options?: string[] | null;
	allow_multiple?: boolean;
	show_if_question_id?: number | null;
	show_if_operator?: string | null;
	show_if_value?: string | null;
}

export const surveysApi = {
	listTemplates: () => api.get<SurveyTemplate[]>('/surveys/templates'),
	createTemplate: (name: string) => api.post<SurveyTemplate>('/surveys/templates', { name }),
	getVersion: (id: number) => api.get<SurveyVersionDetail>(`/surveys/versions/${id}`),
	addDimension: (versionId: number, name: string) =>
		api.post<Dimension>(`/surveys/versions/${versionId}/dimensions`, { name }),
	deleteDimension: (id: number) => api.delete<void>(`/surveys/dimensions/${id}`),
	addQuestion: (versionId: number, input: QuestionInput) =>
		api.post<Question>(`/surveys/versions/${versionId}/questions`, input),
	updateQuestion: (id: number, input: Partial<QuestionInput>) =>
		api.patch<Question>(`/surveys/questions/${id}`, input),
	deleteQuestion: (id: number) => api.delete<void>(`/surveys/questions/${id}`),
	reorder: (versionId: number, questions: { id: number; dimension_id: number | null; sort_order: number }[]) =>
		api.put<SurveyVersionDetail>(`/surveys/versions/${versionId}/reorder`, { questions }),
	clone: (versionId: number) => api.post<SurveyVersionDetail>(`/surveys/versions/${versionId}/clone`),
	setLanguages: (versionId: number, languages: string[]) =>
		api.put<{ languages: string[] }>(`/surveys/versions/${versionId}/languages`, { languages }),
	setQuestionTranslation: (id: number, lang: string, body: QuestionTranslation) =>
		api.put(`/surveys/questions/${id}/translations/${lang}`, body),
	setDimensionTranslation: (id: number, lang: string, name: string) =>
		api.put(`/surveys/dimensions/${id}/translations/${lang}`, { name }),
	autoTranslate: (versionId: number, lang: string) =>
		api.post<{ translated: number }>(`/surveys/versions/${versionId}/translate?lang=${lang}`),
	transfer: (versionId: number) =>
		api.post<{ limesurvey_template_sid: number }>(`/surveys/versions/${versionId}/transfer`)
};
