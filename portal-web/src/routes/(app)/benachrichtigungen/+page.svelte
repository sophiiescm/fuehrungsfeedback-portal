<script lang="ts">
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import { auth } from '$lib/stores/auth.svelte';
	import { notificationsApi, type Notification, type MailTemplate } from '$lib/api/rounds';

	let items = $state<Notification[]>([]);
	let templates = $state<MailTemplate[]>([]);
	let saved = $state('');
	onMount(async () => {
		items = await notificationsApi.mine();
		if (auth.hasRole('admin')) templates = await notificationsApi.templates();
	});
	async function markRead(n: Notification) {
		await notificationsApi.read(n.id);
		n.read_at = new Date().toISOString();
	}
	async function save(t: MailTemplate) {
		await notificationsApi.saveTemplate(t);
		saved = t.key;
	}
</script>

<h1 class="mb-6 text-2xl font-bold" style="color: var(--text-primary)">Benachrichtigungen</h1>
<div class="flex flex-col gap-3">
	{#each items as n (n.id)}
		<Card>
			<div class="flex items-start justify-between gap-2">
				<div>
					<p class:font-bold={!n.read_at} style="color: var(--text-primary)">{n.title}</p>
					<div class="text-sm" style="color: var(--text-secondary)">{@html n.body}</div>
				</div>
				{#if !n.read_at}<button class="text-xs" style="color: var(--accent-text)" onclick={() => markRead(n)}>Gelesen</button>{/if}
			</div>
		</Card>
	{:else}
		<Card><p style="color: var(--text-secondary)">Keine Benachrichtigungen.</p></Card>
	{/each}
</div>

{#if auth.hasRole('admin')}
	<h2 class="mt-10 mb-4 text-xl font-bold" style="color: var(--text-primary)">E-Mail-Vorlagen</h2>
	<div class="flex flex-col gap-3">
		{#each templates as t (t.key)}
			<Card title={t.key}>
				<input bind:value={t.subject} class="glass-surface mb-2 w-full rounded px-3 py-2 text-sm" style="color: var(--text-primary)" />
				<textarea bind:value={t.body_html} rows="4" class="glass-surface mb-2 w-full rounded px-3 py-2 text-sm" style="color: var(--text-primary)"></textarea>
				<Button onclick={() => save(t)}>Speichern</Button>
				{#if saved === t.key}<span class="ml-2 text-xs" style="color: var(--success)">Gespeichert</span>{/if}
			</Card>
		{/each}
	</div>
{/if}
