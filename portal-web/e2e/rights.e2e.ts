import { test, expect, type Page } from '@playwright/test';

const API = process.env.API_URL ?? 'http://localhost:8001';

async function loginAs(page: Page, pnr: string, target = '/dashboard') {
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
	await page.goto(target);
}

test('Login-Seite bietet Entwickler-Schnellzugriff für alle Ansichten', async ({ page }) => {
	await page.goto('/login');
	for (const t of ['Admin (HR)', 'Führungskraft', 'Mitarbeiter', 'Produktion ohne E-Mail'])
		await expect(page.getByText(t, { exact: true }).first()).toBeVisible();
	await page.getByRole('button', { name: /^Mitarbeiter/ }).first().click();
	await expect(page).toHaveURL(/dashboard/);
});

test('Einstellungen: Rollen und Rechte sind verwaltbar', async ({ page }) => {
	await loginAs(page, 'P00001', '/einstellungen');
	await expect(page.getByRole('heading', { name: /Nutzer & Rechte/ })).toBeVisible();
	for (const r of ['Vollzugriff', 'Umfrage & Auswertung', 'Nur Auswertung']) await expect(page.getByText(r).first()).toBeVisible();
	await page.getByRole('button', { name: '+ Neue Rolle' }).click();
	await expect(page.locator('label', { hasText: 'Auswertungen ansehen' })).toBeVisible();
	await expect(page.locator('label', { hasText: 'Umfragen anlegen und bearbeiten' })).toBeVisible();
});

test('Umfrage-Editor: Likert-Stufen einzeln beschriftbar, Auswahl mit mehreren Feldern', async ({ page }) => {
	await page.setViewportSize({ width: 1280, height: 1000 });
	await loginAs(page, 'P00001', '/survey-builder');
	// erste Vorlage öffnen, als neue Version bearbeiten (gesperrt) bzw. direkt bearbeiten
	await page.locator('a[href^="/survey-builder/"]').last().click();
	const clone = page.getByRole('button', { name: 'Als neue Version bearbeiten' });
	await expect(clone.or(page.getByRole('button', { name: '+ Frage hinzufügen' }).first())).toBeVisible();
	if (await clone.count()) {
		await clone.click();
		await expect(clone).toHaveCount(0);
	}
	await page.getByRole('button', { name: '+ Frage hinzufügen' }).first().click();
	await page.getByRole('button', { name: 'Likert-Skala' }).click();
	await expect(page.getByPlaceholder('Stufe 5')).toBeVisible(); // 5 Stufen, jede mit eigenem Feld
	await page.getByRole('button', { name: '7 Stufen' }).click();
	await expect(page.getByPlaceholder('Stufe 7')).toBeVisible();
	await page.getByRole('button', { name: 'Auswahlfrage' }).click();
	await expect(page.getByPlaceholder('Option 3')).toBeVisible();
	await page.getByRole('button', { name: '+ Option hinzufügen' }).click();
	await expect(page.getByPlaceholder('Option 4')).toBeVisible();
});
