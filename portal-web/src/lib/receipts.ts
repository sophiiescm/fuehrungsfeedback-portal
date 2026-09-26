// Quittungen: die eigenen abgegebenen Antworten, NUR im Browser dieses Geräts (localStorage).
// Es gibt bewusst keine Speicherung auf dem Server – die Verknüpfung Person <-> Antworten existiert nirgends
// außerhalb dieses Geräts (Anonymitätsregel). Auf Kiosk-/Gemeinschafts-Geräten wird nichts gespeichert.
import { browser } from '$app/environment';

export interface ReceiptItem { g: string; q: string; a: string[] }
export interface Receipt { sid: string; at: string; items: ReceiptItem[] }

const key = (pnr: string, sid: number | string) => `ffp_receipt:${pnr}:${sid}`;

export function saveReceipt(pnr: string, r: Receipt): void {
	if (!browser) return;
	try {
		localStorage.setItem(key(pnr, r.sid), JSON.stringify(r));
	} catch {
		/* Speicher voll/gesperrt: dann eben keine Quittung */
	}
}

export function getReceipt(pnr: string, sid: number | string | null | undefined): Receipt | null {
	if (!browser || sid == null) return null;
	try {
		const raw = localStorage.getItem(key(pnr, sid));
		return raw ? (JSON.parse(raw) as Receipt) : null;
	} catch {
		return null;
	}
}

export function deleteReceipt(pnr: string, sid: number | string): void {
	if (browser) localStorage.removeItem(key(pnr, sid));
}

/** Fragment aus dem LimeSurvey-Theme: r=<base64url(JSON)>&sid=<id> */
export function decodeFragment(hash: string): { receipt: Receipt | null; sid: string | null } {
	const p = new URLSearchParams(hash.replace(/^#/, ''));
	const sid = p.get('sid');
	const r = p.get('r');
	if (!r) return { receipt: null, sid };
	try {
		const b64 = r.replace(/-/g, '+').replace(/_/g, '/');
		const bin = atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4));
		const json = new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
		const data = JSON.parse(json) as Receipt;
		if (!Array.isArray(data.items)) return { receipt: null, sid };
		return { receipt: { sid: String(data.sid || sid), at: String(data.at ?? ''), items: data.items.slice(0, 300) }, sid };
	} catch {
		return { receipt: null, sid };
	}
}
