<script lang="ts">
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import { api, ApiError } from '$lib/api/client';
	import { downloadFile } from '$lib/api/rounds';

	interface Section { key: string; enabled: boolean; title: string; body?: string }
	interface Config {
		title: string;
		subtitle: string;
		intro: string;
		footer: string;
		accent: string;
		texts: Record<string, string>;
		columns: Record<string, boolean>;
		sections: Section[];
	}
	interface CatalogItem { key: string; title: string; description: string }
	interface TextItem { key: string; label: string; default: string; hint: string }
	interface Ph { key: string; label: string }

	const COLUMN_LABELS: Record<string, string> = {
		fachbereich: 'Fachbereich', unternehmen: 'Unternehmen', vorrunde: 'Vorrunde', median: 'Median', stddev: 'Streuung', minmax: 'Min/Max'
	};

	let cfg = $state<Config | null>(null);
	let saved = $state('');
	let catalog = $state<CatalogItem[]>([]);
	let textCatalog = $state<TextItem[]>([]);
	let placeholders = $state<Ph[]>([]);
	let lastField: HTMLInputElement | HTMLTextAreaElement | null = null;
	let html = $state('');
	let msg = $state('');
	let error = $state('');
	let busy = $state(false);
	let timer: ReturnType<typeof setTimeout>;

	const desc = (k: string) => catalog.find((c) => c.key === k)?.description ?? '';
	const dirty = $derived(cfg !== null && JSON.stringify(cfg) !== saved);

	async function load() {
		const r = await api.get<{ config: Config; catalog: CatalogItem[]; texts: TextItem[]; placeholders: Ph[] }>('/report-layout');
		cfg = r.config;
		catalog = r.catalog;
		textCatalog = r.texts;
		placeholders = r.placeholders;
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

	const isCustom = (k: string) => k.startsWith('custom:');
	const newId = () => 'custom:' + Math.random().toString(36).slice(2, 10);
	const customCount = $derived(cfg?.sections.filter((x) => isCustom(x.key)).length ?? 0);
	function addBlock() {
		if (!cfg || customCount >= 10) return;
		cfg.sections.push({ key: newId(), enabled: true, title: 'Neuer Textbaustein', body: 'Liebe/r {leader},\n\nhier steht dein eigener Text.' });
	}
	function removeBlock(i: number) {
		if (cfg && confirm('Textbaustein löschen?')) cfg.sections.splice(i, 1);
	}
	const textVal = (t: TextItem) => cfg?.texts[t.key] ?? t.default;
	function setText(t: TextItem, v: string) {
		if (!cfg) return;
		if (v === t.default) delete cfg.texts[t.key];
		else cfg.texts[t.key] = v;
	}
	// Platzhalter an der Cursorposition des zuletzt genutzten Textfelds einfügen
	function insertPh(key: string) {
		const el = lastField;
		if (!el) {
			msg = 'Klicke zuerst in ein Textfeld, dann auf einen Platzhalter.';
			return;
		}
		msg = '';
		el.setRangeText(`{${key}}`, el.selectionStart ?? el.value.length, el.selectionEnd ?? el.value.length, 'end');
		el.dispatchEvent(new Event('input', { bubbles: true }));
		el.focus();
	}
	function trackFocus(e: FocusEvent) {
		const t = e.target;
		if (t instanceof HTMLTextAreaElement || (t instanceof HTMLInputElement && t.type === 'text')) lastField = t;
	}

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
		<div class="flex flex-col gap-5" onfocusin={trackFocus}>
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
								{#if isCustom(s.key)}
									<textarea bind:value={s.body} rows="4" class="glass-surface mt-2 w-full rounded px-3 py-2 text-sm" style="color: var(--text-primary)" aria-label="Text des Bausteins" placeholder="Dein Text …"></textarea>
									<p class="mt-1 flex items-center justify-between text-xs" style="color: var(--text-muted)"><span>Eigener Textbaustein</span><button class="del" onclick={() => removeBlock(i)}>Löschen</button></p>
								{:else}
									<p class="mt-1 text-xs" style="color: var(--text-muted)">{desc(s.key)}</p>
								{/if}
							</div>
							<label class="switch" title={s.enabled ? 'Abschnitt ist sichtbar' : 'Abschnitt ist ausgeblendet'}>
								<input type="checkbox" bind:checked={s.enabled} />
								<span>{s.enabled ? 'An' : 'Aus'}</span>
							</label>
						</li>
					{/each}
				</ol>
				<div class="mt-3"><Button variant="secondary" onclick={addBlock} disabled={customCount >= 10}>＋ Textbaustein hinzufügen</Button></div>
				{#if cfg.sections.find((s) => s.key === 'freetext')?.enabled}
					<p class="mt-3 text-xs" style="color: var(--warning)">Hinweis: „Alle Freitexte“ ist aktiv – die (geschwärzten) Texte landen dann auch in Excel und CSV.</p>
				{/if}
			</Card>

			<Card title="Texte im Report">
				<p class="mb-3 text-xs" style="color: var(--text-secondary)">Passe die festen Formulierungen an. Leer lassen blendet einen Text aus, „Standard“ stellt ihn wieder her.
					Formatierung: <code>**fett**</code>, Leerzeile = neuer Absatz, <code>- </code> am Zeilenanfang = Aufzählung.</p>
				<div class="mb-4 flex flex-wrap items-center gap-2">
					<span class="text-xs font-semibold" style="color: var(--text-primary)">Platzhalter einfügen:</span>
					{#each placeholders as ph (ph.key)}
						<button class="ph" title={ph.label} onclick={() => insertPh(ph.key)}>{'{' + ph.key + '}'}</button>
					{/each}
				</div>
				<div class="flex flex-col gap-4">
					{#each textCatalog as t (t.key)}
						<div>
							<div class="mb-1 flex items-center justify-between gap-2">
								<label class="text-sm font-semibold" style="color: var(--text-primary)" for={'t-' + t.key}>{t.label}</label>
								{#if cfg.texts[t.key] !== undefined}<button class="del" style="color: var(--accent-text)" onclick={() => setText(t, t.default)}>Standard</button>{/if}
							</div>
							<textarea id={'t-' + t.key} rows={t.default.length > 90 ? 4 : 2} class="glass-surface w-full rounded px-3 py-2 text-sm" style="color: var(--text-primary)"
								value={textVal(t)} oninput={(e) => setText(t, e.currentTarget.value)}></textarea>
							{#if t.hint}<p class="mt-1 text-xs" style="color: var(--text-muted)">{t.hint}</p>{/if}
						</div>
					{/each}
				</div>
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
	.ph {
		min-height: 32px;
		padding: 0 0.6rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-family: ui-monospace, monospace;
		background: var(--accent-soft);
		color: var(--accent-text);
		border: 1px solid var(--border-subtle);
	}
	.del {
		font-size: 0.75rem;
		color: var(--danger);
	}
	code {
		font-size: 0.75rem;
		background: var(--surface-glass);
		padding: 0 0.3rem;
		border-radius: 4px;
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
