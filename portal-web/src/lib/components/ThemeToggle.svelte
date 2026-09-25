<script lang="ts">
	import { browser } from '$app/environment';

	type Theme = 'light' | 'dark' | 'system';

	let theme = $state<Theme>(browser ? ((localStorage.getItem('ffp_theme') as Theme) ?? 'system') : 'system');

	function apply(t: Theme) {
		if (!browser) return;
		if (t === 'system') {
			document.documentElement.removeAttribute('data-theme');
		} else {
			document.documentElement.setAttribute('data-theme', t);
		}
		localStorage.setItem('ffp_theme', t);
	}

	$effect(() => {
		apply(theme);
	});

	function cycle() {
		theme = theme === 'light' ? 'dark' : theme === 'dark' ? 'system' : 'light';
	}

	const labels: Record<Theme, string> = {
		light: '☀️ Hell',
		dark: '🌙 Dunkel',
		system: '💻 System'
	};
</script>

<button
	onclick={cycle}
	class="glass-surface rounded-[var(--radius-sm)] px-3 py-1.5 text-left text-xs"
	style="color: var(--text-secondary)"
>
	{labels[theme]}
</button>
