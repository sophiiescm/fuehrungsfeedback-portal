<script lang="ts">
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import { feedbackApi, type MyFeedback } from '$lib/api/rounds';
	import { auth } from '$lib/stores/auth.svelte';
	import { deleteReceipt, getReceipt, type Receipt } from '$lib/receipts';

	let items = $state<MyFeedback[]>([]);
	let loaded = $state(false);
	let view = $state<{ title: string; receipt: Receipt; sid: number } | null>(null);
	let picked = $state<Record<number, string>>({});
	const LANG_NAMES: Record<string, string> = { de: 'Deutsch', en: 'English', tr: 'Türkçe', pl: 'Polski', ru: 'Русский', ro: 'Română', uk: 'Українська', ar: 'العربية', es: 'Español', fr: 'Français', it: 'Italiano', nl: 'Nederlands', pt: 'Português', bg: 'Български', hr: 'Hrvatski', cs: 'Čeština', hu: 'Magyar', el: 'Ελληνικά', sq: 'Shqip', bs: 'Bosanski' };
	const langFor = (f: MyFeedback) => picked[f.participation_id] ?? ((f.languages ?? ['de']).includes(auth.user?.language ?? 'de') ? (auth.user?.language ?? 'de') : 'de');
	const linkFor = (f: MyFeedback) => (f.feedback_link ? `${f.feedback_link}/lang/${langFor(f)}` : null);
	let receiptVersion = $state(0); // erzwingt Neuberechnung nach Loeschen

	onMount(async () => {
		items = await feedbackApi.mine();
		loaded = true;
	});
	const open = $derived(items.filter((i) => i.status === 'offen' && !i.round_closed));
	// Verlauf: alles Abgegebene und verpasste Runden, neueste zuerst
	const history = $derived(
		items
			.filter((i) => i.status === 'erledigt' || i.round_closed)
			.sort((a, b) => (b.completed_date ?? b.due_date).localeCompare(a.completed_date ?? a.due_date))
	);
	const days = (iso: string) => Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000);
	const pnr = $derived(auth.user?.personalnummer ?? '');
	const receiptFor = (f: MyFeedback) => (receiptVersion >= 0 ? getReceipt(pnr, f.survey_id) : null);

	function show(f: MyFeedback) {
		const r = receiptFor(f);
		if (r && f.survey_id) view = { title: `${f.round_name} · ${f.leader_name}`, receipt: r, sid: f.survey_id };
	}
	function remove() {
		if (!view || !confirm('Die auf diesem Gerät gespeicherte Kopie wirklich löschen? Das kann nicht rückgängig gemacht werden.')) return;
		deleteReceipt(pnr, view.sid);
		view = null;
		receiptVersion += 1;
	}
	const groups = (r: Receipt) => {
		const out: { name: string; items: Receipt['items'] }[] = [];
		for (const it of r.items) {
			const last = out.at(-1);
			if (last && last.name === it.g) last.items.push(it);
			else out.push({ name: it.g, items: [it] });
		}
		return out;
	};
</script>

<h1 class="mb-1 text-2xl font-bold" style="color: var(--text-primary)">Meine Feedbacks</h1>
<p class="mb-5 text-sm" style="color: var(--text-secondary)" data-testid="open-summary">
	{#if !loaded}Lädt…{:else if open.length === 0}Alles erledigt.{:else}Du hast {open.length} offene{open.length === 1 ? 's Feedback' : ' Feedbacks'}.{/if}
</p>

<!-- Vertrauen zuerst: was passiert mit meinen Antworten? -->
<div class="trust mb-5" role="note">
	<strong>🔒 Dein Feedback ist anonym.</strong>
	<ul>
		<li>Niemand sieht, <em>was</em> du geantwortet hast. Das Portal merkt sich nur, <em>dass</em> du teilgenommen hast.</li>
		<li>Freitexte werden automatisch von Namen und Kontaktdaten bereinigt.</li>
	</ul>
</div>

{#if open.length}
	<h2 class="mb-2 text-sm font-semibold tracking-wide uppercase" style="color: var(--text-muted)">Offen</h2>
	<div class="mb-6 flex flex-col gap-3">
		{#each open as f (f.participation_id)}
			<div class="glass-surface fb-card p-4 sm:p-5">
				<div>
					<p class="text-xs font-semibold tracking-wide uppercase" style="color: var(--accent)">{f.round_name}</p>
					<p class="text-lg font-semibold" style="color: var(--text-primary)">Feedback für {f.leader_name}</p>
					<p class="text-sm" style="color: var(--text-secondary)">
						Fällig bis {f.due_date}{#if days(f.due_date) <= 3 && days(f.due_date) >= 0} · <strong style="color: var(--warning)">nur noch {days(f.due_date)} Tage</strong>{/if} · ca. 5 Minuten
					</p>
				</div>
				{#if f.feedback_link}
					<div class="flex flex-col items-stretch gap-2 sm:items-end">
						<a href={linkFor(f)} class="cta">Jetzt starten</a>
						{#if (f.languages ?? []).length > 1}
							<label class="text-xs" style="color: var(--text-secondary)">🌐
								<select class="glass-surface rounded px-2 py-1" value={langFor(f)} aria-label="Sprache der Umfrage" onchange={(e) => (picked[f.participation_id] = e.currentTarget.value)}>
									{#each f.languages ?? [] as c (c)}<option value={c}>{LANG_NAMES[c] ?? c}</option>{/each}
								</select>
							</label>
						{/if}
					</div>
				{/if}
			</div>
		{/each}
	</div>
{/if}

<h2 class="mb-2 text-sm font-semibold tracking-wide uppercase" style="color: var(--text-muted)">Meine Teilnahmen</h2>
{#if loaded && history.length === 0}
	<Card><p class="text-sm" style="color: var(--text-secondary)">Noch keine abgeschlossenen Runden.</p></Card>
{/if}
<div class="flex flex-col gap-2">
	{#each history as f (f.participation_id)}
		{@const done = f.status === 'erledigt'}
		{@const r = receiptFor(f)}
		<div class="glass-surface flex flex-wrap items-center gap-3 p-4">
			<span class="tick" class:miss={!done} aria-hidden="true">{done ? '✓' : '–'}</span>
			<div class="min-w-0 flex-1">
				<p style="color: var(--text-primary)">{f.leader_name} <span class="text-xs" style="color: var(--text-muted)">· {f.round_name}</span></p>
				<p class="text-sm" style="color: {done ? 'var(--success)' : 'var(--text-secondary)'}">
					{done ? `Abgegeben am ${f.completed_date}` : `Nicht teilgenommen (Runde endete am ${f.due_date})`}
				</p>
			</div>
			{#if done}
				{#if r}
					<button class="link" onclick={() => show(f)}>Meine Antworten ansehen</button>
				{:else}
					<span class="text-xs" style="color: var(--text-muted)" title="Antworten werden nur auf dem Gerät gespeichert, auf dem du sie abgegeben hast">keine Kopie auf diesem Gerät</span>
				{/if}
			{/if}
		</div>
	{/each}
</div>

<details class="mt-5 text-sm" style="color: var(--text-secondary)">
	<summary class="cursor-pointer py-2">Warum kann ich meine Antworten nur auf dem Gerät ansehen?</summary>
	<p class="pb-2">
		Das Portal speichert nicht, was du geantwortet hast – so bleibt dein Feedback anonym. Direkt nach dem Absenden legt dein Browser deshalb eine Kopie
		nur auf diesem Gerät ab. Sie ist schreibgeschützt, wird nie hochgeladen und auf Gemeinschaftsgeräten (Kiosk) gar nicht angelegt. Abgegebene Antworten lassen sich nicht mehr ändern.
	</p>
</details>

{#if view}
	<div class="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label="Meine abgegebenen Antworten">
		<button class="absolute inset-0" style="background: rgba(0,0,0,0.45)" aria-label="Schließen" onclick={() => (view = null)}></button>
		<div class="glass-surface relative flex max-h-[90vh] w-full max-w-2xl flex-col" style="background: var(--surface-glass-strong); border-radius: var(--radius-lg) var(--radius-lg) 0 0">
			<div class="flex items-start justify-between gap-3 p-4 pb-2">
				<div>
					<p class="text-lg font-semibold" style="color: var(--text-primary)">Meine Antworten</p>
					<p class="text-xs" style="color: var(--text-secondary)">{view.title} · abgegeben am {view.receipt.at} · nur lesbar, nur auf diesem Gerät</p>
				</div>
				<button class="link" onclick={() => (view = null)} aria-label="Schließen">✕</button>
			</div>
			<div class="overflow-y-auto p-4 pt-2">
				{#each groups(view.receipt) as g (g.name)}
					<p class="mt-3 mb-1 text-sm font-semibold" style="color: var(--accent)">{g.name}</p>
					{#each g.items as it}
						<div class="mb-2 rounded-[var(--radius-sm)] p-3 text-sm" style="background: var(--surface-glass)">
							<p style="color: var(--text-secondary)">{it.q}</p>
							<p class="mt-1 font-medium whitespace-pre-line" style="color: var(--text-primary)">{it.a.length ? it.a.join('\n') : '– keine Antwort –'}</p>
						</div>
					{/each}
				{/each}
			</div>
			<div class="flex justify-between gap-2 border-t p-3" style="border-color: var(--border-subtle)">
				<button class="link" style="color: var(--danger)" onclick={remove}>Kopie von diesem Gerät löschen</button>
				<button class="cta small" onclick={() => (view = null)}>Schließen</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.trust {
		background: var(--surface-glass-strong);
		border: 1px solid var(--border-subtle);
		border-left: 4px solid var(--success);
		border-radius: var(--radius-md);
		padding: 0.9rem 1rem;
		font-size: 0.875rem;
		color: var(--text-primary);
	}
	.trust ul {
		margin-top: 0.35rem;
		padding-left: 1.1rem;
		list-style: disc;
		color: var(--text-secondary);
	}
	.fb-card {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}
	@media (min-width: 640px) {
		.fb-card {
			flex-direction: row;
			align-items: center;
			justify-content: space-between;
		}
	}
	.cta {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 48px;
		padding: 0 1.5rem;
		border-radius: var(--radius-sm);
		background: var(--accent);
		color: var(--accent-contrast);
		font-weight: 600;
	}
	.cta.small {
		min-height: 40px;
		padding: 0 1rem;
		font-size: 0.875rem;
	}
	.link {
		min-height: 40px;
		padding: 0 0.5rem;
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--accent);
	}
	.tick {
		display: inline-flex;
		flex: 0 0 auto;
		width: 2rem;
		height: 2rem;
		align-items: center;
		justify-content: center;
		border-radius: 999px;
		background: var(--success);
		color: #fff;
		font-weight: 700;
	}
	.tick.miss {
		background: var(--text-muted);
	}
</style>
