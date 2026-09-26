import { test, expect, type Page } from '@playwright/test';

const API = process.env.API_URL ?? 'http://localhost:8001';
// Fiktive Seed-Personen (seed/generate_org_csv.py, Seed 42) + Admin-Rolle fuer P00001
const USERS = {
	admin: { pnr: process.env.ADMIN_PNR ?? 'P00001', label: 'Admin' },
	fuehrungskraft: { pnr: process.env.FK_PNR ?? 'P00002', label: 'Führungskraft' },
	mitarbeiter: { pnr: process.env.MA_PNR ?? 'P00783', label: 'Mitarbeiter' }
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

test('Smartphone-Ansicht: Hamburger-Menü statt Sidebar', async ({ page }) => {
	await page.setViewportSize({ width: 375, height: 812 });
	await loginAs(page, USERS.mitarbeiter.pnr);
	await page.getByLabel('Menü öffnen').click();
	await expect(page.getByRole('link', { name: 'Meine Feedbacks' })).toBeVisible();
});
