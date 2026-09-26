<script lang="ts">
	import { auth } from '$lib/stores/auth.svelte';
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import { api } from '$lib/api/client';
	import { feedbackApi, roundsApi, type Round, type Dashboard } from '$lib/api/rounds';

	let openCount = $state<number | null>(null);
	let dueDate = $state('');
	let firstLink = $state<string | null>(null);
	let reports = $state<{ target_id: number; round_name: string; start: string }[]>([]);
	let round = $state<Round | null>(null);
	let dash = $state<Dashboard | null>(null);
	let nextStart = $state<string | null>(null);
	let actionsOpen = $state(0);

	const daysLeft = (iso: string) => Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000));
	const firstName = $derived(auth.user?.full_name.split(' ')[0] ?? '');

	onMount(async () => {
		const items = await feedbackApi.mine();
		const open = items.filter((i) => i.status === 'offen');
		openCount = open.length;
		dueDate = open.map((i) => i.due_date).sort()[0] ?? '';
		firstLink = open.length === 1 ? open[0].feedback_link : null;
		if (auth.hasRole('fuehrungskraft')) reports = await api.get<typeof reports>('/reports/mine').catch(() => []);
		if (auth.can('rounds.manage') || auth.can('results.view')) {
			const rounds = await roundsApi.list();
			round = rounds.find((r) => r.status === 'offen') ?? rounds.find((r) => r.status === 'geplant') ?? null;
			if (round && round.status === 'offen') dash = await roundsApi.dashboard(round.id);
			const cfg = await api.get<{ enabled: boolean; next_start: string | null }>('/rounds/automation').catch(() => null);
			nextStart = cfg?.enabled ? cfg.next_start : null;
		}
		const acts = await api.get<{ status: string }[]>('/actions/mine').catch(() => []);
		actionsOpen = acts.filter((a) => a.status !== 'erledigt').length;
	});
</script>

<h1 class="mb-1 text-2xl font-bold" style="color: var(--text-primary)">Hallo {firstName} 👋</h1>
<p class="mb-5 text-sm" style="color: var(--text-secondary)">Das ist heute für dich wichtig.</p>

<div class="grid gap-4 lg:grid-cols-2">
	<!-- Mitarbeiter-Sicht: eine klare Hauptaktion -->
	<Card>
		{#if openCount === null}
			<p style="color: var(--text-secondary)">Lädt…</p>
		{:else if openCount === 0}
			<p class="text-lg font-semibold" style="color: var(--text-primary)">✓ Alles erledigt</p>
			<p class="text-sm" style="color: var(--text-secondary)">Du hast aktuell keine offenen Feedbacks. Danke für deine Beteiligung!</p>
		{:else}
			<p class="text-lg font-semibold" style="color: var(--text-primary)" data-testid="dash-open">
				Du hast {openCount} offene{openCount === 1 ? 's Feedback' : ' Feedbacks'}
			</p>
			<p class="mb-4 text-sm" style="color: var(--text-secondary)">Fällig bis {dueDate} · dauert ca. 5 Minuten · anonym</p>
			<a href={firstLink ?? '/feedbacks'} class="cta">{openCount === 1 ? 'Jetzt starten' : 'Feedbacks ansehen'}</a>
		{/if}
	</Card>

	{#if auth.hasRole('fuehrungskraft')}
		<Card title="Mein Feedback-Report">
			{#if reports.length}
				<p class="mb-1" style="color: var(--text-primary)">Neu: {reports[0].round_name}</p>
				<p class="mb-4 text-sm" style="color: var(--text-secondary)">Sieh dir Stärken und Handlungsfelder an und leite Maßnahmen für dein Team ab.</p>
				<a href="/reports" class="cta">Report öffnen</a>
			{:else}
				<p class="text-sm" style="color: var(--text-secondary)">Sobald eine Runde ausgewertet ist und mindestens 3 Antworten vorliegen, erscheint hier dein Report.</p>
			{/if}
		</Card>
	{/if}

	{#if actionsOpen}
		<Card title="Maßnahmen">
			<p class="mb-3 text-sm" style="color: var(--text-secondary)">{actionsOpen} Maßnahme{actionsOpen === 1 ? '' : 'n'} in Arbeit.</p>
			<a href="/massnahmen" class="cta">Ansehen</a>
		</Card>
	{/if}

	{#if auth.can('rounds.manage') || auth.can('results.view')}
		<Card title="Aktuelle Befragungsrunde">
			{#if round && dash}
				<p class="mb-2" style="color: var(--text-primary)">{round.name}</p>
				<div class="mb-1 h-3 overflow-hidden rounded-full" style="background: var(--border-subtle)" role="progressbar" aria-valuenow={Math.round(dash.response_rate * 100)} aria-valuemin="0" aria-valuemax="100">
					<div class="h-3" style="width: {dash.response_rate * 100}%; background: var(--accent)"></div>
				</div>
				<p class="mb-4 text-sm" style="color: var(--text-secondary)">
					Rücklauf {Math.round(dash.response_rate * 100)} % ({dash.total_completed} von {dash.total_invited}) · noch {daysLeft(round.end_at)} Tage
				</p>
				{#if auth.can('rounds.manage')}<a href="/rounds" class="cta">Rücklauf & Erinnerungen</a>{:else}<a href="/auswertung" class="cta">Auswertung ansehen</a>{/if}
			{:else if round}
				<p class="text-sm" style="color: var(--text-secondary)">„{round.name}“ startet am {round.start_at.slice(0, 10)}.</p>
			{:else}
				<p class="mb-3 text-sm" style="color: var(--text-secondary)">
					Keine Runde aktiv.{#if nextStart} Nächste automatische Runde: {nextStart}.{/if}
				</p>
				{#if auth.can('rounds.manage')}<a href="/rounds" class="cta">Neue Runde planen</a>{/if}
			{/if}
		</Card>
	{/if}
</div>

<style>
	.cta {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 44px;
		padding: 0 1.25rem;
		border-radius: var(--radius-sm);
		background: var(--accent);
		color: var(--accent-contrast);
		font-weight: 600;
		font-size: 0.9rem;
	}
	.cta:hover {
		background: var(--accent-hover);
	}
</style>
