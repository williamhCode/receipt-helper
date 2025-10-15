export interface Group {
	id: number;
	created_at: string;
	slug: string;
	name: string;
	people: string[];
	receipts: Receipt[];
}

export interface Person {
	id: number;
	name: string;
	created_at: string;
	group_id: number;
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

export interface ReceiptEntry {
	id: number;
	name: string;
	price: number;
	taxable: boolean;
	assigned_to: string[];
	receipt_id: number;
}
