<!-- src/routes/+page.svelte -->

<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { fetchGroups, createGroup, handleError } from '$lib/api';
	import type { Group } from '$lib/types';
	import ErrorDisplay from '$lib/components/ErrorDisplay.svelte';

	// State using runes
	let groups = $state<Group[]>([]);
	let error = $state('');
	let loading = $state(true);
	let showCreateForm = $state(false);
	let newGroupMembers = $state('');

	async function loadGroups() {
		try {
			loading = true;
			error = '';
			groups = await fetchGroups();
		} catch (err) {
			error = handleError(err, 'Failed to load groups');
		} finally {
			loading = false;
		}
	}

	async function handleCreateGroup() {
		if (!newGroupMembers.trim()) {
			error = 'Please enter at least one member name';
			return;
		}

		try {
			error = '';
			const members = newGroupMembers.split(',').map(name => name.trim()).filter(name => name);
			if (members.length === 0) {
				error = 'Please enter valid member names';
				return;
			}

			const newGroup = await createGroup({ people: members });
			groups = [...groups, newGroup];
			newGroupMembers = '';
			showCreateForm = false;
		} catch (err) {
			error = handleError(err, 'Failed to create group');
		}
	}

	onMount(loadGroups);
</script>

<svelte:head>
	<title>Receipt Helper - Groups</title>
</svelte:head>

<main class="container mx-auto p-6 bg-gray-50 min-h-screen">
	<!-- Header -->
	<div class="flex items-center justify-between mb-8">
		<div>
			<h1 class="text-4xl font-bold text-gray-800">Receipt Helper</h1>
			<p class="text-gray-600 mt-2">Manage and split expenses with your groups</p>
		</div>
		
		<button
			onclick={() => showCreateForm = true}
			class="bg-blue-500 text-white px-3 py-2 rounded-lg hover:bg-blue-600 transition-colors font-medium"
		>
			+ New Group
		</button>
	</div>

	<ErrorDisplay bind:error />

	{#if loading}
		<div class="flex justify-center items-center py-12">
			<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
		</div>
	{:else if groups.length === 0}
		<!-- Empty State -->
		<div class="text-center py-16">
			<div class="mx-auto w-24 h-24 bg-gray-100 rounded-full flex items-center justify-center mb-6">
				<svg class="w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
				</svg>
			</div>
			<h3 class="text-xl font-medium text-gray-900 mb-2">No groups found</h3>
			<p class="text-gray-500 mb-6">Create your first group to start splitting expenses</p>
			<button
				onclick={() => showCreateForm = true}
				class="bg-blue-500 text-white px-6 py-3 rounded-lg hover:bg-blue-600 transition-colors font-medium"
			>
				Create Your First Group
			</button>
		</div>
	{:else}
		<!-- Groups Grid -->
		<div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
			{#each groups as group}

				<a
					class="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow duration-200 cursor-pointer border border-gray-200"
          href={`/groups/${group.id}`}
				>
					<div class="p-6">
						<!-- Group Header -->
						<div class="flex items-start justify-between mb-4">
							<div>
								<h3 class="text-xl font-semibold text-gray-800 mb-1">
									{group.name}
								</h3>
								<p class="text-sm text-gray-500">
									Created {new Date(group.created_at).toLocaleDateString()}
								</p>
							</div>
							<div class="text-right">
								<div class="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
									ID: {group.slug}
								</div>
							</div>
						</div>

						<!-- Members -->
						<div class="mb-4">
							<h4 class="text-sm font-medium text-gray-700 mb-2">Members ({group.people.length})</h4>
							<div class="flex flex-wrap gap-1">
								{#each group.people as person}
									<span class="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded-full">
										{person}
									</span>
								{/each}
							</div>
						</div>

						<!-- Stats -->
						<div class="flex justify-between items-center pt-4 border-t border-gray-100">
							<div class="text-center">
								<div class="text-lg font-semibold text-gray-800">{group.receipts.length}</div>
								<div class="text-xs text-gray-500">Receipts</div>
							</div>
							<div class="text-center">
								<div class="text-lg font-semibold text-green-600">
									${group.receipts.reduce((total, receipt) => 
										total + receipt.entries.reduce((sum, entry) => sum + entry.price, 0), 0
									).toFixed(2)}
								</div>
								<div class="text-xs text-gray-500">Total</div>
							</div>
							<div class="text-center">
								<div class="text-lg font-semibold text-yellow-600">
									{group.receipts.filter(r => !r.processed).length}
								</div>
								<div class="text-xs text-gray-500">Pending</div>
							</div>
						</div>
					</div>
				</a>
			{/each}
		</div>
	{/if}

	<!-- Create Group Modal -->
	{#if showCreateForm}
		<div class="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
			<div class="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
				<h3 class="text-lg font-semibold text-gray-800 mb-4">Create New Group</h3>
				
				<div class="space-y-4">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-2">
							Group Members
						</label>
						<textarea
							bind:value={newGroupMembers}
							placeholder="Enter member names separated by commas (e.g., Alice, Bob, Charlie)"
							class="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
							rows="3"
						></textarea>
						<p class="text-xs text-gray-500 mt-1">
							The group name will default to "Group [ID]" but can be edited later
						</p>
					</div>
				</div>

				<div class="flex space-x-3 mt-6">
					<button
						onclick={handleCreateGroup}
						class="flex-1 bg-blue-500 text-white py-2 px-4 rounded-lg hover:bg-blue-600 transition-colors font-medium"
						disabled={!newGroupMembers.trim()}
					>
						Create Group
					</button>
					<button
						onclick={() => {
							showCreateForm = false;
							newGroupMembers = '';
							error = '';
						}}
						class="flex-1 bg-gray-300 text-gray-700 py-2 px-4 rounded-lg hover:bg-gray-400 transition-colors font-medium"
					>
						Cancel
					</button>
				</div>
			</div>
		</div>
	{/if}
</main>
