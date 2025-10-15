<script lang="ts">
	import { API_BASE } from '$lib/api';

	let { error = $bindable(), onDismiss }: { 
		error: string; 
		onDismiss?: () => void;
	} = $props();

	function dismissError() {
		error = '';
		onDismiss?.();
	}
</script>

{#if error}
	<div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
		<div class="flex items-start">
			<div class="flex-shrink-0">
				<svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
					<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
				</svg>
			</div>
			<div class="ml-3 flex-1">
				<h3 class="text-sm font-medium text-red-800 mb-2">Error Details</h3>
				<div class="text-sm text-red-700">
					<p class="font-mono bg-red-100 p-2 rounded text-xs overflow-x-auto">{error}</p>
				</div>
				<div class="mt-3 text-xs text-red-600">
					<p><strong>API Endpoint:</strong> {API_BASE}</p>
					<p><strong>Timestamp:</strong> {new Date().toLocaleString()}</p>
				</div>
			</div>
			<div class="ml-auto pl-3">
				<button
					onclick={dismissError}
					class="inline-flex text-red-400 hover:text-red-600 focus:outline-none focus:text-red-600"
				>
					<svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
						<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
					</svg>
				</button>
			</div>
		</div>
	</div>
{/if}
