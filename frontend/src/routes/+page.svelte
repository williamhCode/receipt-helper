<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { fetchGroups, createSampleData, handleError, type Group } from '$lib/utils.js';
	import ErrorDisplay from '$lib/components/ErrorDisplay.svelte';
	import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';

	// State using runes
	let groups = $state<Group[]>([]);
	let loading = $state(false);
	let error = $state('');

	async function loadGroups() {
		try {
			loading = true;
			error = '';
			groups = await fetchGroups();
		} catch (err) {
			error = handleError(err, 'Failed to fetch groups');
		} finally {
			loading = false;
		}
	}

	async function handleCreateSampleData() {
		try {
			loading = true;
			error = '';
			await createSampleData();
			await loadGroups();
		} catch (err) {
			error = handleError(err, 'Failed to create sample data');
		} finally {
			loading = false;
		}
	}

	function viewGroup(groupId: number) {
		goto(`/groups/${groupId}`);
	}

	onMount(() => {
		loadGroups();
	});
</script>

<main class="container mx-auto p-6 bg-gray-50 min-h-screen">
	<h1 class="text-3xl font-bold mb-6 text-gray-800">Receipt Helper</h1>

	<ErrorDisplay bind:error />

	{#if loading}
		<LoadingSpinner />
	{/if}

	<div class="bg-white p-6 rounded-lg shadow-md">
		<div class="flex justify-between items-center mb-6">
			<h2 class="text-xl font-semibold text-gray-700">Your Groups</h2>
			<button 
				onclick={handleCreateSampleData}
				class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:opacity-50 transition-colors"
				disabled={loading}
			>
				Create Sample Data
			</button>
		</div>

		{#if groups.length === 0 && !loading}
			<div class="text-center py-12">
				<div class="text-gray-400 mb-4">
					<svg class="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
					</svg>
				</div>
				<h3 class="text-lg font-medium text-gray-900 mb-2">No groups found</h3>
				<p class="text-gray-500 mb-4">Create some sample data to get started!</p>
			</div>
		{:else}
			<div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
				{#each groups as group}
					<div 
						class="border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-all duration-200 cursor-pointer hover:border-blue-300"
						onclick={() => viewGroup(group.id)}
						onkeydown={(e) => e.key === 'Enter' && viewGroup(group.id)}
						role="button"
						tabindex="0"
					>
						<div class="flex justify-between items-start mb-4">
							<h3 class="text-lg font-semibold text-gray-800">Group {group.id}</h3>
							<span class="text-xs text-gray-500 font-mono bg-gray-100 px-2 py-1 rounded">
								{group.slug}
							</span>
						</div>
						
						<div class="space-y-3">
							<div>
								<p class="text-sm text-gray-600 mb-1">
									<span class="font-medium">People:</span>
								</p>
								<div class="flex flex-wrap gap-2">
									{#each group.people as person}
										<span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full">
											{person}
										</span>
									{/each}
								</div>
							</div>
							
							<div class="flex justify-between items-center text-sm">
								<span class="text-gray-600">
									<span class="font-medium">Receipts:</span> {group.receipts.length}
								</span>
								<span class="text-blue-600 font-medium">
									View Details →
								</span>
							</div>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</main>
