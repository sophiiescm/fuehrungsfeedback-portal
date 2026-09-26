<script lang="ts">
	// Angemeldete Person rechts oben (ab lg); auf Handy/Tablet steht der Name in der Kopfleiste.
	import { auth } from '$lib/stores/auth.svelte';
	import ThemeToggle from './ThemeToggle.svelte';
	import DevSwitcher from './DevSwitcher.svelte';
	import LanguagePicker from './LanguagePicker.svelte';

	let open = $state(false);
	const initials = $derived(
		(auth.user?.full_name ?? '?')
			.split(' ')
			.map((p) => p[0])
			.slice(0, 2)
			.join('')
			.toUpperCase()
	);
	const roleLabel = $derived(
		auth.hasRole('admin') ? 'Admin' : auth.hasRole('fuehrungskraft') ? 'Führungskraft' : 'Mitarbeiter'
	);
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && (open = false)} />

<div class="user fixed top-4 right-4 z-30 hidden lg:block">
	<button
		class="glass-surface flex items-center gap-3 py-1.5 pr-4 pl-1.5"
		style="border-radius: 999px; color: var(--text-primary)"
		aria-haspopup="menu"
		aria-expanded={open}
		onclick={() => (open = !open)}
	>
		<span class="avatar" aria-hidden="true">{initials}</span>
		<span class="text-left leading-tight">
			<span class="block text-sm font-semibold">{auth.user?.full_name ?? ''}</span>
			<span class="block text-xs" style="color: var(--text-secondary)">{roleLabel}</span>
		</span>
		<span aria-hidden="true" class="text-xs" style="color: var(--text-muted)">▾</span>
	</button>

	{#if open}
		<button class="fixed inset-0 -z-10 cursor-default" aria-label="Menü schließen" onclick={() => (open = false)}></button>
		<div class="glass-surface mt-2 flex w-64 flex-col gap-3 p-4" style="background: var(--surface-glass-strong)" role="menu">
			<div>
				<p class="text-sm font-semibold" style="color: var(--text-primary)">{auth.user?.full_name}</p>
				<p class="text-xs" style="color: var(--text-secondary)">{auth.user?.email ?? 'keine E-Mail hinterlegt'}</p>
				<p class="text-xs" style="color: var(--text-muted)">Personalnummer {auth.user?.personalnummer}</p>
			</div>
			<LanguagePicker />
			<DevSwitcher />
			<ThemeToggle />
			<button onclick={() => auth.logout()} class="rounded-[var(--radius-sm)] px-3 py-2 text-left text-sm" style="background: var(--surface-glass); color: var(--text-primary)" role="menuitem">Abmelden</button>
		</div>
	{/if}
</div>

<style>
	.avatar {
		display: inline-flex;
		width: 2.25rem;
		height: 2.25rem;
		align-items: center;
		justify-content: center;
		border-radius: 999px;
		background: var(--accent);
		color: var(--accent-contrast);
		font-size: 0.8rem;
		font-weight: 700;
	}
</style>
