<script lang="ts">
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import Table from '$lib/components/Table.svelte';
	import { organisationApi, importApi, type PersonListItem, type ImportDiff, type OrgTreeNode } from '$lib/api/organisation';

	type Tab = 'personen' | 'import' | 'organigramm';
	let tab = $state<Tab>('personen');

	// --- Personen ---
	let persons = $state<PersonListItem[]>([]);
	let total = $state(0);
	let q = $state('');
	let fachbereich = $state('');
	let fachbereiche = $state<string[]>([]);
	let onlyActive = $state(true);
	let loadingPersons = $state(false);

	async function loadPersons() {
		loadingPersons = true;
		try {
			const result = await organisationApi.listPersons({
				q: q || undefined,
				fachbereich: fachbereich || undefined,
				only_active: onlyActive
			});
			persons = result.items;
			total = result.total;
		} finally {
			loadingPersons = false;
		}
	}

	onMount(async () => {
		fachbereiche = await organisationApi.listFachbereiche();
		await loadPersons();
	});

	// --- Import ---
	let selectedFile = $state<File | null>(null);
	let diff = $state<ImportDiff | null>(null);
	let importError = $state('');
	let importing = $state(false);

	function onFileSelected(event: Event) {
		const input = event.target as HTMLInputElement;
		selectedFile = input.files?.[0] ?? null;
		diff = null;
		importError = '';
	}

	async function runDryRun() {
		if (!selectedFile) return;
		importing = true;
		importError = '';
		try {
			diff = await importApi.dryRun(selectedFile);
		} catch (e) {
			importError = e instanceof Error ? e.message : 'Trockenlauf fehlgeschlagen';
		} finally {
			importing = false;
		}
	}

	async function applyImport() {
		if (!selectedFile) return;
		importing = true;
		importError = '';
		try {
			diff = await importApi.apply(selectedFile);
			await loadPersons();
		} catch (e) {
			importError = e instanceof Error ? e.message : 'Import fehlgeschlagen';
		} finally {
			importing = false;
		}
	}

	// --- Organigramm ---
	let tree = $state<OrgTreeNode[]>([]);
	let treeLoaded = $state(false);

	async function loadTree() {
		tree = await organisationApi.getTree();
		treeLoaded = true;
	}

	$effect(() => {
		if (tab === 'organigramm' && !treeLoaded) loadTree();
	});
</script>

{#snippet treeNode(node: OrgTreeNode)}
	<li>
		<div class="flex items-center gap-2 py-1">
			<span style="color: var(--text-primary)">{node.full_name}</span>
			{#if node.team_size > 0}
				<span
					class="rounded-full px-2 py-0.5 text-xs"
					style="background: {node.team_too_small
						? 'var(--danger)'
						: 'var(--surface-glass-strong)'}; color: {node.team_too_small
						? 'white'
						: 'var(--text-muted)'}"
				>
					Team: {node.team_size}{node.team_too_small ? ' (< Schwelle)' : ''}
				</span>
			{/if}
		</div>
		{#if node.children.length > 0}
			<ul class="ml-5 border-l pl-4" style="border-color: var(--border-subtle)">
				{#each node.children as child (child.personalnummer)}
					{@render treeNode(child)}
				{/each}
			</ul>
		{/if}
	</li>
{/snippet}

<h1 class="mb-6 text-2xl font-bold" style="color: var(--text-primary)">
	Benutzerverwaltung & Organisation
</h1>

<div class="mb-6 flex gap-2">
	{#each [['personen', 'Personen'], ['import', 'SAP-Import'], ['organigramm', 'Organigramm']] as [id, label] (id)}
		<button
			onclick={() => (tab = id as Tab)}
			class="rounded-[var(--radius-sm)] px-4 py-2 text-sm"
			style="background: {tab === id ? 'var(--accent)' : 'var(--surface-glass)'}; color: {tab === id
				? 'var(--accent-contrast)'
				: 'var(--text-secondary)'}"
		>
			{label}
		</button>
	{/each}
</div>

{#if tab === 'personen'}
	<Card>
		<div class="mb-4 flex flex-wrap gap-2">
			<input
				type="text"
				placeholder="Suche (Name, Personalnummer)"
				bind:value={q}
				onkeyup={(e) => e.key === 'Enter' && loadPersons()}
				class="glass-surface rounded-[var(--radius-sm)] px-3 py-2 text-sm"
				style="color: var(--text-primary)"
			/>
			<select
				bind:value={fachbereich}
				onchange={loadPersons}
				class="glass-surface rounded-[var(--radius-sm)] px-3 py-2 text-sm"
				style="color: var(--text-primary)"
			>
				<option value="">Alle Fachbereiche</option>
				{#each fachbereiche as fb (fb)}
					<option value={fb}>{fb}</option>
				{/each}
			</select>
			<label class="flex items-center gap-2 text-sm" style="color: var(--text-secondary)">
				<input type="checkbox" bind:checked={onlyActive} onchange={loadPersons} />
				Nur aktive
			</label>
			<Button variant="secondary" onclick={loadPersons}>Suchen</Button>
		</div>

		<Table
			columns={[
				{ key: 'personalnummer', label: 'Personalnummer' },
				{ key: 'full_name', label: 'Name' },
				{ key: 'fachbereich', label: 'Fachbereich' },
				{ key: 'roles', label: 'Rollen', render: (r) => (r.roles as string[]).join(', ') },
				{ key: 'email', label: 'E-Mail', render: (r) => (r.email as string) ?? '—' }
			]}
			rows={persons as unknown as Record<string, unknown>[]}
			emptyText={loadingPersons ? 'Lädt…' : 'Keine Personen gefunden.'}
		/>
		<p class="mt-2 text-xs" style="color: var(--text-muted)">{total} Treffer</p>
	</Card>
{:else if tab === 'import'}
	<Card title="SAP-CSV-Import">
		<p class="mb-4 text-sm" style="color: var(--text-secondary)">
			Format (UTF-8, Semikolon): personalnummer;vorname;nachname;email;org_einheit;fachbereich;manager_personalnummer;standort;aktiv
		</p>
		<input type="file" accept=".csv" onchange={onFileSelected} class="mb-4 text-sm" />
		<div class="flex gap-2">
			<Button variant="secondary" onclick={runDryRun} disabled={!selectedFile || importing}>
				Trockenlauf (Vorschau)
			</Button>
			<Button variant="primary" onclick={applyImport} disabled={!diff || importing}>
				Übernehmen
			</Button>
		</div>

		{#if importError}
			<p class="mt-4 text-sm" style="color: var(--danger)">{importError}</p>
		{/if}

		{#if diff}
			<div class="mt-6 grid gap-4 md:grid-cols-4">
				<div class="glass-surface p-3 text-center">
					<div class="text-2xl font-bold" style="color: var(--success)">{diff.new.length}</div>
					<div class="text-xs" style="color: var(--text-muted)">Neu</div>
				</div>
				<div class="glass-surface p-3 text-center">
					<div class="text-2xl font-bold" style="color: var(--accent)">{diff.changed.length}</div>
					<div class="text-xs" style="color: var(--text-muted)">Geändert</div>
				</div>
				<div class="glass-surface p-3 text-center">
					<div class="text-2xl font-bold" style="color: var(--warning)">{diff.deactivated.length}</div>
					<div class="text-xs" style="color: var(--text-muted)">Deaktiviert</div>
				</div>
				<div class="glass-surface p-3 text-center">
					<div class="text-2xl font-bold" style="color: var(--text-secondary)">{diff.unchanged_count}</div>
					<div class="text-xs" style="color: var(--text-muted)">Unverändert</div>
				</div>
			</div>

			{#if diff.issues.length > 0}
				<div class="mt-4 glass-surface p-3">
					<p class="mb-2 text-sm font-semibold" style="color: var(--danger)">Plausibilitätshinweise</p>
					<ul class="list-inside list-disc text-sm" style="color: var(--text-secondary)">
						{#each diff.issues as issue (issue)}
							<li>{issue}</li>
						{/each}
					</ul>
				</div>
			{/if}
		{/if}
	</Card>
{:else if tab === 'organigramm'}
	<Card>
		{#if tree.length === 0}
			<p style="color: var(--text-secondary)">Kein Organigramm verfügbar.</p>
		{:else}
			<ul>
				{#each tree as root (root.personalnummer)}
					{@render treeNode(root)}
				{/each}
			</ul>
		{/if}
	</Card>
{/if}
