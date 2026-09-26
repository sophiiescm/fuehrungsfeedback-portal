<script lang="ts">
	// Formular „Automatische Runde“ (wiederkehrend, z. B. halbjährlich) – wird im Fenster der Rundenseite gezeigt.
	import { onMount } from 'svelte';
	import Button from '$lib/components/Button.svelte';
	import { api } from '$lib/api/client';
	import { surveysApi, type SurveyTemplate } from '$lib/api/surveys';

	export interface AutomationCfg {
		enabled: boolean;
		survey_version_id: number | null;
		interval_months: number;
		next_start: string | null;
		duration_days: number;
		lead_days: number;
		name_pattern: string;
		reminder_days_before_end: number[];
		report_channel: string;
		target_fachbereiche: string[] | null;
	}

	let { onsaved, oncancel }: { onsaved?: (c: AutomationCfg) => void; oncancel?: () => void } = $props();

	let cfg = $state<AutomationCfg | null>(null);
	let templates = $state<SurveyTemplate[]>([]);
	let reminders = $state('7,2');
	let error = $state('');
	let saving = $state(false);

	onMount(async () => {
		cfg = await api.get<AutomationCfg>('/rounds/automation');
		reminders = cfg.reminder_days_before_end.join(',');
		templates = await surveysApi.listTemplates();
		if (!cfg.survey_version_id) cfg.survey_version_id = templates[0]?.versions.at(-1)?.id ?? null;
		if (!cfg.next_start) {
			const d = new Date();
			d.setMonth(d.getMonth() + 1, 1);
			cfg.next_start = d.toISOString().slice(0, 10);
		}
	});

	async function save() {
		if (!cfg) return;
		error = '';
		saving = true;
		try {
			const saved = await api.put<AutomationCfg>('/rounds/automation', {
				...cfg,
				reminder_days_before_end: reminders.split(',').map((x) => Number(x.trim())).filter((x) => !isNaN(x) && x > 0)
			});
			onsaved?.(saved);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Fehler';
		} finally {
			saving = false;
		}
	}
</script>

{#if cfg}
	<p class="mb-4 text-sm" style="color: var(--text-secondary)">
		Das Portal legt die nächste Runde automatisch an, holt vorher die Teams aus SAP und startet sie zum Termin – ohne dass du daran denken musst.
	</p>
	<label class="mb-4 flex items-center gap-3 text-sm font-semibold" style="color: var(--text-primary)">
		<input type="checkbox" class="h-5 w-5" bind:checked={cfg.enabled} /> Wiederkehrende Runden automatisch anlegen
	</label>
	<div class="grid gap-3 text-sm sm:grid-cols-2" style="color: var(--text-secondary)">
		<label class="sm:col-span-2">Fragebogen
			<select bind:value={cfg.survey_version_id} class="glass-surface mt-1 w-full rounded px-3 py-2">
				<option value={null}>– wählen –</option>
				{#each templates as t (t.id)}{#each t.versions as v (v.id)}<option value={v.id}>{t.name} · Version {v.version_number}</option>{/each}{/each}
			</select>
		</label>
		<label>Nächster Start
			<input type="date" bind:value={cfg.next_start} class="glass-surface mt-1 w-full rounded px-3 py-2" />
		</label>
		<label>Wiederholung alle … Monate
			<select bind:value={cfg.interval_months} class="glass-surface mt-1 w-full rounded px-3 py-2">
				{#each [[1, 'jeden Monat'], [3, 'vierteljährlich'], [6, 'halbjährlich'], [12, 'jährlich']] as [v, l]}<option value={v}>{l} ({v})</option>{/each}
			</select>
		</label>
		<label>Laufzeit (Tage)
			<input type="number" min="1" bind:value={cfg.duration_days} class="glass-surface mt-1 w-full rounded px-3 py-2" />
		</label>
		<label>Anlegen … Tage vor Start
			<input type="number" min="0" bind:value={cfg.lead_days} class="glass-surface mt-1 w-full rounded px-3 py-2" />
		</label>
		<label>Erinnerungen (Tage vor Ende)
			<input bind:value={reminders} class="glass-surface mt-1 w-full rounded px-3 py-2" />
		</label>
		<label>Report-Versand
			<select bind:value={cfg.report_channel} class="glass-surface mt-1 w-full rounded px-3 py-2">
				<option value="portal">im Portal</option><option value="email">per E-Mail</option><option value="beides">beides</option>
			</select>
		</label>
		<label class="sm:col-span-2">Namensmuster <span class="text-xs">({'{year}'}, {'{half}'}, {'{quarter}'})</span>
			<input bind:value={cfg.name_pattern} class="glass-surface mt-1 w-full rounded px-3 py-2" />
		</label>
	</div>
	{#if error}<p class="mt-3 text-sm" style="color: var(--danger)">{error}</p>{/if}
	<div class="mt-5 flex justify-end gap-2">
		<Button variant="secondary" onclick={() => oncancel?.()}>Abbrechen</Button>
		<Button onclick={save} disabled={saving}>{saving ? 'Speichere…' : 'Speichern'}</Button>
	</div>
{/if}
