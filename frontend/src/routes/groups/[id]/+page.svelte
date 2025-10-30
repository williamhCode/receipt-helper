<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import {
		fetchGroup,
		fetchGroupVersion,
		getReceipt,
		createReceipt,
		updateGroup,
		updateReceipt,
		updateReceiptPaidBy,
		updateReceiptEntryDetails,
		createReceiptEntry,
		deleteReceiptEntry,
		deleteReceipt,
		deleteGroup,
		handleError
	} from '$lib/api';
	import {
		calculateCombinedCosts,
		calculateReceiptCosts,
		calculateReceiptTotal,
		getInitials
	} from '$lib/utils';
	import type { Group, Receipt, ReceiptEntry } from '$lib/types';
	import { pollingStore } from '$lib/stores/polling.svelte';
	import ErrorDisplay from '$lib/components/ErrorDisplay.svelte';
	import NewReceiptModal from '$lib/components/NewReceiptModal.svelte';
	import GroupMembersManager from '$lib/components/GroupMembersManager.svelte';
	import ReceiptMembersManager from '$lib/components/ReceiptMembersManager.svelte';
	import EditableGroupName from '$lib/components/EditableGroupName.svelte';

	// ============================================================================
	// State
	// ============================================================================
	
	let group = $state<Group | null>(null);
	let error = $state('');
	let showNewReceiptForm = $state(false);
	let editingEntry = $state<{ receiptId: number; entryId: number; field: 'name' | 'price' } | null>(null);
	let editingValue = $state('');
	let updatingEntries = $state(new Set<number>());
	let currentReceiptIndex = $state(0);

	const groupId = $derived(parseInt($page.params.id));
	const currentReceipt = $derived(group?.receipts[currentReceiptIndex] ?? null);
	const hasReceipts = $derived(group && group.receipts.length > 0);
	const canGoLeft = $derived(currentReceiptIndex > 0);
	const canGoRight = $derived(group && currentReceiptIndex < group.receipts.length - 1);

	// ============================================================================
	// Data fetching
	// ============================================================================
	
	async function refreshGroup() {
		try {
			error = '';
			const updatedGroup = await fetchGroup(groupId);
			group = updatedGroup;
		} catch (err) {
			error = handleError(err, 'Failed to refresh group');
		}
	}

	async function refreshCurrentReceipt() {
		try {
			if (!group || !currentReceipt) return;

			error = '';

			// Fetch receipt and group version in parallel
			const [updatedReceipt, versionData] = await Promise.all([
				getReceipt(currentReceipt.id),
				fetchGroupVersion(groupId)
			]);

			// Update only the current receipt in the group
			const receiptIndex = group.receipts.findIndex(r => r.id === currentReceipt.id);
			if (receiptIndex !== -1) {
				group.receipts[receiptIndex] = updatedReceipt;
				group = group; // Trigger Svelte reactivity
			}

			// Update polling store so next poll doesn't trigger unnecessary refresh
			pollingStore.updateVersion(versionData.updated_at);
		} catch (err) {
			error = handleError(err, 'Failed to refresh receipt');
		}
	}

	// ============================================================================
	// API call wrappers (handle errors consistently)
	// ============================================================================

	async function apiCall(fn: () => Promise<any>, errorMessage: string) {
		try {
			error = '';
			await fn();
			await refreshGroup(); // Refresh UI after successful operation
		} catch (err) {
			error = handleError(err, errorMessage);
		}
	}

	async function receiptApiCall(fn: () => Promise<any>, errorMessage: string) {
		try {
			error = '';
			await fn();
			await refreshCurrentReceipt();
		} catch (err) {
			error = handleError(err, errorMessage);
		}
	}

	// ============================================================================
	// Group handlers
	// ============================================================================
	
	function handleGroupNameUpdate(newName: string) {
		if (group) {
			group.name = newName;
			group = group;
		}
	}

	function handleUpdateGroupMembers(newPeople: string[]) {
		if (!group) return;
		return apiCall(
			async () => {
        group = await updateGroup(groupId, { people: newPeople })
      },
			'Failed to update group members'
		);
	}

	function handlePersonRenamed() {
		return refreshGroup();
	}

	function removeGroup() {
		if (!group) return;
		if (!confirm(`Delete group "${group.name}"? This will delete all receipts and cannot be undone.`)) return;
		
		apiCall(
			async () => {
				await deleteGroup(groupId);
				goto('/');
			},
			'Failed to delete group'
		);
	}

	// ============================================================================
	// Receipt handlers
	// ============================================================================
	
	function handleUpdateReceiptMembers(receiptId: number, newPeople: string[]) {
		if (!group) return;
		return receiptApiCall(
			() => updateReceipt(receiptId, { people: newPeople }),
			'Failed to update receipt members'
		);
	}

	function handleToggleProcessed(receiptId: number, currentStatus: boolean) {
		if (!group) return;
		return receiptApiCall(
			() => updateReceipt(receiptId, { processed: !currentStatus }),
			'Failed to update receipt status'
		);
	}

	async function handleCreateReceipt(data: { name: string; paidBy: string; entries: string; people: string[] }) {
		if (!group) return;

		try {
			error = '';

			let entries = [];
			if (data.entries.trim()) {
				entries = JSON.parse(data.entries);
			}

			const receiptData = {
				processed: false,
				name: data.name,
				raw_data: null,
				paid_by: data.paidBy || null,
				people: data.people,
				entries: entries,
			};

			await createReceipt(groupId, receiptData);
			await refreshGroup(); // Refresh UI to show new receipt
		} catch (err) {
			error = handleError(err, 'Failed to create receipt');
		}
	}

	function handlePaidByChange(receiptId: number, newValue: string) {
		if (!group) return;
		const newPaidBy = newValue.trim() || null;
		return receiptApiCall(
			() => updateReceiptPaidBy(receiptId, newPaidBy),
			'Failed to update paid by'
		);
	}

	function removeReceipt(receiptId: number, receiptName: string) {
		if (!confirm(`Delete receipt "${receiptName}"? This cannot be undone.`)) return;
		return apiCall(
			() => deleteReceipt(receiptId),
			'Failed to delete receipt'
		);
	}

	// ============================================================================
	// Entry handlers
	// ============================================================================
	
	async function updateAssignment(receiptId: number, entryId: number, person: string, assigned: boolean) {
		if (!group || updatingEntries.has(entryId)) return;

		try {
			updatingEntries.add(entryId);

			const receipt = group.receipts.find(r => r.id === receiptId);
			if (!receipt) return;
			const entry = receipt.entries.find(e => e.id === entryId);
			if (!entry) return;

			let newAssignedTo = [...entry.assigned_to];
			if (assigned && !newAssignedTo.includes(person)) {
				newAssignedTo.push(person);
			} else if (!assigned) {
				newAssignedTo = newAssignedTo.filter(p => p !== person);
			}

			// Optimistic update
			entry.assigned_to = newAssignedTo;
			group = group;

			await updateReceiptEntryDetails(entryId, { assigned_to: newAssignedTo });

			// Fetch group version and update polling store
			const versionData = await fetchGroupVersion(groupId);
			pollingStore.updateVersion(versionData.updated_at);

		} catch (err) {
			error = handleError(err, 'Failed to update assignment');
			await refreshCurrentReceipt(); // Only refresh current receipt on error
		} finally {
			updatingEntries.delete(entryId);
		}
	}

	function startEditEntry(receiptId: number, entryId: number, field: 'name' | 'price', currentValue: string | number) {
		editingEntry = { receiptId, entryId, field };
		editingValue = String(currentValue);
	}

	async function saveEntry() {
		if (!editingEntry || !group) return;

		try {
			const { entryId, field } = editingEntry;

			if (field === 'name') {
				await updateReceiptEntryDetails(entryId, { name: editingValue.trim() });
			} else if (field === 'price') {
				const price = parseFloat(editingValue);
				if (isNaN(price) || price < 0) {
					throw new Error('Invalid price');
				}
				await updateReceiptEntryDetails(entryId, { price });
			}

			cancelEditEntry();
			await refreshCurrentReceipt(); // Only refresh current receipt
		} catch (err) {
			error = handleError(err, 'Failed to update entry');
		}
	}

	function cancelEditEntry() {
		editingEntry = null;
		editingValue = '';
	}

	function toggleTaxable(entryId: number, currentTaxable: boolean) {
		return receiptApiCall(
			() => updateReceiptEntryDetails(entryId, { taxable: !currentTaxable }),
			'Failed to toggle taxable'
		);
	}

	function addNewEntry(receiptId: number) {
		return receiptApiCall(
			() => createReceiptEntry(receiptId, { name: 'New Item', price: 0, taxable: false }),
			'Failed to add new entry'
		);
	}

	function removeEntry(entryId: number) {
		if (!confirm('Delete this item?')) return;
		return receiptApiCall(
			() => deleteReceiptEntry(entryId),
			'Failed to delete entry'
		);
	}

	// ============================================================================
	// Navigation functions
	// ============================================================================

	function goToPreviousReceipt() {
		if (canGoLeft) {
			currentReceiptIndex--;
		}
	}

	function goToNextReceipt() {
		if (canGoRight) {
			currentReceiptIndex++;
		}
	}

	function selectReceipt(index: number) {
		if (group && index >= 0 && index < group.receipts.length) {
			currentReceiptIndex = index;
		}
	}

	// ============================================================================
	// Utility functions
	// ============================================================================

	function handleKeydown(e: KeyboardEvent, saveFunc: () => void, cancelFunc: () => void) {
		if (e.key === 'Enter') {
			e.preventDefault();
			saveFunc();
		} else if (e.key === 'Escape') {
			e.preventDefault();
			cancelFunc();
		}
	}

	// ============================================================================
	// Lifecycle
	// ============================================================================

	async function initializePolling() {
		pollingStore.onGroupChanged = refreshGroup;
		pollingStore.start(groupId);
	}

	onMount(async () => {
		await refreshGroup();
		initializePolling();
	});

	onDestroy(() => {
		pollingStore.stop();
	});
</script>

<style>
	input[type='number']::-webkit-inner-spin-button,
	input[type='number']::-webkit-outer-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}
	
	input[type='number'] {
		-moz-appearance: textfield;
	}
</style>

<main class="container mx-auto p-6 bg-gray-50 min-h-screen">
	<!-- Header -->
	<div class="flex items-center justify-between mb-6">
		<div class="flex items-center space-x-4">
			<button
				onclick={() => goto('/')}
				class="text-blue-600 hover:text-blue-800 flex items-center space-x-2"
				aria-label="Go back to groups list"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
				</svg>
			</button>
			
			{#if group}
				<EditableGroupName
					{groupId}
					initialName={group.name}
					onNameUpdate={handleGroupNameUpdate}
				/>

				{#if pollingStore.isPolling}
					<span class="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full flex items-center space-x-1">
						<div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
						<span>Live</span>
					</span>
				{:else if pollingStore.isPaused}
					<span class="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded-full flex items-center space-x-1">
						<div class="w-2 h-2 bg-yellow-500 rounded-full"></div>
						<span>Paused</span>
					</span>
				{:else if pollingStore.hasError}
					<span class="text-xs bg-red-100 text-red-800 px-2 py-1 rounded-full flex items-center space-x-1">
						<div class="w-2 h-2 bg-red-500 rounded-full"></div>
						<span>Error</span>
					</span>
				{:else}
					<span class="text-xs bg-gray-100 text-gray-800 px-2 py-1 rounded-full">
						Offline
					</span>
				{/if}
			{/if}
		</div>
		
		<div class="flex items-center gap-2">
			<button
				onclick={() => showNewReceiptForm = true}
				class="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 transition-colors"
			>
				+ New Receipt
			</button>
			{#if group}
				<button
					onclick={removeGroup}
					class="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600 transition-colors"
					title="Delete group"
				>
					🗑️ Delete Group
				</button>
			{/if}
		</div>
	</div>

	<ErrorDisplay bind:error />

	{#if group}
		<!-- Top Section: Group Info & Combined Costs -->
		<div class="grid lg:grid-cols-2 gap-6 mb-6">
			<!-- Group Info -->
			<div class="bg-white p-6 rounded-lg shadow-md">
				<GroupMembersManager 
					bind:people={group.people} 
					onUpdate={handleUpdateGroupMembers}
					onPersonRenamed={handlePersonRenamed}
					{group}
				/>
				
				<div class="space-y-2 mt-4 pt-4 border-t">
					<p><span class="font-medium text-lg">Group ID:</span> <span class="font-mono text-sm bg-gray-100 px-2 py-1 rounded">{group.slug}</span></p>
					<p><span class="font-medium text-lg">Total Receipts:</span> {group.receipts.length}</p>
				</div>
			</div>

			<!-- Combined Cost Breakdown -->
			<div class="bg-gradient-to-br from-blue-50 to-indigo-50 p-6 rounded-lg border border-blue-200 h-[300px] flex flex-col">
				<h3 class="text-2xl font-semibold text-gray-700 mb-4 flex-shrink-0">Combined Balance</h3>
				<div class="flex flex-wrap overflow-y-auto flex-1 -m-1.5 content-start">
					{#each Object.entries(calculateCombinedCosts(group)) as [person, amount]}
						<div class="w-full sm:w-[calc(50%-0.75rem)] m-1.5 bg-white p-3 rounded-lg shadow-sm max-h-20">
							<div class="flex justify-between items-center">
								<div class="flex items-center space-x-2">
									<span class="font-medium text-xs bg-blue-200 text-blue-900 w-7 h-7 rounded-full flex items-center justify-center">
										{getInitials(person)}
									</span>
									<span class="font-medium text-lg text-gray-700">{person}:</span>
								</div>
								<span class="font-mono font-semibold text-xl"
									class:text-green-600={amount < 0}
									class:text-red-600={amount > 0}
									class:text-gray-800={amount === 0}>
									{amount < 0 ? '+' : ''}{Math.abs(amount).toFixed(2)}
								</span>
							</div>
							<div class="text-sm text-gray-500 mt-1 ml-9">
								{amount < 0 ? 'Is owed' : amount > 0 ? 'Owes' : 'Even'}
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>

		<!-- Bottom Section: Receipt List + Receipt Detail + Cost Breakdown -->
		<div class="grid lg:grid-cols-[minmax(200px,250px)_minmax(400px,1fr)_minmax(250px,300px)] gap-6">
			<!-- Receipt List (Left Sidebar) -->
			<div class="bg-white rounded-lg shadow-md overflow-hidden h-[900px] flex flex-col">
				<div class="p-4 border-b bg-gray-50 flex-shrink-0">
					<h3 class="text-lg font-semibold text-gray-700">Receipts ({group.receipts.length})</h3>
				</div>

				{#if group.receipts.length === 0}
					<div class="p-8 text-center text-gray-500 flex-1 flex items-center justify-center flex-col">
						<svg class="w-12 h-12 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
						</svg>
						<p class="text-sm">No receipts yet</p>
					</div>
				{:else}
					<div class="overflow-y-auto flex-1">
						{#each group.receipts as receipt, index}
							<button
								onclick={() => selectReceipt(index)}
								class="w-full p-4 text-left border-b hover:bg-gray-50 transition-colors"
								class:bg-blue-50={currentReceiptIndex === index}
								class:border-l-4={currentReceiptIndex === index}
								class:border-l-blue-500={currentReceiptIndex === index}
							>
								<div class="flex justify-between items-start mb-1">
									<h4 class="font-medium text-gray-900 truncate">{receipt.name}</h4>
									<span
										class="text-xs px-2 py-0.5 rounded-full flex-shrink-0 ml-2"
										class:bg-green-100={receipt.processed}
										class:text-green-800={receipt.processed}
										class:bg-yellow-100={!receipt.processed}
										class:text-yellow-800={!receipt.processed}
									>
										{receipt.processed ? '✓' : '○'}
									</span>
								</div>
								<p class="text-xs text-gray-500">{new Date(receipt.created_at).toLocaleDateString()}</p>
								<p class="text-xs text-gray-600 mt-1">{receipt.entries.length} items</p>
							</button>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Single Receipt Detail View (Middle) -->
			<div class="bg-white rounded-lg shadow-md h-[900px] flex flex-col">
				{#if !hasReceipts}
					<div class="p-12 text-center text-gray-500 flex-1 flex items-center justify-center flex-col">
						<svg class="w-16 h-16 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
						</svg>
						<h4 class="text-lg font-medium text-gray-900 mb-2">No receipts found</h4>
						<p class="text-gray-500">Create a new receipt to get started!</p>
					</div>
				{:else if currentReceipt}
					{@const receipt = currentReceipt}
					<!-- Receipt Navigation Header -->
					<div class="p-4 border-b bg-gray-50 flex items-center justify-between flex-shrink-0">
						<button
							onclick={goToPreviousReceipt}
							disabled={!canGoLeft}
							class="p-2 rounded hover:bg-gray-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
							title="Previous receipt"
						>
							<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
							</svg>
						</button>

						<span class="text-sm text-gray-600">
							Receipt {currentReceiptIndex + 1} of {group.receipts.length}
						</span>

						<button
							onclick={goToNextReceipt}
							disabled={!canGoRight}
							class="p-2 rounded hover:bg-gray-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
							title="Next receipt"
						>
							<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
							</svg>
						</button>
					</div>

					<!-- Receipt Content (Scrollable) -->
					<div class="p-6 overflow-y-auto flex-1">
						<!-- Receipt Header -->
						<div class="flex justify-between items-start mb-4">
									<div>
										<h4 class="text-lg font-semibold text-gray-800">{receipt.name}</h4>
										<p class="text-sm text-gray-500">{new Date(receipt.created_at).toLocaleDateString()}</p>
									</div>
									<div class="flex items-center gap-2">
										<button
											onclick={() => handleToggleProcessed(receipt.id, receipt.processed)}
											class="text-xs px-2 py-1 rounded-full cursor-pointer transition-all hover:shadow-md"
											class:bg-green-100={receipt.processed}
											class:text-green-800={receipt.processed}
											class:hover:bg-green-200={receipt.processed}
											class:bg-yellow-100={!receipt.processed}
											class:text-yellow-800={!receipt.processed}
											class:hover:bg-yellow-200={!receipt.processed}
											title={receipt.processed ? 'Mark as unprocessed' : 'Mark as processed'}
										>
											{receipt.processed ? 'Processed' : 'Pending'}
										</button>
										<button
											onclick={() => removeReceipt(receipt.id, receipt.name)}
											class="text-xs px-2 py-1 rounded-full bg-red-100 text-red-800 hover:bg-red-200 cursor-pointer transition-all"
											title="Delete receipt"
										>
											🗑️
										</button>
									</div>
								</div>

								<!-- Receipt Members -->
								<div class="mb-4">
									<ReceiptMembersManager 
										bind:receiptPeople={receipt.people}
										groupPeople={group.people}
										onUpdate={(newPeople) => handleUpdateReceiptMembers(receipt.id, newPeople)}
									/>
								</div>

								<!-- Paid By -->
								<div class="mb-4">
									<div class="flex items-center gap-2 text-sm">
										<span class="font-medium">Paid by:</span>
										<select 
											value={receipt.paid_by || ""}
											onchange={(e) => handlePaidByChange(receipt.id, e.currentTarget.value)}
											class="text-xs px-2 py-1 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
										>
											<option value="">None</option>
											{#each receipt.people as person}
												<option value={person}>{person}</option>
											{/each}
										</select>
									</div>
								</div>

								<!-- Items Table -->
								<div class="mb-4">
									<h5 class="font-medium text-gray-700 mb-2">Items</h5>
									<div class="bg-white rounded border border-gray-200 overflow-hidden">
										<table class="w-full text-xs">
											<thead class="bg-gray-50">
												<tr>
													<th class="p-2 text-left font-medium text-gray-700">Item</th>
													<th class="p-2 text-right font-medium text-gray-700 w-16">Price</th>
													<th class="p-2 text-center font-medium text-gray-700 w-10">Tax</th>
													{#each receipt.people as person}
														<th class="p-2 text-center font-medium text-gray-700 w-10" title={person}>{getInitials(person)}</th>
													{/each}
													<th class="p-2 text-center font-medium text-gray-700 w-10">Del</th>
												</tr>
											</thead>
											<tbody>
												{#each receipt.entries as entry}
													<tr 
														class="border-t border-gray-100 hover:bg-gray-50 transition-colors"
														data-entry-id={entry.id}
													>
														<!-- Editable Item Name -->
														<td class="p-2 text-gray-800 text-xs" title={entry.name}>
															{#if editingEntry?.entryId === entry.id && editingEntry?.field === 'name'}
																<input
																	type="text"
																	bind:value={editingValue}
																	onblur={saveEntry}
																	onkeydown={(e) => handleKeydown(e, saveEntry, cancelEditEntry)}
																	class="w-full px-1 py-0.5 border rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
																	autofocus
																/>
															{:else}
																<button
																	onclick={() => startEditEntry(receipt.id, entry.id, 'name', entry.name)}
																	class="text-left w-full hover:bg-blue-50 px-1 py-0.5 rounded"
																	title="Click to edit"
																>
																	{entry.name}
																</button>
															{/if}
														</td>
														
														<!-- Editable Price -->
														<td class="p-2 text-gray-800 font-mono text-xs text-right w-16">
															{#if editingEntry?.entryId === entry.id && editingEntry?.field === 'price'}
																<input
																	type="number"
																	step="0.01"
																	bind:value={editingValue}
																	onblur={saveEntry}
																	onkeydown={(e) => handleKeydown(e, saveEntry, cancelEditEntry)}
																	class="w-full px-1 py-0.5 border rounded text-right focus:outline-none focus:ring-1 focus:ring-blue-500"
																	autofocus
																/>
															{:else}
																<button
																	onclick={() => startEditEntry(receipt.id, entry.id, 'price', entry.price)}
																	class="w-full text-right hover:bg-blue-50 px-1 py-0.5 rounded"
																	title="Click to edit"
																>
																	${entry.price.toFixed(2)}
																</button>
															{/if}
														</td>
														
														<!-- Tax Toggle -->
														<td class="p-2 text-center w-10">
															<button
																onclick={() => toggleTaxable(entry.id, entry.taxable)}
																class="w-3 h-3 rounded-full inline-block cursor-pointer hover:opacity-75"
																class:bg-green-500={entry.taxable}
																class:bg-gray-300={!entry.taxable}
																title={entry.taxable ? 'Taxable' : 'Not taxable'}
															/>
														</td>
														
														<!-- Assignment Checkboxes -->
														{#each receipt.people as person}
															<td class="p-2 text-center w-10">
																<input
																	type="checkbox"
																	checked={entry.assigned_to.includes(person)}
																	disabled={updatingEntries.has(entry.id)}
																	onchange={(e) => updateAssignment(receipt.id, entry.id, person, e.currentTarget.checked)}
																	class="w-3 h-3 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
																	class:opacity-50={updatingEntries.has(entry.id)}
																	title={updatingEntries.has(entry.id) ? 'Updating...' : person}
																/>
															</td>
														{/each}
														
														<!-- Delete Button -->
														<td class="p-2 text-center w-10">
															<button
																onclick={() => removeEntry(entry.id)}
																class="text-red-500 hover:text-red-700 text-xs"
																title="Delete item"
															>
																🗑️
															</button>
														</td>
													</tr>
												{/each}
												
												<!-- Add New Entry Row -->
												<tr class="border-t border-gray-200 bg-gray-50">
													<td colspan="100" class="p-2 text-center">
														<button
															onclick={() => addNewEntry(receipt.id)}
															class="text-xs text-blue-600 hover:text-blue-800 font-medium"
														>
															+ Add Item
														</button>
													</td>
												</tr>
											</tbody>
										</table>
									</div>
								</div>
					</div>
				{/if}
			</div>

			<!-- Cost Breakdown (Right Sidebar) -->
			<div class="bg-white rounded-lg shadow-md h-[900px] overflow-hidden">
				{#if currentReceipt}
					{@const receipt = currentReceipt}
					<div class="p-4 border-b bg-gray-50">
						<h3 class="text-lg font-semibold text-gray-700">Cost Breakdown</h3>
					</div>
					<div class="p-4 overflow-y-auto h-[calc(900px-60px)]">
						<div class="bg-gradient-to-br from-green-50 to-emerald-50 p-4 rounded-lg border border-green-200">
							<h5 class="font-medium mb-3 text-gray-700">Per Person</h5>
							<div class="space-y-2">
								{#each Object.entries(calculateReceiptCosts(receipt, receipt.people)) as [person, cost]}
									<div class="flex justify-between items-center">
										<div class="flex items-center space-x-2">
											<span class="font-medium text-xs bg-green-200 text-green-900 w-6 h-6 rounded-full flex items-center justify-center">
												{getInitials(person)}
											</span>
											<span class="text-gray-700 font-medium">{person}</span>
										</div>
										<span class="font-mono font-semibold text-gray-800">${cost.toFixed(2)}</span>
									</div>
								{/each}
								<div class="border-t border-green-200 pt-2 mt-2 flex justify-between items-center font-semibold">
									<span class="text-gray-800">Total:</span>
									<span class="font-mono text-green-700">
										${Object.values(calculateReceiptCosts(receipt, receipt.people)).reduce((a, b) => a + b, 0).toFixed(2)}
									</span>
								</div>
							</div>
						</div>

						<!-- Payment Status -->
						{#if receipt.paid_by}
							<div class="mt-4 bg-blue-50 p-4 rounded-lg border border-blue-200">
								<p class="font-medium text-blue-900 mb-3">Payments Needed</p>
								<div class="space-y-2">
									{#each Object.entries(calculateReceiptCosts(receipt, receipt.people)) as [person, owes]}
										{#if person !== receipt.paid_by && owes > 0}
											<div class="flex justify-between items-center bg-white p-2 rounded">
												<span class="text-gray-700 text-sm">{person} → {receipt.paid_by}</span>
												<span class="font-mono font-semibold text-blue-900">${owes.toFixed(2)}</span>
											</div>
										{/if}
									{/each}
								</div>
							</div>
						{:else}
							<div class="mt-4 bg-yellow-50 p-4 rounded-lg border border-yellow-200">
								<p class="text-sm text-yellow-800">No payer assigned</p>
							</div>
						{/if}
					</div>
				{:else}
					<div class="h-full flex items-center justify-center p-8 text-center text-gray-500">
						<p class="text-sm">Select a receipt to view cost breakdown</p>
					</div>
				{/if}
			</div>
		</div>
	{/if}

	<NewReceiptModal 
		bind:show={showNewReceiptForm} 
		{group} 
		onSubmit={handleCreateReceipt}
	/>
</main>
