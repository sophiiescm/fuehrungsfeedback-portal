<script lang="ts">
	import { page } from '$app/state';
	import { auth, type Role } from '$lib/stores/auth.svelte';
	import ThemeToggle from './ThemeToggle.svelte';
	import DevSwitcher from './DevSwitcher.svelte';
	import LanguagePicker from './LanguagePicker.svelte';

	interface MenuItem {
		href: string;
		label: string;
		short: string;
		icon: string; // SVG-Pfad (24x24, Stroke)
		roles: Role[];
		perm?: string; // Admin-Recht, das fuer den Punkt noetig ist
		primary?: Role[]; // in der mobilen Tab-Leiste fuer diese Rollen
	}

	const ICONS = {
		home: 'M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z',
		chat: 'M4 5h16v11H9l-5 4z',
		chart: 'M4 20V10m6 10V4m6 16v-7m4 7H2',
		edit: 'M4 20h4L19 9l-4-4L4 16zm9-13l4 4',
		rounds: 'M4 12a8 8 0 1 0 3-6.2M4 4v4h4',
		users: 'M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm-6 9a6 6 0 0 1 12 0M17 11a3 3 0 1 0-1-5.8M18 20a6 6 0 0 0-3-5.2',
		bell: 'M6 9a6 6 0 0 1 12 0c0 6 2 7 2 7H4s2-1 2-7zm4 10a2 2 0 0 0 4 0',
		cog: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm7-3l2-1-2-4-2 .5-1.5-1.5.5-2-4-2-1 2h-2l-1-2-4 2 .5 2L5 8.5 3 8l-2 4 2 1v2l-2 1 2 4 2-.5L6.5 21l-.5 2 4 2 1-2h2l1 2 4-2-.5-2 1.5-1.5 2 .5 2-4-2-1z',
		more: 'M5 12h.01M12 12h.01M19 12h.01'
	};

	// Siehe CLAUDE.md "UI (Glassmorphism)" -> Sidebar-Tabelle je Rolle.
	const menuItems: MenuItem[] = [
		{ href: '/dashboard', label: 'Dashboard', short: 'Start', icon: ICONS.home, roles: ['admin', 'fuehrungskraft', 'mitarbeiter'], primary: ['admin', 'fuehrungskraft', 'mitarbeiter'] },
		{ href: '/feedbacks', label: 'Meine Feedbacks', short: 'Feedbacks', icon: ICONS.chat, roles: ['admin', 'fuehrungskraft', 'mitarbeiter'], primary: ['fuehrungskraft', 'mitarbeiter'] },
		{ href: '/reports', label: 'Meine Reports / Trend', short: 'Reports', icon: ICONS.chart, roles: ['fuehrungskraft'], primary: ['fuehrungskraft'] },
		{ href: '/massnahmen', label: 'Maßnahmen', short: 'Maßnahmen', icon: ICONS.rounds, roles: ['admin', 'fuehrungskraft', 'mitarbeiter'], primary: ['mitarbeiter'] },
		{ href: '/rounds', perm: 'rounds.manage', label: 'Befragungsrunden', short: 'Runden', icon: ICONS.rounds, roles: ['admin'], primary: ['admin'] },
		{ href: '/auswertung', perm: 'results.view', label: 'Auswertung & Benchmarking', short: 'Auswertung', icon: ICONS.chart, roles: ['admin'], primary: ['admin'] },
		{ href: '/survey-builder', perm: 'surveys.manage', label: 'Umfrage gestalten', short: 'Umfrage', icon: ICONS.edit, roles: ['admin'] },
		{ href: '/report-layout', perm: 'surveys.manage', label: 'Report-Layout', short: 'Report', icon: ICONS.edit, roles: ['admin'] },
		{ href: '/organisation', perm: 'users.manage', label: 'Benutzer & Organisation', short: 'Benutzer', icon: ICONS.users, roles: ['admin'] },
		{ href: '/benachrichtigungen', label: 'Benachrichtigungen', short: 'Mitteilungen', icon: ICONS.bell, roles: ['admin', 'fuehrungskraft', 'mitarbeiter'] },
		{ href: '/einstellungen', perm: 'settings.manage', label: 'Einstellungen', short: 'Einstellungen', icon: ICONS.cog, roles: ['admin'] }
	];

	const visibleItems = $derived(menuItems.filter((item) => item.roles.some((r) => auth.hasRole(r)) && (!item.perm || auth.can(item.perm))));
	// Tab-Leiste: Prioritaet Admin > Fuehrungskraft > Mitarbeiter, maximal 4 + "Mehr"
	const roleOrder: Role[] = ['admin', 'fuehrungskraft', 'mitarbeiter'];
	const mainRole = $derived(roleOrder.find((r) => auth.hasRole(r)) ?? 'mitarbeiter');
	const tabItems = $derived(visibleItems.filter((i) => i.primary?.includes(mainRole)).slice(0, 4));
	const active = (href: string) => page.url.pathname.startsWith(href);
	const moreActive = $derived(!tabItems.some((i) => active(i.href)));

	let sheetOpen = $state(false);
	$effect(() => {
		page.url.pathname;
		sheetOpen = false;
	});
</script>

{#snippet icon(path: string)}
	<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d={path} /></svg>
{/snippet}

<!-- Mobil/Tablet (< lg): kompakte Kopfleiste + Tab-Leiste unten (Daumenreichweite, iOS-Safe-Area).
     Ab lg: feste linke Sidebar. -->
<header class="glass-surface topbar fixed top-0 right-0 left-0 z-30 flex items-center justify-between px-4 lg:hidden" style="border-radius: 0;">
	<span class="text-base font-bold" style="color: var(--text-primary)">Führungsfeedback</span>
	<span class="truncate text-xs" style="color: var(--text-secondary)">{auth.user?.full_name ?? ''}</span>
</header>

<nav class="glass-surface tabbar fixed right-0 bottom-0 left-0 z-30 grid lg:hidden" style="border-radius: 0; grid-template-columns: repeat({tabItems.length + 1}, 1fr);" aria-label="Hauptnavigation">
	{#each tabItems as item (item.href)}
		<a href={item.href} class="tab" class:on={active(item.href)} aria-current={active(item.href) ? 'page' : undefined}>
			{@render icon(item.icon)}
			<span>{item.short}</span>
		</a>
	{/each}
	<button class="tab" class:on={moreActive || sheetOpen} onclick={() => (sheetOpen = !sheetOpen)} aria-expanded={sheetOpen}>
		{@render icon(ICONS.more)}
		<span>Mehr</span>
	</button>
</nav>

{#if sheetOpen}
	<button class="fixed inset-0 z-30 lg:hidden" style="background: rgba(0,0,0,0.35)" aria-label="Menü schließen" onclick={() => (sheetOpen = false)}></button>
	<div class="glass-surface sheet fixed right-3 left-3 z-40 flex flex-col gap-1 p-3 lg:hidden" style="background: var(--surface-glass-strong)">
		{#each visibleItems as item (item.href)}
			<a href={item.href} class="row" class:on={active(item.href)}>
				{@render icon(item.icon)}<span>{item.label}</span>
			</a>
		{/each}
		<div class="mt-2 flex flex-col gap-3 border-t pt-3" style="border-color: var(--border-subtle)"><LanguagePicker /><DevSwitcher /></div>
		<div class="mt-2 flex items-center justify-between border-t pt-3" style="border-color: var(--border-subtle)">
			<ThemeToggle />
			<button onclick={() => auth.logout()} class="px-3 py-2 text-sm" style="color: var(--text-secondary)">Abmelden</button>
		</div>
	</div>
{/if}

<aside class="glass-surface fixed top-4 bottom-4 left-4 z-20 hidden w-[var(--sidebar-width)] flex-col justify-between p-4 lg:flex">
	<div>
		<div class="mb-6 flex items-center gap-3 px-2 text-lg font-bold" style="color: var(--text-primary)"><span class="brand" aria-hidden="true"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="var(--accent-contrast)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16v11H9l-5 4z" /></svg></span>Führungsfeedback</div>
		<nav class="flex flex-col gap-1" aria-label="Hauptnavigation">
			{#each visibleItems as item (item.href)}
				<a href={item.href} class="row" class:on={active(item.href)}>
					{@render icon(item.icon)}<span>{item.label}</span>
				</a>
			{/each}
		</nav>
	</div>

	<div class="flex flex-col gap-3 border-t px-2 pt-4" style="border-color: var(--border-subtle)">
		<p class="text-xs" style="color: var(--text-muted)">Angemeldet als {auth.user?.full_name ?? ''} – Menü oben rechts.</p>
	</div>
</aside>

<style>
	.brand {
		display: inline-flex;
		width: 2.25rem;
		height: 2.25rem;
		align-items: center;
		justify-content: center;
		border-radius: 12px;
		background: var(--accent);
		font-size: 1.1rem;
		box-shadow: 0 4px 12px rgba(80, 130, 88, 0.35);
	}
	.topbar {
		padding-top: env(safe-area-inset-top);
		height: calc(3rem + env(safe-area-inset-top));
	}
	.tabbar {
		padding-bottom: env(safe-area-inset-bottom);
	}
	.tab {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 2px;
		min-height: 56px;
		font-size: 11px;
		color: var(--text-secondary);
		background: transparent;
	}
	.tab.on {
		color: var(--accent-text);
		font-weight: 600;
	}
	.sheet {
		bottom: calc(64px + env(safe-area-inset-bottom));
		max-height: 70vh;
		overflow-y: auto;
	}
	.row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		min-height: 44px;
		border-radius: var(--radius-sm);
		padding: 0.5rem 0.75rem;
		font-size: 0.875rem;
		color: var(--text-secondary);
	}
	.row:hover {
		background: var(--surface-glass-strong);
		color: var(--text-primary);
	}
	.row.on {
		background: var(--accent);
		color: var(--accent-contrast);
	}
</style>
