<script lang="ts">
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import { api, ApiError } from '$lib/api/client';

	interface Perm { key: string; label: string; hint: string }
	interface Role { id: number; name: string; description: string | null; permissions: string[]; is_system: boolean; members: number }
	interface Admin { person_id: number; personalnummer: string; full_name: string; aktiv: boolean; role_ids: number[]; permissions: string[] }
	interface Found { person_id: number; personalnummer: string; full_name: string }

	let perms = $state<Perm[]>([]);
	let roles = $state<Role[]>([]);
	let admins = $state<Admin[]>([]);
	let error = $state('');
	let info = $state('');

	// Rollen-Editor
	let editId = $state<number | null>(null);
	let name = $state('');
	let description = $state('');
	let selected = $state<string[]>([]);
	let editing = $state(false);

	// Person hinzufuegen
	let q = $state('');
	let found = $state<Found[]>([]);

	async function load() {
		perms = await api.get('/access/permissions');
		roles = await api.get('/access/roles');
		admins = await api.get('/access/admins');
	}
	onMount(load);

	async function guarded(fn: () => Promise<unknown>, ok = '') {
		error = '';
		info = '';
		try {
			await fn();
			info = ok;
			await load();
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Fehler';
		}
	}

	function newRole() {
		editing = true;
		editId = null;
		name = description = '';
		selected = [];
	}
	function editRole(r: Role) {
		editing = true;
		editId = r.id;
		name = r.name;
		description = r.description ?? '';
		selected = [...r.permissions];
	}
	const saveRole = () =>
		guarded(async () => {
			const body = { name, description: description || null, permissions: selected };
			if (editId) await api.put(`/access/roles/${editId}`, body);
			else await api.post('/access/roles', body);
			editing = false;
		}, 'Rolle gespeichert.');
	const removeRole = (r: Role) => guarded(() => api.delete(`/access/roles/${r.id}`), 'Rolle gelöscht.');
	const toggle = (k: string) => (selected = selected.includes(k) ? selected.filter((x) => x !== k) : [...selected, k]);

	const setRoles = (a: Admin, ids: number[]) => guarded(() => api.put(`/access/persons/${a.person_id}`, { role_ids: ids }), 'Gespeichert.');
	const toggleRoleFor = (a: Admin, id: number) =>
		setRoles(a, a.role_ids.includes(id) ? a.role_ids.filter((x) => x !== id) : [...a.role_ids, id]);

	async function search() {
		found = q.trim().length >= 2 ? await api.get(`/access/persons/search?q=${encodeURIComponent(q.trim())}`) : [];
	}
	const add = (p: Found) =>
		guarded(async () => {
			const light = roles.find((r) => r.name === 'Nur Auswertung') ?? roles[0];
			await api.put(`/access/persons/${p.person_id}`, { role_ids: [light.id] });
			q = '';
			found = [];
		}, 'Person hinzugefügt (Rolle „Nur Auswertung“ – bitte bei Bedarf anpassen).');
	const label = (k: string) => perms.find((p) => p.key === k)?.label ?? k;
</script>

<h1 class="mb-1 text-2xl font-bold" style="color: var(--text-primary)">Einstellungen · Nutzer & Rechte</h1>
<p class="mb-5 text-sm" style="color: var(--text-secondary)">Lege fest, wer im Verwaltungsbereich was tun darf. Rohantworten gibt es im Portal für niemanden – auch nicht für Admins.</p>
{#if error}<p class="mb-3 text-sm" style="color: var(--danger)">{error}</p>{/if}
{#if info}<p class="mb-3 text-sm" style="color: var(--success)">{info}</p>{/if}

<div class="flex flex-col gap-5">
	<Card title="Rollen">
		<ul class="flex flex-col gap-2">
			{#each roles as r (r.id)}
				<li class="item">
					<div class="flex-1">
						<p style="color: var(--text-primary)">{r.name} {#if r.is_system}<span class="chip">Standard</span>{/if} <span class="text-xs" style="color: var(--text-muted)">· {r.members} Person{r.members === 1 ? '' : 'en'}</span></p>
						{#if r.description}<p class="text-xs" style="color: var(--text-secondary)">{r.description}</p>{/if}
						<p class="mt-1 flex flex-wrap gap-1">{#each r.permissions as k}<span class="chip">{label(k)}</span>{/each}</p>
					</div>
					<Button variant="secondary" onclick={() => editRole(r)}>Bearbeiten</Button>
					{#if !r.is_system}<Button variant="danger" onclick={() => removeRole(r)}>Löschen</Button>{/if}
				</li>
			{/each}
		</ul>
		{#if !editing}<div class="mt-3"><Button onclick={newRole}>+ Neue Rolle</Button></div>{/if}
		{#if editing}
			<div class="mt-4 flex flex-col gap-3 rounded-[var(--radius-md)] p-3" style="background: var(--surface-glass-strong)">
				<input placeholder="Name der Rolle" bind:value={name} class="glass-surface rounded px-3 py-2" style="color: var(--text-primary)" />
				<input placeholder="Beschreibung (optional)" bind:value={description} class="glass-surface rounded px-3 py-2" style="color: var(--text-primary)" />
				<div class="flex flex-col gap-2">
					{#each perms as p (p.key)}
						<label class="flex items-start gap-3 text-sm" style="color: var(--text-primary)">
							<input type="checkbox" class="mt-1" checked={selected.includes(p.key)} onchange={() => toggle(p.key)} />
							<span>{p.label}<br /><span class="text-xs" style="color: var(--text-muted)">{p.hint}</span></span>
						</label>
					{/each}
				</div>
				<div class="flex gap-2"><Button onclick={saveRole} disabled={name.trim().length < 2}>Speichern</Button><Button variant="secondary" onclick={() => (editing = false)}>Abbrechen</Button></div>
			</div>
		{/if}
	</Card>

	<Card title="Personen mit Admin-Zugang">
		<ul class="flex flex-col gap-2">
			{#each admins as a (a.person_id)}
				<li class="item flex-col items-start!">
					<p style="color: var(--text-primary)">{a.full_name} <span class="text-xs" style="color: var(--text-muted)">· {a.personalnummer}{a.aktiv ? '' : ' · inaktiv'}</span></p>
					<div class="flex flex-wrap gap-2">
						{#each roles as r (r.id)}
							<button aria-pressed={a.role_ids.includes(r.id)} class="pill" class:on={a.role_ids.includes(r.id)} onclick={() => toggleRoleFor(a, r.id)}>{r.name}</button>
						{/each}
					</div>
					{#if a.role_ids.length === 0}<p class="text-xs" style="color: var(--warning)">Keine Rolle zugewiesen → Vollzugriff (Altbestand). Bitte eine Rolle wählen.</p>{/if}
					<button class="text-xs" style="color: var(--danger)" onclick={() => setRoles(a, [])}>Admin-Zugang entziehen</button>
				</li>
			{/each}
		</ul>
		<div class="mt-4">
			<p class="mb-1 text-sm font-semibold" style="color: var(--text-primary)">Person hinzufügen</p>
			<input placeholder="Name oder Personalnummer suchen" bind:value={q} oninput={search} class="glass-surface w-full rounded px-3 py-2" style="color: var(--text-primary)" />
			{#each found as p (p.person_id)}
				<div class="item mt-2"><span class="flex-1" style="color: var(--text-primary)">{p.full_name} <span class="text-xs" style="color: var(--text-muted)">· {p.personalnummer}</span></span><Button onclick={() => add(p)}>Hinzufügen</Button></div>
			{/each}
		</div>
	</Card>
</div>

<style>
	.item {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
		background: var(--surface-glass-strong);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-md);
		padding: 0.7rem 0.9rem;
	}
	.chip {
		border-radius: 999px;
		padding: 0.1rem 0.55rem;
		font-size: 0.7rem;
		background: var(--surface-glass);
		border: 1px solid var(--border-subtle);
		color: var(--text-secondary);
	}
	.pill {
		border-radius: 999px;
		min-height: 36px;
		padding: 0 0.9rem;
		font-size: 0.8rem;
		background: var(--surface-glass);
		border: 1px solid var(--border-subtle);
		color: var(--text-primary);
	}
	.pill.on {
		background: var(--accent);
		color: var(--accent-contrast);
	}
</style>
