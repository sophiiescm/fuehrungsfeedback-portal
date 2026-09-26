<script lang="ts">
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import RoundAutomation from '$lib/components/RoundAutomation.svelte';
	import { roundsApi, downloadPdf, type Round, type Dashboard } from '$lib/api/rounds';
	import { surveysApi, type SurveyTemplate } from '$lib/api/surveys';

	let rounds = $state<Round[]>([]);
	let templates = $state<SurveyTemplate[]>([]);
	let dashboards = $state<Record<number, Dashboard>>({});
	let error = $state('');
	let busy = $state(false);
	let name = $state('');
	let versionId = $state<number | null>(null);
	let start = $state('');
	let end = $state('');
	let reminders = $state('7,2');

	async function load() {
		rounds = await roundsApi.list();
		templates = await surveysApi.listTemplates();
		if (!versionId) versionId = templates[0]?.versions.at(-1)?.id ?? null;
	}
	onMount(load);

	async function run(fn: () => Promise<unknown>) {
		busy = true;
		error = '';
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
		run(() =>
			roundsApi.create({
				name,
				survey_version_id: versionId,
				start_at: new Date(start).toISOString(),
				end_at: new Date(end).toISOString(),
				reminder_days_before_end: reminders
					.split(',')
					.map((x) => Number(x.trim()))
					.filter(Boolean)
			})
		);
	async function showDashboard(id: number) {
		dashboards[id] = await roundsApi.dashboard(id);
	}
	function pdf(path: string, file: string) {
		downloadPdf(path, file).catch((e) => (error = e.message));
	}
	function quote(completed: number, open: number) {
		return Math.round((completed / Math.max(1, completed + open)) * 100);
	}
</script>

<h1 class="mb-6 text-2xl font-bold" style="color: var(--text-primary)">Befragungsrunden</h1>
{#if error}<p class="mb-4 text-sm" style="color: var(--danger)">{error}</p>{/if}

<RoundAutomation />

<Card title="Neue Runde">
	<div class="grid gap-2 md:grid-cols-2">
		<input placeholder="Name" bind:value={name} class="glass-surface rounded px-3 py-2 text-sm" style="color: var(--text-primary)" />
		<select bind:value={versionId} class="glass-surface rounded px-3 py-2 text-sm" style="color: var(--text-primary)">
			{#each templates as t (t.id)}
				{#each t.versions as v (v.id)}<option value={v.id}>{t.name} v{v.version_number}</option>{/each}
			{/each}
		</select>
		<label class="text-xs" style="color: var(--text-secondary)">Start <input type="datetime-local" bind:value={start} class="glass-surface rounded px-2 py-1" /></label>
		<label class="text-xs" style="color: var(--text-secondary)">Ende <input type="datetime-local" bind:value={end} class="glass-surface rounded px-2 py-1" /></label>
		<label class="text-xs" style="color: var(--text-secondary)">Erinnerungen (Tage vor Ende) <input bind:value={reminders} class="glass-surface rounded px-2 py-1" /></label>
	</div>
	<div class="mt-3"><Button onclick={create} disabled={busy || !name || !start || !end}>Runde anlegen</Button></div>
</Card>

<div class="mt-6 flex flex-col gap-4">
	{#each rounds as r (r.id)}
		<Card title={`${r.name} · ${r.status}`}>
			<p class="text-sm" style="color: var(--text-secondary)">{r.start_at.slice(0, 10)} – {r.end_at.slice(0, 10)}</p>
			<div class="mt-3 flex flex-wrap gap-2">
				{#if r.status === 'geplant' || r.status === 'entwurf'}
					<Button onclick={() => run(() => roundsApi.start(r.id))} disabled={busy}>Jetzt starten</Button>
				{/if}
				{#if r.status === 'offen'}
					<Button variant="danger" onclick={() => run(() => roundsApi.close(r.id))} disabled={busy}>Schließen</Button>
				{/if}
				<Button variant="secondary" onclick={() => showDashboard(r.id)}>Rücklauf</Button>
				<Button variant="secondary" onclick={() => pdf(`/rounds/${r.id}/code-letters.pdf`, 'code-briefe.pdf')}>Code-Briefe (PDF)</Button>
				<Button variant="secondary" onclick={() => pdf(`/rounds/${r.id}/team-notices.pdf`, 'aushang.pdf')}>Team-Aushang (PDF)</Button>
			</div>
			{#if dashboards[r.id]}
				{@const d = dashboards[r.id]}
				<p class="mt-4 text-sm" style="color: var(--text-primary)">
					Rücklauf gesamt: {d.total_completed}/{d.total_invited} ({Math.round(d.response_rate * 100)} %)
				</p>
				<ul class="mt-2 text-sm" style="color: var(--text-secondary)">
					{#each Object.entries(d.by_fachbereich) as [fb, v] (fb)}
						<li>{fb}: {v.completed}/{v.invited} ({Math.round(v.response_rate * 100)} %)</li>
					{/each}
				</ul>
				<details class="mt-2 text-sm" style="color: var(--text-secondary)">
					<summary>Führungskräfte ({d.targets.length})</summary>
					{#each d.targets as t (t.id)}
						<div>
							{t.leader_name}:
							{#if t.evaluable}
								Schwelle erreicht: {t.completed_count >= 3 ? 'ja' : 'nein'}, Quote {quote(t.completed_count, t.open_count)} %
							{:else}
								nicht auswertbar (Team &lt; 3)
							{/if}
						</div>
					{/each}
				</details>
			{/if}
		</Card>
	{/each}
</div>
