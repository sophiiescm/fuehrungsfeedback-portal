import { test, expect, type Page } from '@playwright/test';

const API = process.env.API_URL ?? 'http://localhost:8001';
// Fiktive Seed-Personen (seed/generate_org_csv.py, Seed 42) + Admin-Rolle fuer P00001
const USERS = {
	admin: { pnr: process.env.ADMIN_PNR ?? 'P00001', label: 'Admin' },
	fuehrungskraft: { pnr: process.env.FK_PNR ?? 'P00002', label: 'Führungskraft' },
	mitarbeiter: { pnr: process.env.MA_PNR ?? 'P01900', label: 'Mitarbeiter' }
};

async function loginAs(page: Page, pnr: string) {
	await page.goto('/login');
	const token = await page.evaluate(async ([api, p]) => {
		const r = await fetch(`${api}/auth/dev-login`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ personalnummer: p })
		});
		return (await r.json()).access_token as string;
	}, [API, pnr]);
	await page.evaluate((t) => localStorage.setItem('ffp_token', t), token);
	await page.goto('/dashboard');
}

const nav = (page: Page, name: string) => page.locator('aside').getByRole('link', { name, exact: true });

test('Login-Seite zeigt SSO, Code-Login und Dev-Login', async ({ page }) => {
	await page.goto('/login');
	await expect(page.getByText('Mit Single Sign-On anmelden')).toBeVisible();
	await expect(page.getByPlaceholder('Personalnummer')).toBeVisible();
});

test('Admin sieht alle Verwaltungsbereiche', async ({ page }) => {
	await loginAs(page, USERS.admin.pnr);
	for (const n of ['Umfrage gestalten', 'Befragungsrunden', 'Auswertung & Benchmarking', 'Einstellungen'])
		await expect(nav(page, n)).toBeVisible();
	await page.goto('/organisation');
	await expect(page.getByRole('heading', { name: /Organisation/ })).toBeVisible();
});

test('Führungskraft sieht Reports, aber keine Admin-Bereiche', async ({ page }) => {
	await loginAs(page, USERS.fuehrungskraft.pnr);
	await expect(nav(page, 'Meine Reports / Trend')).toBeVisible();
	await expect(nav(page, 'Umfrage gestalten')).toHaveCount(0);
	await page.goto('/reports');
	await expect(page.getByRole('heading', { name: 'Meine Reports / Trend' })).toBeVisible();
});

test('Mitarbeiter sieht nur Dashboard, Feedbacks, Benachrichtigungen', async ({ page }) => {
	await loginAs(page, USERS.mitarbeiter.pnr);
	await expect(nav(page, 'Meine Feedbacks')).toBeVisible();
	await expect(nav(page, 'Meine Reports / Trend')).toHaveCount(0);
	await expect(nav(page, 'Befragungsrunden')).toHaveCount(0);
	await page.goto('/feedbacks');
	await expect(page.getByTestId('open-summary')).toContainText(/offene|Alles erledigt/);
});

test('Smartphone: Tab-Leiste unten, Mehr-Menü, kein horizontales Scrollen', async ({ page }) => {
	await page.setViewportSize({ width: 375, height: 812 });
	await loginAs(page, USERS.mitarbeiter.pnr);
	await expect(page.getByRole('navigation', { name: 'Hauptnavigation' }).first()).toBeVisible();
	await expect(page.locator('aside')).toBeHidden();
	await page.getByRole('button', { name: 'Mehr' }).click();
	await expect(page.getByRole('link', { name: 'Benachrichtigungen' })).toBeVisible();
	const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
	expect(overflow).toBeLessThanOrEqual(1);
	await page.screenshot({ path: 'e2e/screens/phone-mitarbeiter.png' });
});

test('iPad hochkant: Tab-Leiste, Inhalte nutzen die Breite', async ({ page }) => {
	await page.setViewportSize({ width: 820, height: 1180 });
	await loginAs(page, USERS.fuehrungskraft.pnr);
	await expect(page.locator('aside')).toBeHidden();
	await expect(page.locator('nav.tabbar')).toBeVisible();
	await page.goto('/feedbacks');
	await expect(page.getByText('Dein Feedback ist anonym')).toBeVisible();
	await page.screenshot({ path: 'e2e/screens/ipad-feedbacks.png' });
});

test('Admin: Runden-Assistent führt in 4 Schritten durch die Planung', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await loginAs(page, USERS.admin.pnr);
	await page.goto('/rounds');
	await page.getByRole('button', { name: '+ Neue Runde' }).click();
	await expect(page.getByText('Welchen Fragebogen')).toBeVisible();
	await page.getByRole('button', { name: 'Weiter' }).click();
	await expect(page.getByText('Wann soll die Runde laufen?')).toBeVisible();
	await page.getByRole('button', { name: 'Weiter' }).click();
	await expect(page.getByText('Wer wird bewertet und wer eingeladen?')).toBeVisible();
	await expect(page.getByText('Führungskräfte', { exact: true })).toBeVisible();
	await page.screenshot({ path: 'e2e/screens/phone-runden-assistent.png' });
});

test('Führungskraft: Maßnahmen-Seite erreichbar', async ({ page }) => {
	await loginAs(page, USERS.fuehrungskraft.pnr);
	await page.goto('/massnahmen');
	await expect(page.getByRole('heading', { name: 'Maßnahmen', exact: true })).toBeVisible();
	await expect(page.getByText('Meine Maßnahmen')).toBeVisible();
});
