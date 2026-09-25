<script lang="ts">
	import { page } from '$app/state';
	import { auth, type Role } from '$lib/stores/auth.svelte';
	import ThemeToggle from './ThemeToggle.svelte';

	interface MenuItem {
		href: string;
		label: string;
		roles: Role[];
	}

	// Siehe CLAUDE.md "UI (Glassmorphism)" -> Sidebar-Tabelle je Rolle.
	const menuItems: MenuItem[] = [
		{ href: '/dashboard', label: 'Dashboard', roles: ['admin', 'fuehrungskraft', 'mitarbeiter'] },
		{ href: '/feedbacks', label: 'Meine Feedbacks', roles: ['admin', 'fuehrungskraft', 'mitarbeiter'] },
		{ href: '/reports', label: 'Meine Reports / Trend', roles: ['fuehrungskraft'] },
		{ href: '/survey-builder', label: 'Umfrage gestalten', roles: ['admin'] },
		{ href: '/rounds', label: 'Befragungsrunden', roles: ['admin'] },
		{ href: '/organisation', label: 'Benutzerverwaltung & Organisation', roles: ['admin'] },
		{ href: '/auswertung', label: 'Auswertung & Benchmarking', roles: ['admin'] },
		{ href: '/benachrichtigungen', label: 'Benachrichtigungen', roles: ['admin', 'fuehrungskraft', 'mitarbeiter'] },
		{ href: '/einstellungen', label: 'Einstellungen', roles: ['admin'] }
	];

	const visibleItems = $derived(menuItems.filter((item) => item.roles.some((r) => auth.hasRole(r))));

	let mobileOpen = $state(false);

	$effect(() => {
		// Menue nach Navigation auf dem Smartphone automatisch schliessen
		page.url.pathname;
		mobileOpen = false;
	});
</script>

<!-- Mobil: feste obere Leiste mit Hamburger-Menue. Ab md: feste linke Sidebar
     (CLAUDE.md: "Responsiv. Die Teilnahme muss auf dem Smartphone ... gut
     funktionieren."). -->
<header
	class="glass-surface fixed top-0 right-0 left-0 z-30 flex items-center justify-between px-4 py-3 md:hidden"
	style="border-radius: 0;"
>
	<span class="text-lg font-bold" style="color: var(--text-primary)">Führungsfeedback</span>
	<button
		onclick={() => (mobileOpen = !mobileOpen)}
		class="rounded-[var(--radius-sm)] px-3 py-2 text-sm"
		style="color: var(--text-primary)"
		aria-label="Menü öffnen"
	>
		{mobileOpen ? '✕' : '☰'}
	</button>
</header>

<aside
	class="glass-surface fixed top-4 bottom-4 left-4 z-20 hidden w-[var(--sidebar-width)] flex-col justify-between p-4 md:flex"
>
	<div>
		<div class="mb-6 px-2 text-lg font-bold" style="color: var(--text-primary)">
			Führungsfeedback
		</div>
		<nav class="flex flex-col gap-1">
			{#each visibleItems as item (item.href)}
				<a
					href={item.href}
					class="rounded-[var(--radius-sm)] px-3 py-2 text-sm transition-colors"
					class:active={page.url.pathname.startsWith(item.href)}
				>
					{item.label}
				</a>
			{/each}
		</nav>
	</div>

	<div class="flex flex-col gap-3 border-t px-2 pt-4" style="border-color: var(--border-subtle)">
		<div class="text-sm" style="color: var(--text-secondary)">{auth.user?.full_name ?? ''}</div>
		<ThemeToggle />
		<button onclick={() => auth.logout()} class="text-left text-sm" style="color: var(--text-muted)">
			Abmelden
		</button>
	</div>
</aside>

{#if mobileOpen}
	<nav class="glass-surface fixed top-16 right-4 left-4 z-30 flex flex-col gap-1 p-3 md:hidden">
		{#each visibleItems as item (item.href)}
			<a
				href={item.href}
				class="rounded-[var(--radius-sm)] px-3 py-2 text-sm"
				class:active={page.url.pathname.startsWith(item.href)}
			>
				{item.label}
			</a>
		{/each}
		<div class="mt-2 flex items-center justify-between border-t pt-3" style="border-color: var(--border-subtle)">
			<ThemeToggle />
			<button onclick={() => auth.logout()} class="text-sm" style="color: var(--text-muted)">
				Abmelden
			</button>
		</div>
	</nav>
{/if}

<style>
	nav a {
		color: var(--text-secondary);
	}
	nav a:hover {
		background: var(--surface-glass-strong);
		color: var(--text-primary);
	}
	nav a.active {
		background: var(--accent);
		color: var(--accent-contrast);
	}
</style>
