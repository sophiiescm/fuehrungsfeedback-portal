<script lang="ts">
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import { api } from '$lib/api/client';
	import { surveysApi, type SurveyTemplate } from '$lib/api/surveys';

	interface Cfg {
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
	let cfg = $state<Cfg | null>(null);
	let templates = $state<SurveyTemplate[]>([]);
	let reminders = $state('7,2');
	let msg = $state('');
	interface Preview {
		total: Record<string, number>;
		by_fachbereich: Record<string, Record<string, number>>;
		excluded: { leader: string; fachbereich: string; team_size: number }[];
	}
	let preview = $state<Preview | null>(null);
	async function loadPreview() {
		preview = await api.get<Preview>('/rounds/preview');
	}

	onMount(async () => {
		cfg = await api.get<Cfg>('/rounds/automation');
		reminders = cfg.reminder_days_before_end.join(',');
		templates = await surveysApi.listTemplates();
	});

	async function save() {
		if (!cfg) return;
		msg = '';
		try {
			cfg = await api.put<Cfg>('/rounds/automation', {
				...cfg,
				reminder_days_before_end: reminders.split(',').map((x) => Number(x.trim())).filter((x) => !isNaN(x) && x > 0)
			});
			msg = 'Gespeichert. Die nächste Runde wird automatisch angelegt und gestartet.';
		} catch (e) {
			msg = e instanceof Error ? e.message : 'Fehler';
		}
	}
</script>

{#if cfg}
	<Card title="Automatische Runden">
		<label class="mb-3 flex items-center gap-2 text-sm" style="color: var(--text-primary)">
			<input type="checkbox" bind:checked={cfg.enabled} /> Wiederkehrende Runden automatisch anlegen
		</label>
		<div class="grid gap-2 text-sm md:grid-cols-2" style="color: var(--text-secondary)">
			<label>Fragebogen-Version
				<select bind:value={cfg.survey_version_id} class="glass-surface w-full rounded px-2 py-2">
					<option value={null}>– wählen –</option>
					{#each templates as t (t.id)}{#each t.versions as v (v.id)}<option value={v.id}>{t.name} v{v.version_number} ({v.status})</option>{/each}{/each}
				</select>
			</label>
			<label>Nächster Start
				<input type="date" bind:value={cfg.next_start} class="glass-surface w-full rounded px-2 py-2" />
			</label>
			<label>Wiederholung alle … Monate
				<input type="number" min="1" max="24" bind:value={cfg.interval_months} class="glass-surface w-full rounded px-2 py-2" />
			</label>
			<label>Laufzeit (Tage)
				<input type="number" min="1" bind:value={cfg.duration_days} class="glass-surface w-full rounded px-2 py-2" />
			</label>
			<label>Anlegen … Tage vor Start
				<input type="number" min="0" bind:value={cfg.lead_days} class="glass-surface w-full rounded px-2 py-2" />
			</label>
			<label>Erinnerungen (Tage vor Ende)
				<input bind:value={reminders} class="glass-surface w-full rounded px-2 py-2" />
			</label>
			<label class="md:col-span-2">Namensmuster ({'{year}'}, {'{half}'}, {'{quarter}'})
				<input bind:value={cfg.name_pattern} class="glass-surface w-full rounded px-2 py-2" />
			</label>
			<label>Report-Versand
				<select bind:value={cfg.report_channel} class="glass-surface w-full rounded px-2 py-2">
					<option value="portal">Portal</option><option value="email">E-Mail</option><option value="beides">Beides</option>
				</select>
			</label>
		</div>
		<div class="mt-3 flex items-center gap-3">
			<Button onclick={save}>Speichern</Button>
			{#if msg}<span class="text-xs" style="color: var(--text-secondary)">{msg}</span>{/if}
		</div>
	</Card>
{/if}

{#if cfg}
	<Card title="Empfänger-Vorschau (aktueller SAP-/Org-Stand)">
		<Button variant="secondary" onclick={loadPreview}>Vorschau berechnen</Button>
		{#if preview}
			<p class="mt-3 text-sm" style="color: var(--text-primary)">
				{preview.total.leaders} Führungskräfte werden bewertet, {preview.total.recipients} Personen würden eingeladen
				({preview.total.without_email} ohne E-Mail → Code-Brief); {preview.total.excluded_leaders} Führungskräfte mit Team &lt; 3 werden nicht bewertet.
			</p>
			<table class="mt-2 w-full text-left text-xs" style="color: var(--text-secondary)">
				<thead><tr><th>Fachbereich</th><th>FK</th><th>Empfänger</th><th>ohne E-Mail</th><th>ausgeschlossen</th></tr></thead>
				<tbody>
					{#each Object.entries(preview.by_fachbereich) as [fb, r] (fb)}
						<tr><td>{fb}</td><td>{r.leaders}</td><td>{r.recipients}</td><td>{r.without_email}</td><td>{r.excluded_leaders}</td></tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</Card>
{/if}
