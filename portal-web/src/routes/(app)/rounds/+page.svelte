<script lang="ts">
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import RoundAutomation from '$lib/components/RoundAutomation.svelte';
	import { api } from '$lib/api/client';
	import { roundsApi, downloadPdf, type Round, type Dashboard } from '$lib/api/rounds';
	import { surveysApi, type SurveyTemplate } from '$lib/api/surveys';
	import { organisationApi } from '$lib/api/organisation';

	interface Preview {
		total: Record<string, number>;
		by_fachbereich: Record<string, Record<string, number>>;
		excluded: { leader: string; fachbereich: string; team_size: number }[];
	}

	let rounds = $state<Round[]>([]);
	let templates = $state<SurveyTemplate[]>([]);
	let fachbereiche = $state<string[]>([]);
	let dashboards = $state<Record<number, Dashboard>>({});
	let error = $state('');
	let info = $state('');
	let busy = $state(false);

	// --- Assistent "Neue Runde" ---
	let wizard = $state(false);
	let step = $state(1);
	let versionId = $state<number | null>(null);
	let start = $state('');
	let end = $state('');
	let reminders = $state('7,2');
	let selectedFb = $state<string[]>([]); // leer = alle
	let channel = $state('portal');
	let name = $state('');
	let preview = $state<Preview | null>(null);
	let startNow = $state(false);
	let orgStatus = $state<{ last_import: { finished_at: string | null; triggered_by: string } | null; source_configured: boolean; source: string } | null>(null);
	let syncing = $state(false);
	let syncMsg = $state('');

	const STEPS = ['Fragebogen', 'Zeitraum', 'Empfänger', 'Bestätigen'];
	const pad = (n: number) => String(n).padStart(2, '0');
	const local = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;

	async function load() {
		rounds = await roundsApi.list();
		templates = await surveysApi.listTemplates();
		fachbereiche = await organisationApi.listFachbereiche();
		if (!versionId) versionId = templates[0]?.versions.at(-1)?.id ?? null;
	}
	onMount(load);

	function openWizard() {
		wizard = true;
		step = 1;
		const s = new Date();
		s.setDate(s.getDate() + 1);
		s.setHours(6, 0, 0, 0);
		start = local(s);
		setDuration(28);
		name = suggestName(s);
	}
	function suggestName(d: Date) {
		return `Feedback-Runde ${d.getMonth() < 6 ? 'H1' : 'H2'}/${d.getFullYear()}`;
	}
	function setDuration(days: number) {
		const e = new Date(start);
		e.setDate(e.getDate() + days);
		end = local(e);
	}
	async function syncSap() {
		syncing = true;
		syncMsg = '';
		try {
			await api.post('/rounds/org-sync');
			syncMsg = 'Teams wurden aus SAP aktualisiert.';
		} catch (e) {
			syncMsg = e instanceof Error ? e.message : 'Aktualisierung fehlgeschlagen';
		} finally {
			syncing = false;
			await loadPreview();
		}
	}
	async function loadPreview() {
		orgStatus = await api.get('/rounds/org-status');
		const q = selectedFb.length ? `?fachbereiche=${encodeURIComponent(selectedFb.join(','))}` : '';
		preview = await api.get<Preview>(`/rounds/preview${q}`);
	}
	async function next() {
		if (step === 2) await loadPreview();
		step += 1;
		if (step === 3) await loadPreview();
	}
	const canNext = $derived(step === 1 ? !!versionId : step === 2 ? !!start && !!end && new Date(end) > new Date(start) : true);

	async function run(fn: () => Promise<unknown>) {
		busy = true;
		error = '';
		info = '';
		try {
			await fn();
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Fehler';
		} finally {
			busy = false;
		}
	}
	const create = () =>
		run(async () => {
			const r = await roundsApi.create({
				name,
				survey_version_id: versionId,
				start_at: new Date(start).toISOString(),
				end_at: new Date(end).toISOString(),
				report_channel: channel,
				target_fachbereiche: selectedFb.length ? selectedFb : null,
				reminder_days_before_end: reminders.split(',').map((x) => Number(x.trim())).filter(Boolean)
			});
			if (startNow) await roundsApi.start(r.id);
			wizard = false;
			info = startNow ? 'Runde gestartet – Einladungen sind raus.' : 'Runde geplant. Sie startet automatisch zum Startzeitpunkt.';
		});
	async function showDashboard(id: number) {
		dashboards[id] = await roundsApi.dashboard(id);
	}
	const remind = (id: number) =>
		run(async () => {
			const r = await api.post<{ sent: number }>(`/rounds/${id}/remind`);
			info = `${r.sent} Erinnerung(en) verschickt (nur an Personen ohne Teilnahme).`;
			await showDashboard(id);
		});
	function pdf(path: string, file: string) {
		downloadPdf(path, file).catch((e) => (error = e.message));
	}
	const STATUS: Record<string, string> = { entwurf: 'Entwurf', geplant: 'Geplant', offen: 'Läuft', geschlossen: 'Geschlossen', ausgewertet: 'Ausgewertet', berichtet: 'Abgeschlossen' };
	const days = (iso: string) => Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000));
</script>

<div class="mb-5 flex flex-wrap items-center justify-between gap-3">
	<h1 class="text-2xl font-bold" style="color: var(--text-primary)">Befragungsrunden</h1>
	{#if !wizard}<Button onclick={openWizard}>+ Neue Runde</Button>{/if}
</div>
{#if error}<p class="mb-4 text-sm" style="color: var(--danger)">{error}</p>{/if}
{#if info}<p class="mb-4 text-sm" style="color: var(--success)">{info}</p>{/if}

{#if wizard}
	<Card>
		<ol class="mb-5 flex gap-2 text-xs" aria-label="Schritte">
			{#each STEPS as label, i}
				<li class="flex-1 rounded-full px-2 py-1.5 text-center" style="background: {i + 1 === step ? 'var(--accent)' : i + 1 < step ? 'var(--success)' : 'var(--surface-glass-strong)'}; color: {i + 1 <= step ? '#fff' : 'var(--text-secondary)'}">{i + 1}. {label}</li>
			{/each}
		</ol>

		{#if step === 1}
			<p class="mb-2 font-semibold" style="color: var(--text-primary)">Welchen Fragebogen möchtest du verwenden?</p>
			<select bind:value={versionId} class="glass-surface w-full rounded px-3 py-3" style="color: var(--text-primary)">
				{#each templates as t (t.id)}{#each t.versions as v (v.id)}<option value={v.id}>{t.name} · Version {v.version_number}{v.limesurvey_template_sid ? ' · veröffentlicht' : ''}</option>{/each}{/each}
			</select>
			<p class="mt-2 text-xs" style="color: var(--text-muted)">Der Fragebogen wird beim Start automatisch veröffentlicht – du musst nichts weiter tun.</p>
		{:else if step === 2}
			<p class="mb-2 font-semibold" style="color: var(--text-primary)">Wann soll die Runde laufen?</p>
			<div class="grid gap-3 sm:grid-cols-2">
				<label class="text-sm" style="color: var(--text-secondary)">Start<input type="datetime-local" bind:value={start} onchange={() => setDuration(28)} class="glass-surface mt-1 w-full rounded px-3 py-2" /></label>
				<label class="text-sm" style="color: var(--text-secondary)">Ende<input type="datetime-local" bind:value={end} class="glass-surface mt-1 w-full rounded px-3 py-2" /></label>
			</div>
			<div class="mt-3 flex flex-wrap gap-2 text-sm">
				{#each [14, 21, 28] as d}<button class="rounded-full px-3 py-1.5" style="background: var(--surface-glass-strong); color: var(--text-primary)" onclick={() => setDuration(d)}>{d / 7} Wochen</button>{/each}
			</div>
			<label class="mt-3 block text-sm" style="color: var(--text-secondary)">Erinnerungen (Tage vor Ende, kommagetrennt)<input bind:value={reminders} class="glass-surface mt-1 w-full rounded px-3 py-2" /></label>
		{:else if step === 3}
			<p class="mb-2 font-semibold" style="color: var(--text-primary)">Wer wird bewertet und wer eingeladen?</p>
			<p class="mb-2 text-xs" style="color: var(--text-muted)">Optional auf Fachbereiche einschränken (nichts gewählt = alle).</p>
			<div class="mb-3 flex flex-wrap gap-2">
				{#each fachbereiche as f (f)}
					<button aria-pressed={selectedFb.includes(f)} class="rounded-full px-3 py-1.5 text-sm" style="background: {selectedFb.includes(f) ? 'var(--accent)' : 'var(--surface-glass-strong)'}; color: {selectedFb.includes(f) ? 'var(--accent-contrast)' : 'var(--text-primary)'}"
						onclick={async () => { selectedFb = selectedFb.includes(f) ? selectedFb.filter((x) => x !== f) : [...selectedFb, f]; await loadPreview(); }}>{f}</button>
				{/each}
			</div>
			<div class="mb-3 flex flex-wrap items-center gap-3 rounded-[var(--radius-md)] p-3 text-sm" style="background: var(--surface-glass-strong); color: var(--text-secondary)">
				<span class="flex-1">
					🔄 Teams kommen automatisch aus SAP.
					{#if orgStatus?.last_import?.finished_at}Letzter Stand: {orgStatus.last_import.finished_at.slice(0, 16).replace('T', ' ')} Uhr.{:else}Noch kein Import.{/if}
					{#if orgStatus && !orgStatus.source_configured}<br /><span style="color: var(--warning)">Keine SAP-Quelle eingerichtet – es gilt der zuletzt importierte Stand (Organisation → Import).</span>{/if}
					Beim Start der Runde wird der Stand automatisch nochmals abgeglichen.
				</span>
				{#if orgStatus?.source_configured}<Button variant="secondary" onclick={syncSap} disabled={syncing}>{syncing ? 'Aktualisiere…' : 'Jetzt aus SAP aktualisieren'}</Button>{/if}
			</div>
			{#if syncMsg}<p class="mb-2 text-xs" style="color: var(--text-secondary)">{syncMsg}</p>{/if}
			{#if preview}
				<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
					{#each [['Führungskräfte', preview.total.leaders], ['Einladungen', preview.total.recipients], ['ohne E-Mail', preview.total.without_email], ['nicht auswertbar', preview.total.excluded_leaders]] as [l, v]}
						<div class="rounded-[var(--radius-md)] p-3 text-center" style="background: var(--surface-glass-strong)"><div class="text-2xl font-bold" style="color: var(--text-primary)">{v}</div><div class="text-xs" style="color: var(--text-secondary)">{l}</div></div>
					{/each}
				</div>
				<p class="mt-2 text-xs" style="color: var(--text-muted)">„Nicht auswertbar“ = Team kleiner als 3 (Anonymität). Personen ohne E-Mail erhalten einen Code-Brief.</p>
			{/if}
		{:else}
			<p class="mb-2 font-semibold" style="color: var(--text-primary)">Alles bereit?</p>
			<label class="block text-sm" style="color: var(--text-secondary)">Name der Runde<input bind:value={name} class="glass-surface mt-1 w-full rounded px-3 py-2" /></label>
			<label class="mt-3 block text-sm" style="color: var(--text-secondary)">Reports an Führungskräfte
				<select bind:value={channel} class="glass-surface mt-1 w-full rounded px-3 py-2"><option value="portal">im Portal</option><option value="email">per E-Mail</option><option value="beides">beides</option></select>
			</label>
			<label class="mt-3 flex items-center gap-2 text-sm" style="color: var(--text-primary)"><input type="checkbox" bind:checked={startNow} /> Sofort starten (Einladungen jetzt versenden)</label>
			<p class="mt-3 text-sm" style="color: var(--text-secondary)">
				{start.replace('T', ' ')} bis {end.replace('T', ' ')} · {preview?.total.leaders ?? 0} Führungskräfte · {preview?.total.recipients ?? 0} Einladungen
			</p>
		{/if}

		<div class="mt-5 flex justify-between gap-2">
			<Button variant="secondary" onclick={() => (step === 1 ? (wizard = false) : (step -= 1))}>{step === 1 ? 'Abbrechen' : 'Zurück'}</Button>
			{#if step < 4}<Button onclick={next} disabled={!canNext}>Weiter</Button>{:else}<Button onclick={create} disabled={busy || !name}>{startNow ? 'Runde starten' : 'Runde planen'}</Button>{/if}
		</div>
	</Card>
{/if}

<div class="mt-5 flex flex-col gap-4">
	{#each rounds as r (r.id)}
		<Card>
			<div class="flex flex-wrap items-start justify-between gap-2">
				<div>
					<h2 class="text-lg font-semibold" style="color: var(--text-primary)">{r.name}</h2>
					<p class="text-sm" style="color: var(--text-secondary)">{r.start_at.slice(0, 10)} – {r.end_at.slice(0, 10)}{#if r.status === 'offen'} · noch {days(r.end_at)} Tage{/if}</p>
				</div>
				<span class="rounded-full px-3 py-1 text-xs font-semibold" style="background: {r.status === 'offen' ? 'var(--success)' : 'var(--surface-glass-strong)'}; color: {r.status === 'offen' ? '#fff' : 'var(--text-secondary)'}">{STATUS[r.status] ?? r.status}</span>
			</div>
			<div class="mt-3 flex flex-wrap gap-2">
				{#if r.status === 'geplant' || r.status === 'entwurf'}
					<Button onclick={() => run(() => roundsApi.start(r.id))} disabled={busy}>Jetzt starten</Button>
				{/if}
				{#if r.status === 'offen'}
					<Button onclick={() => remind(r.id)} disabled={busy}>Erinnerung an alle Offenen</Button>
					<Button variant="danger" onclick={() => run(() => roundsApi.close(r.id))} disabled={busy}>Schließen</Button>
				{/if}
				<Button variant="secondary" onclick={() => showDashboard(r.id)}>Rücklauf</Button>
				<Button variant="secondary" onclick={() => pdf(`/rounds/${r.id}/code-letters.pdf`, 'code-briefe.pdf')}>Code-Briefe</Button>
				<Button variant="secondary" onclick={() => pdf(`/rounds/${r.id}/team-notices.pdf`, 'aushang.pdf')}>Team-Aushang</Button>
				<Button variant="secondary" onclick={() => pdf(`/rounds/${r.id}/response-rate.csv`, `ruecklauf-${r.id}.csv`)}>Rücklauf als CSV</Button>
			</div>
			{#if dashboards[r.id]}
				{@const d = dashboards[r.id]}
				<div class="mt-4 h-3 overflow-hidden rounded-full" style="background: var(--border-subtle)"><div class="h-3" style="width: {d.response_rate * 100}%; background: var(--accent)"></div></div>
				<p class="mt-1 text-sm" style="color: var(--text-primary)">Rücklauf gesamt: {d.total_completed}/{d.total_invited} ({Math.round(d.response_rate * 100)} %)</p>
				<ul class="mt-3 flex flex-col gap-2 text-sm" style="color: var(--text-secondary)">
					{#each Object.entries(d.by_fachbereich) as [fb, v] (fb)}
						<li>
							<div class="flex justify-between"><span>{fb}</span><span>{v.completed}/{v.invited} ({Math.round(v.response_rate * 100)} %)</span></div>
							<div class="h-2 overflow-hidden rounded-full" style="background: var(--border-subtle)"><div class="h-2" style="width: {v.response_rate * 100}%; background: {v.response_rate < 0.4 ? 'var(--danger)' : v.response_rate < 0.7 ? 'var(--warning)' : 'var(--success)'}"></div></div>
						</li>
					{/each}
				</ul>
				<p class="mt-2 text-xs" style="color: var(--text-muted)">Angezeigt werden nur Zahlen je Bereich – nie, wer teilgenommen hat.</p>
			{/if}
		</Card>
	{/each}
</div>

<details class="mt-6">
	<summary class="cursor-pointer py-2 text-sm font-semibold" style="color: var(--text-primary)">Automatische Runden (z. B. halbjährlich)</summary>
	<RoundAutomation />
</details>
