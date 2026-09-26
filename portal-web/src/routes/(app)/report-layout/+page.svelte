<script lang="ts">
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import { api, ApiError } from '$lib/api/client';
	import { downloadFile } from '$lib/api/rounds';

	interface Section { key: string; enabled: boolean; title: string }
	interface Config {
		title: string;
		subtitle: string;
		intro: string;
		footer: string;
		accent: string;
		columns: Record<string, boolean>;
		sections: Section[];
	}
	interface CatalogItem { key: string; title: string; description: string }

	const COLUMN_LABELS: Record<string, string> = {
		fachbereich: 'Fachbereich', unternehmen: 'Unternehmen', vorrunde: 'Vorrunde', median: 'Median', stddev: 'Streuung', minmax: 'Min/Max'
	};

	let cfg = $state<Config | null>(null);
	let saved = $state('');
	let catalog = $state<CatalogItem[]>([]);
	let html = $state('');
	let msg = $state('');
	let error = $state('');
	let busy = $state(false);
	let timer: ReturnType<typeof setTimeout>;

	const desc = (k: string) => catalog.find((c) => c.key === k)?.description ?? '';
	const dirty = $derived(cfg !== null && JSON.stringify(cfg) !== saved);

	async function load() {
		const r = await api.get<{ config: Config; catalog: CatalogItem[] }>('/report-layout');
		cfg = r.config;
		catalog = r.catalog;
		saved = JSON.stringify(r.config);
		await refresh();
	}
	onMount(load);

	async function refresh() {
		if (!cfg) return;
		try {
			html = (await api.post<{ html: string }>('/report-layout/preview', { config: cfg })).html;
		} catch {
			/* Vorschau ist optional */
		}
	}
	// Vorschau leicht verzoegert aktualisieren
	$effect(() => {
		JSON.stringify(cfg);
		clearTimeout(timer);
		timer = setTimeout(refresh, 350);
		return () => clearTimeout(timer);
	});

	function move(i: number, d: number) {
		if (!cfg) return;
		const j = i + d;
		if (j < 0 || j >= cfg.sections.length) return;
		const s = cfg.sections;
		[s[i], s[j]] = [s[j], s[i]];
	}

	async function save() {
		busy = true;
		error = msg = '';
		try {
			const r = await api.put<{ config: Config }>('/report-layout', { config: cfg });
			cfg = r.config;
			saved = JSON.stringify(r.config);
			msg = 'Gespeichert. Ab sofort gilt das Layout für alle neuen Exporte.';
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Fehler';
		} finally {
			busy = false;
		}
	}
	async function reset() {
		if (!confirm('Layout auf den Standard zurücksetzen?')) return;
		const r = await api.post<{ config: Config }>('/report-layout/reset');
		cfg = r.config;
		saved = JSON.stringify(r.config);
		msg = 'Standard wiederhergestellt.';
	}
	async function sample(format: string) {
		error = '';
		try {
			await downloadFile(`/report-layout/sample?format=${format}`, `beispiel-report.${format}`, 'POST', { config: cfg });
		} catch (e) {
			error = e instanceof Error ? e.message : 'Export fehlgeschlagen';
		}
	}
</script>

<h1 class="mb-1 text-2xl font-bold" style="color: var(--text-primary)">Report-Layout</h1>
<p class="mb-5 text-sm" style="color: var(--text-secondary)">
	Bestimme, wie der Report der Führungskräfte aufgebaut ist – als PDF, PowerPoint, Excel und CSV. Die Vorschau zeigt Beispieldaten; echte Reports sind für Admins nie einsehbar.
</p>

{#if error}<p class="mb-3 text-sm" style="color: var(--danger)">{error}</p>{/if}
{#if msg}<p class="mb-3 text-sm" style="color: var(--success)">{msg}</p>{/if}

{#if cfg}
	<div class="grid gap-5 xl:grid-cols-2">
		<div class="flex flex-col gap-5">
			<Card title="Abschnitte und Reihenfolge">
				<ol class="flex flex-col gap-2">
					{#each cfg.sections as s, i (s.key)}
						<li class="sec" class:off={!s.enabled}>
							<div class="flex flex-col gap-1">
								<button class="arrow" onclick={() => move(i, -1)} disabled={i === 0} aria-label="Nach oben">▲</button>
								<button class="arrow" onclick={() => move(i, 1)} disabled={i === cfg.sections.length - 1} aria-label="Nach unten">▼</button>
							</div>
							<div class="min-w-0 flex-1">
								<input bind:value={s.title} class="glass-surface w-full rounded px-3 py-2 text-sm font-semibold" style="color: var(--text-primary)" aria-label="Überschrift" />
								<p class="mt-1 text-xs" style="color: var(--text-muted)">{desc(s.key)}</p>
							</div>
							<label class="switch" title={s.enabled ? 'Abschnitt ist sichtbar' : 'Abschnitt ist ausgeblendet'}>
								<input type="checkbox" bind:checked={s.enabled} />
								<span>{s.enabled ? 'An' : 'Aus'}</span>
							</label>
						</li>
					{/each}
				</ol>
				{#if cfg.sections.find((s) => s.key === 'freetext')?.enabled}
					<p class="mt-3 text-xs" style="color: var(--warning)">Hinweis: „Alle Freitexte“ ist aktiv – die (geschwärzten) Texte landen dann auch in Excel und CSV.</p>
				{/if}
			</Card>

			<Card title="Kopf, Fuß und Farbe">
				<div class="flex flex-col gap-3 text-sm" style="color: var(--text-secondary)">
					<label>Titel <span class="text-xs">({'{round}'} = Runde, {'{leader}'} = Führungskraft, {'{n}'} = Antworten)</span>
						<input bind:value={cfg.title} class="glass-surface mt-1 w-full rounded px-3 py-2" style="color: var(--text-primary)" /></label>
					<label>Untertitel
						<input bind:value={cfg.subtitle} class="glass-surface mt-1 w-full rounded px-3 py-2" style="color: var(--text-primary)" /></label>
					<label>Einleitungstext (optional)
						<textarea bind:value={cfg.intro} rows="3" class="glass-surface mt-1 w-full rounded px-3 py-2" style="color: var(--text-primary)"></textarea></label>
					<label>Fußzeile
						<input bind:value={cfg.footer} class="glass-surface mt-1 w-full rounded px-3 py-2" style="color: var(--text-primary)" /></label>
					<label class="flex items-center gap-3">Akzentfarbe
						<input type="color" bind:value={cfg.accent} class="h-10 w-16 cursor-pointer rounded" /> <span class="text-xs">{cfg.accent}</span></label>
				</div>
			</Card>

			<Card title="Spalten im Themenvergleich">
				<div class="flex flex-wrap gap-2">
					{#each Object.keys(cfg.columns) as k (k)}
						<label class="pill" class:on={cfg.columns[k]}><input type="checkbox" bind:checked={cfg.columns[k]} class="sr-only" />{COLUMN_LABELS[k] ?? k}</label>
					{/each}
				</div>
			</Card>

			<div class="flex flex-wrap items-center gap-3">
				<Button onclick={save} disabled={busy || !dirty}>Speichern</Button>
				<Button variant="secondary" onclick={reset}>Auf Standard zurücksetzen</Button>
				{#if dirty}<span class="text-xs" style="color: var(--warning)">Ungespeicherte Änderungen</span>{/if}
			</div>

			<Card title="Beispiel herunterladen">
				<p class="mb-3 text-xs" style="color: var(--text-secondary)">Prüfe das Ergebnis mit Beispieldaten, bevor du speicherst.</p>
				<div class="flex flex-wrap gap-2">
					{#each [['pdf', 'PDF'], ['pptx', 'PowerPoint'], ['xlsx', 'Excel'], ['csv', 'CSV']] as [f, l] (f)}
						<Button variant="secondary" onclick={() => sample(f)}>⬇ {l}</Button>
					{/each}
				</div>
			</Card>
		</div>

		<div>
			<div class="sticky top-20">
				<p class="mb-2 text-sm font-semibold" style="color: var(--text-primary)">Live-Vorschau (PDF-Aufbau, Beispieldaten)</p>
				<iframe title="Vorschau des Reports" srcdoc={html} class="preview" sandbox=""></iframe>
			</div>
		</div>
	</div>
{/if}

<style>
	.sec {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: var(--surface-glass-strong);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-md);
		padding: 0.6rem 0.75rem;
	}
	.sec.off {
		opacity: 0.6;
	}
	.arrow {
		width: 32px;
		height: 24px;
		border-radius: 6px;
		font-size: 0.7rem;
		background: var(--surface-glass);
		color: var(--text-secondary);
	}
	.arrow:disabled {
		opacity: 0.3;
	}
	.switch {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 44px;
		font-size: 0.8rem;
		color: var(--text-primary);
	}
	.pill {
		display: inline-flex;
		align-items: center;
		min-height: 40px;
		padding: 0 1rem;
		border-radius: 999px;
		font-size: 0.85rem;
		cursor: pointer;
		background: var(--surface-glass-strong);
		color: var(--text-secondary);
		border: 1px solid var(--border-subtle);
	}
	.pill.on {
		background: var(--accent);
		color: var(--accent-contrast);
	}
	.preview {
		width: 100%;
		height: 78vh;
		border-radius: var(--radius-md);
		border: 1px solid var(--border-subtle);
		background: #fff;
	}
</style>
