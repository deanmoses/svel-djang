<script lang="ts">
	import { resolveHref } from '$lib/utils';
</script>

<footer class="site-footer">
	<div class="footer-inner">
		<nav class="footer-links">
			<a href={resolveHref('/licensing')}>Licensing</a>
			<a href={resolveHref('/terms')}>Terms</a>
			<a href={resolveHref('/privacy')}>Privacy</a>
			<a href={resolveHref('/api-docs')}>API</a>
		</nav>
		<p class="copyright">&copy; {new Date().getFullYear()} The Flip</p>
	</div>
</footer>

<style>
	.site-footer {
		border-top: 1px solid var(--color-border-soft);
		padding: var(--size-5) 0;
	}

	.footer-inner {
		max-width: 72rem;
		margin: 0 auto;
		padding: 0 var(--size-5);
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.footer-links {
		display: flex;
		gap: var(--size-5);
	}

	.footer-links a {
		color: var(--color-text-muted);
		font-size: var(--font-size-1);
		text-decoration: none;
	}

	.footer-links a:hover {
		color: var(--color-text-primary);
	}

	.copyright {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}

	@media (max-width: 640px) {
		.footer-inner {
			flex-direction: column;
			text-align: center;
			gap: var(--size-3);
		}
	}
</style>
