import type { Group, Person, Receipt } from './types';

export const API_BASE = import.meta.env.VITE_BACKEND_HOST || 'http://localhost:8000';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
	const response = await fetch(`${API_BASE}${url}`, options);
	
	if (!response.ok) {
		const errorText = await response.text().catch(() => 'Unknown server error');
		throw new Error(`HTTP ${response.status} (${response.statusText}): ${errorText}`);
	}
	
	return await response.json() as T;
}

// basic HTTP methods
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

export function fetchGroupVersion(groupId: number) {
	return get<{ group_id: number; updated_at: string }>(`/groups/${groupId}/version`);
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

export function getReceipt(receiptId: number) {
  return get<Receipt>(`/receipts/${receiptId}`);
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

// ==========================================================================
// Helpers
// ==========================================================================

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

