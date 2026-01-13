<script lang="ts">
	import type { Group } from '$lib/types';
	import { scanMultipleReceipts, handleError } from '$lib/api';

	let {
		show = $bindable(),
		group,
		onSubmit,
		onScanSuccess
	}: {
		show: boolean;
		group: Group | null;
		onSubmit: (data: { name: string; paidBy: string; entries: string; people: string[] }) => Promise<void>;
		onScanSuccess?: () => Promise<void>;
	} = $props();

	// Tab state
	let selectedTab = $state<'scan' | 'manual'>('scan');

	// Manual entry form state
	let newReceiptName = $state('');
	let newReceiptEntries = $state('');
	let newReceiptPaidBy = $state('');

	// Scan receipt form state
	let uploadedFiles = $state<FileList | null>(null);
	let isScanning = $state(false);
	let scanError = $state('');
	let scanProgress = $state<{ current: number; total: number } | null>(null);

	// Clone people from the most recent receipt, or use all group people if no receipts exist
	const defaultPeople = $derived(() => {
		if (!group) return [];
		if (group.receipts.length === 0) return [...group.people];

		// Get the most recent receipt (assuming they're ordered by creation)
		const mostRecentReceipt = group.receipts[group.receipts.length - 1];
		return mostRecentReceipt.people ? [...mostRecentReceipt.people] : [...group.people];
	});

	async function handleManualSubmit() {
		if (!newReceiptName.trim()) return;

		await onSubmit({
			name: newReceiptName,
			paidBy: newReceiptPaidBy,
			entries: newReceiptEntries,
			people: defaultPeople()
		});

		resetForm();
		show = false;
	}

	async function handleScanSubmit() {
		if (!uploadedFiles || uploadedFiles.length === 0 || !group) return;

		isScanning = true;
		scanError = '';

		try {
			const files = Array.from(uploadedFiles);

			// Scan all files sequentially with default people (same as manual entry)
			await scanMultipleReceipts(
				group.id,
				files,
				(current, total) => {
					scanProgress = { current, total };
				},
				defaultPeople()  // Use same people logic as manual entry
			);

			// Success! Close modal and notify parent
			resetForm();
			show = false;

			// Trigger parent refresh if callback provided
			if (onScanSuccess) {
				await onScanSuccess();
			}

		} catch (err) {
			// Show error, stay in modal, allow retry or switch to manual
			scanError = handleError(err, 'Failed to scan receipt');
		} finally {
			isScanning = false;
			scanProgress = null;
		}
	}

	function resetForm() {
		newReceiptName = '';
		newReceiptEntries = '';
		newReceiptPaidBy = '';
		uploadedFiles = null;
		scanError = '';
		scanProgress = null;
		isScanning = false;
	}

	function handleClose() {
		show = false;
		resetForm();
	}

	function switchToManualEntry() {
		selectedTab = 'manual';
		scanError = '';
	}
</script>

{#if show}
	<div class="fixed inset-0 flex items-center bg-black/50 justify-center p-4 z-50">
		<div class="bg-white rounded-lg p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
			<h3 class="text-lg font-semibold text-gray-800 mb-4">Create New Receipt</h3>

			<!-- Tabs -->
			<div class="flex border-b border-gray-200 mb-4">
				<button
					onclick={() => { selectedTab = 'scan'; scanError = ''; }}
					class="px-4 py-2 font-medium text-sm border-b-2 transition-colors {selectedTab === 'scan'
						? 'border-blue-500 text-blue-600'
						: 'border-transparent text-gray-500 hover:text-gray-700'}"
				>
					Scan Receipt
				</button>
				<button
					onclick={() => { selectedTab = 'manual'; }}
					class="px-4 py-2 font-medium text-sm border-b-2 transition-colors {selectedTab === 'manual'
						? 'border-blue-500 text-blue-600'
						: 'border-transparent text-gray-500 hover:text-gray-700'}"
				>
					Manual Entry
				</button>
			</div>

			<!-- Scan Receipt Tab -->
			{#if selectedTab === 'scan'}
				<div class="space-y-4">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-2">
							Upload Receipt Image(s)
						</label>

						<!-- File Input -->
						<input
							type="file"
							accept="image/jpeg,image/png,image/webp,application/pdf"
							multiple
							bind:files={uploadedFiles}
							class="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
						/>

						<p class="text-xs text-gray-500 mt-2">
							Accepts JPEG, PNG, WebP images, or PDF files (max 10MB each)
						</p>
					</div>

					<!-- File List Preview -->
					{#if uploadedFiles && uploadedFiles.length > 0}
						<div class="bg-gray-50 border border-gray-200 rounded p-3">
							<p class="text-xs font-medium text-gray-700 mb-2">
								Selected files ({uploadedFiles.length}):
							</p>
							<ul class="text-xs text-gray-600 space-y-1">
								{#each Array.from(uploadedFiles) as file}
									<li class="truncate">📄 {file.name}</li>
								{/each}
							</ul>
						</div>
					{/if}

					<!-- Progress Indicator -->
					{#if isScanning && scanProgress}
						<div class="bg-blue-50 border border-blue-200 rounded p-3">
							<p class="text-sm text-blue-800 font-medium">
								Processing receipt {scanProgress.current + 1} of {scanProgress.total}...
							</p>
							<div class="w-full bg-blue-200 rounded-full h-2 mt-2">
								<div
									class="bg-blue-600 h-2 rounded-full transition-all"
									style="width: {((scanProgress.current / scanProgress.total) * 100).toFixed(0)}%"
								></div>
							</div>
						</div>
					{/if}

					<!-- Error Display -->
					{#if scanError}
						<div class="bg-red-50 border border-red-200 rounded p-3">
							<p class="text-sm text-red-800 font-medium mb-2">Error</p>
							<p class="text-xs text-red-700">{scanError}</p>
							<button
								onclick={switchToManualEntry}
								class="mt-2 text-xs text-red-600 hover:text-red-800 underline"
							>
								Switch to Manual Entry
							</button>
						</div>
					{/if}

					<!-- Action Buttons -->
					<div class="flex space-x-3 mt-6">
						<button
							onclick={handleScanSubmit}
							disabled={!uploadedFiles || uploadedFiles.length === 0 || isScanning}
							class="flex-1 bg-blue-500 text-white py-2 rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
						>
							{isScanning ? 'Scanning...' : `Scan & Create ${uploadedFiles && uploadedFiles.length > 1 ? `(${uploadedFiles.length})` : ''}`}
						</button>
						<button
							onclick={handleClose}
							disabled={isScanning}
							class="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 transition-colors"
						>
							Cancel
						</button>
					</div>
				</div>
			{/if}

			<!-- Manual Entry Tab -->
			{#if selectedTab === 'manual'}
				<div class="space-y-4">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Receipt Name *</label>
						<input
							type="text"
							bind:value={newReceiptName}
							placeholder="e.g., Grocery Store, Restaurant"
							class="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						/>
					</div>

					{#if group}
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Paid By</label>
							<select bind:value={newReceiptPaidBy} class="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
								<option value="">Select who paid</option>
								{#each defaultPeople() as person}
									<option value={person}>{person}</option>
								{/each}
							</select>
						</div>

						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Receipt Members</label>
							<div class="text-sm text-gray-600 bg-blue-50 p-2 rounded border">
								{defaultPeople().join(', ')}
								<div class="text-xs text-gray-500 mt-1">
									{group.receipts.length > 0 ? 'Copied from most recent receipt' : 'Using all group members'}
								</div>
							</div>
						</div>
					{/if}

					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">
							Entries (Optional JSON)
						</label>
						<textarea
							bind:value={newReceiptEntries}
							placeholder={`[{"name": "Apples", "price": 3.99, "taxable": true}]`}
							rows="4"
							class="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
						></textarea>
						<p class="text-xs text-gray-500 mt-1">
							Format: {`[{"name": "Item", "price": 0.00, "taxable": true}]`}
						</p>
					</div>

					<!-- Action Buttons -->
					<div class="flex space-x-3 mt-6">
						<button
							onclick={handleManualSubmit}
							disabled={!newReceiptName.trim()}
							class="flex-1 bg-blue-500 text-white py-2 rounded hover:bg-blue-600 disabled:opacity-50 transition-colors"
						>
							Create Receipt
						</button>
						<button
							onclick={handleClose}
							class="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50 transition-colors"
						>
							Cancel
						</button>
					</div>
				</div>
			{/if}
		</div>
	</div>
{/if}
