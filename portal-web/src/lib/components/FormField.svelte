<script lang="ts">
	let {
		label,
		type = 'text',
		value = $bindable(''),
		placeholder = '',
		required = false,
		error = ''
	}: {
		label: string;
		type?: 'text' | 'email' | 'password' | 'number' | 'date';
		value?: string;
		placeholder?: string;
		required?: boolean;
		error?: string;
	} = $props();
</script>

<label class="flex flex-col gap-1 text-sm">
	<span style="color: var(--text-secondary)">{label}{required ? ' *' : ''}</span>
	<input
		{type}
		{placeholder}
		{required}
		bind:value
		class="glass-surface rounded-[var(--radius-sm)] px-3 py-2 text-sm outline-none"
		style="color: var(--text-primary)"
	/>
	{#if error}
		<span class="text-xs" style="color: var(--danger)">{error}</span>
	{/if}
</label>
