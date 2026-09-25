<script lang="ts">
	let {
		title = '',
		children
	}: {
		title?: string;
		children?: import('svelte').Snippet;
	} = $props();
</script>

<div class="glass-surface p-6">
	{#if title}
		<h2 class="mb-4 text-lg font-semibold" style="color: var(--text-primary)">{title}</h2>
	{/if}
	{@render children?.()}
</div>
