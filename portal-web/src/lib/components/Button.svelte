<script lang="ts">
	let {
		variant = 'primary',
		type = 'button',
		disabled = false,
		onclick,
		children
	}: {
		variant?: 'primary' | 'secondary' | 'danger';
		type?: 'button' | 'submit';
		disabled?: boolean;
		onclick?: (event: MouseEvent) => void;
		children?: import('svelte').Snippet;
	} = $props();

	const variantClass = $derived(
		{
			primary: 'btn-primary',
			secondary: 'btn-secondary',
			danger: 'btn-danger'
		}[variant]
	);
</script>

<button
	{type}
	{disabled}
	{onclick}
	class="rounded-[var(--radius-sm)] px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 {variantClass}"
>
	{@render children?.()}
</button>

<style>
	.btn-primary {
		background: var(--accent);
		color: var(--accent-contrast);
	}
	.btn-primary:hover:not(:disabled) {
		background: var(--accent-hover);
	}
	.btn-secondary {
		background: var(--surface-glass-strong);
		color: var(--text-primary);
		border: 1px solid var(--border-subtle);
	}
	.btn-secondary:hover:not(:disabled) {
		background: var(--surface-glass);
	}
	.btn-danger {
		background: var(--danger);
		color: white;
	}
</style>
