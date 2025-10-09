// ============================================================================
// Types
// ============================================================================

export interface Person {
	id: number;
	name: string;
	created_at: string;
	group_id: number;  // NEW: Person now belongs to a single group
}

export interface ReceiptEntry {
	id: number;
	name: string;
	price: number;
	taxable: boolean;
	assigned_to: string[];
	receipt_id: number;
}

export interface Receipt {
	id: number;
	created_at: string;
	processed: boolean;
	name: string;
	raw_data: string | null;
	paid_by: string | null;
	group_id: number;
	people: string[];
	entries: ReceiptEntry[];
}

export interface Group {
	id: number;
	created_at: string;
	slug: string;
	name: string;
	people: string[];
	receipts: Receipt[];
}

// ============================================================================
// Constants
// ============================================================================

export const API_BASE = import.meta.env.VITE_BACKEND_HOST || 'http://localhost:8000';
export const TAX_RATE = 0.07;

// ============================================================================
// Utility functions
// ============================================================================

export function handleError(err: unknown, context: string): string {
	console.error(`Error in ${context}:`, err);
	
	if (err instanceof TypeError && err.message.includes('fetch')) {
		return `Network Error: Failed to connect to ${API_BASE}.`;
	}
	
	if (err instanceof Error) {
		if (err.message.includes('HTTP')) {
			return err.message;
		}
		return `${context}: ${err.message}`;
	}
	
	return `${context}: Unknown error occurred`;
}

export function getInitials(name: string): string {
	const parts = name.trim().split(/\s+/);
	if (parts.length === 1) {
		return parts[0].charAt(0).toUpperCase();
	}
	return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

// ============================================================================
// Calculation functions
// ============================================================================

export function calculateReceiptTotal(receipt: Receipt): number {
	return receipt.entries.reduce((total, entry) => {
		const price = entry.taxable ? entry.price * (1 + TAX_RATE) : entry.price;
		return total + price;
	}, 0);
}

export function calculateReceiptCosts(receipt: Receipt, people: string[]): Record<string, number> {
	const costs: Record<string, number> = {};
	people.forEach(person => costs[person] = 0);

	receipt.entries.forEach(entry => {
		const assignedCount = entry.assigned_to.length;
		const price = entry.taxable ? entry.price * (1 + TAX_RATE) : entry.price;
		
		if (assignedCount === 0) {
			const pricePerPerson = price / people.length;
			people.forEach(person => costs[person] += pricePerPerson);
		} else {
			const pricePerPerson = price / assignedCount;
			entry.assigned_to.forEach(person => {
				if (costs[person] !== undefined) {
					costs[person] += pricePerPerson;
				}
			});
		}
	});

	return costs;
}

export function calculateCombinedCosts(group: Group): Record<string, number> {
	const costs: Record<string, number> = {};
	group.people.forEach(person => costs[person] = 0);

	group.receipts.forEach(receipt => {
		if (receipt.processed) return;

		const receiptCosts = calculateReceiptCosts(receipt, receipt.people);
		receipt.people.forEach(person => {
			costs[person] += receiptCosts[person];
		});

		if (receipt.paid_by && costs[receipt.paid_by] !== undefined) {
			costs[receipt.paid_by] -= calculateReceiptTotal(receipt);
		}
	});

	return costs;
}

export function getUnprocessedReceiptsTotal(group: Group): number {
	return group.receipts
		.filter(receipt => !receipt.processed)
		.reduce((total, receipt) => total + calculateReceiptTotal(receipt), 0);
}

// ============================================================================
// HTTP helper functions
// ============================================================================

async function request<T>(url: string, options?: RequestInit): Promise<T> {
	const response = await fetch(`${API_BASE}${url}`, options);
	
	if (!response.ok) {
		const errorText = await response.text().catch(() => 'Unknown server error');
		throw new Error(`HTTP ${response.status} (${response.statusText}): ${errorText}`);
	}
	
	return await response.json() as T;
}

async function get<T>(url: string): Promise<T> {
	return request<T>(url);
}

async function post<T>(url: string, data: any): Promise<T> {
	return request<T>(url, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
}

async function patch<T>(url: string, data: any): Promise<T> {
	return request<T>(url, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
}

async function del<T>(url: string): Promise<T> {
	return request<T>(url, { method: 'DELETE' });
}

// ============================================================================
// Group API functions
// ============================================================================

export function fetchGroups() {
	return get<Group[]>('/groups/');
}

export function fetchGroup(groupId: number) {
	return get<Group>(`/groups/${groupId}`);
}

export function createGroup(groupData: { name?: string; people: string[] }) {
	return post<Group>('/groups/', groupData);
}

export function updateGroup(groupId: number, groupData: { name?: string; people?: string[] }) {
	return patch<Group>(`/groups/${groupId}`, groupData);
}

export function updateGroupName(groupId: number, newName: string) {
	return patch<Group>(`/groups/${groupId}/name`, { name: newName });
}

export function deleteGroup(groupId: number) {
	return del(`/groups/${groupId}`);
}

// ============================================================================
// Person API functions (group-scoped)
// ============================================================================

export function fetchGroupPeople(groupId: number) {
	return get<Person[]>(`/groups/${groupId}/people/`);
}

export function updatePerson(personId: number, name: string) {
	return patch<Person>(`/people/${personId}`, { name });
}

// ============================================================================
// Receipt API functions
// ============================================================================

export function createReceipt(groupId: number, receiptData: {
	processed: boolean;
	name: string;
	raw_data: string | null;
	paid_by: string | null;
	people: string[];
	entries: any[];
}) {
	return post<Receipt>(`/groups/${groupId}/receipts/`, receiptData);
}

export function updateReceipt(receiptId: number, receiptData: { 
	name?: string;
	people?: string[]; 
	processed?: boolean;
	paid_by?: string | null;
}) {
	return patch<Receipt>(`/receipts/${receiptId}`, receiptData);
}

export function updateReceiptPaidBy(receiptId: number, paidBy: string | null) {
	return updateReceipt(receiptId, { paid_by: paidBy ?? '' });
}

export function deleteReceipt(receiptId: number) {
	return del(`/receipts/${receiptId}`);
}

// ============================================================================
// Receipt Entry API functions
// ============================================================================

export function createReceiptEntry(
	receiptId: number,
	entryData: { name: string; price: number; taxable: boolean }
) {
	return post(`/receipts/${receiptId}/entries/`, entryData);
}

export function updateReceiptEntry(entryId: number, assignedTo: string[]) {
	return updateReceiptEntryDetails(entryId, { assigned_to: assignedTo });
}

export function updateReceiptEntryDetails(
	entryId: number, 
	data: { name?: string; price?: number; taxable?: boolean; assigned_to?: string[] }
) {
	return patch(`/receipt-entries/${entryId}`, data);
}

export function deleteReceiptEntry(entryId: number) {
	return del(`/receipt-entries/${entryId}`);
}
