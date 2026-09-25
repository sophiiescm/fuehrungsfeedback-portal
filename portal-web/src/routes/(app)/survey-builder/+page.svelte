<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import { surveysApi, type SurveyTemplate } from '$lib/api/surveys';

	let templates = $state<SurveyTemplate[]>([]);
	let newName = $state('');
	let creating = $state(false);

	async function load() {
		templates = await surveysApi.listTemplates();
	}

	onMount(load);

	async function createTemplate() {
		if (!newName.trim()) return;
		creating = true;
		try {
			const template = await surveysApi.createTemplate(newName.trim());
			newName = '';
			await goto(`/survey-builder/${template.versions[0].id}`);
		} finally {
			creating = false;
		}
	}
</script>

<h1 class="mb-6 text-2xl font-bold" style="color: var(--text-primary)">Umfrage gestalten</h1>

<Card title="Neue Umfrage-Vorlage">
	<div class="flex gap-2">
		<input
			type="text"
			placeholder="Name der Vorlage"
			bind:value={newName}
			class="glass-surface flex-1 rounded-[var(--radius-sm)] px-3 py-2 text-sm"
			style="color: var(--text-primary)"
		/>
		<Button onclick={createTemplate} disabled={creating || !newName.trim()}>Anlegen</Button>
	</div>
</Card>

<div class="mt-6 grid gap-4">
	{#each templates as template (template.id)}
		<Card title={template.name}>
			<div class="flex flex-wrap gap-2">
				{#each template.versions as version (version.id)}
					<a
						href={`/survey-builder/${version.id}`}
						class="glass-surface rounded-[var(--radius-sm)] px-3 py-2 text-sm"
						style="color: var(--text-primary)"
					>
						Version {version.version_number}
						<span
							class="ml-2 rounded-full px-2 py-0.5 text-xs"
							style="background: {version.status === 'entwurf'
								? 'var(--success)'
								: 'var(--text-muted)'}; color: white"
						>
							{version.status === 'entwurf' ? 'Entwurf' : 'Gesperrt'}
						</span>
					</a>
				{/each}
			</div>
		</Card>
	{/each}
</div>
