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

test('Report-Layout: Abschnitte umsortieren, Vorschau aktualisiert sich, Exporte verfügbar', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 1000 });
	await loginAs(page, 'P00001', '/report-layout');
	await expect(page.getByRole('heading', { name: 'Report-Layout' })).toBeVisible();
	const frame = page.frameLocator('iframe[title="Vorschau des Reports"]');
	await expect(frame.getByText('Beispiel-Runde')).toBeVisible();
	await page.getByLabel('Überschrift').first().fill('Mein Gesamtbild');
	await expect(frame.getByText('Mein Gesamtbild')).toBeVisible();
	await page.getByRole('button', { name: 'Nach unten' }).first().click();
	await expect(page.getByText('Ungespeicherte Änderungen')).toBeVisible();
	for (const l of ['PDF', 'PowerPoint', 'Excel', 'CSV']) await expect(page.getByRole('button', { name: `⬇ ${l}` })).toBeVisible();
	await page.screenshot({ path: 'e2e/screens/report-layout.png' });
});

test('Führungskraft: Export-Menü bietet PDF, PowerPoint, Excel und CSV', async ({ page }) => {
	await loginAs(page, 'P00002', '/reports');
	await page.getByRole('button', { name: /Exportieren/ }).click();
	for (const l of ['PDF', 'PowerPoint', 'Excel', 'CSV']) await expect(page.getByRole('menuitem', { name: new RegExp(l) })).toBeVisible();
	const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('menuitem', { name: /PowerPoint/ }).click()]);
	expect(download.suggestedFilename()).toBe('feedback-report.pptx');
});

test('Meine Feedbacks: Verlauf mit Teilnahme-Status und lokal gespeicherter, nur lesbarer Antwortkopie', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await loginAs(page, 'P01900', '/dashboard');
	const item = (id: number, over: object) => ({ participation_id: id, round_name: 'H1/2026', leader_name: 'Uma Koch', status: 'erledigt', due_date: '2026-04-15', feedback_link: null, completed_date: '2026-04-02', survey_id: 111, round_closed: true, ...over });
	await page.route('**/feedbacks/mine', (r) => r.fulfill({ json: [
		item(1, {}),
		item(2, { round_name: 'H2/2025', status: 'offen', completed_date: null, survey_id: 222, due_date: '2025-10-15' }),
		item(3, { round_name: 'Aktuell', status: 'offen', completed_date: null, round_closed: false, survey_id: 333, feedback_link: 'http://localhost:8080/x', due_date: '2099-01-01' })
	] }));
	await page.evaluate(() => localStorage.setItem('ffp_receipt:P01900:111', JSON.stringify({ sid: '111', at: '2026-04-02', items: [{ g: 'Kommunikation', q: 'Klar kommuniziert?', a: ['Trifft eher zu (4)'] }] })));
	await page.goto('/feedbacks');
	await expect(page.getByText('Abgegeben am 2026-04-02')).toBeVisible();
	await expect(page.getByText('Nicht teilgenommen')).toBeVisible();
	await expect(page.getByRole('link', { name: 'Jetzt starten' })).toBeVisible();
	await page.getByRole('button', { name: 'Meine Antworten ansehen' }).click();
	await expect(page.getByRole('dialog').getByText('Trifft eher zu (4)')).toBeVisible();
	await expect(page.getByRole('dialog').locator('input, textarea')).toHaveCount(0); // nur lesbar
	await page.screenshot({ path: 'e2e/screens/feedbacks-verlauf.png' });
	page.once('dialog', (d) => d.accept());
	await page.getByRole('button', { name: 'Kopie von diesem Gerät löschen' }).click();
	await expect(page.getByRole('button', { name: 'Meine Antworten ansehen' })).toHaveCount(0);
});

test('Mehrsprachigkeit: Sprache im Editor hinzufügen, übersetzen; Nutzer wählt eigene Umfragesprache', async ({ page }) => {
	await page.setViewportSize({ width: 1280, height: 1000 });
	await loginAs(page, 'P00001', '/dashboard');
	// eigenen, frischen Entwurf anlegen (unabhängig von vorhandenen Umfragen)
	const vid = await page.evaluate(async (api) => {
		const h = { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('ffp_token')}` };
		const t = await (await fetch(`${api}/surveys/templates`, { method: 'POST', headers: h, body: JSON.stringify({ name: 'E2E Sprachtest' }) })).json();
		const v = t.versions[0].id;
		await fetch(`${api}/surveys/versions/${v}/questions`, { method: 'POST', headers: h, body: JSON.stringify({ type: 'freitext', text: 'Was läuft gut?', mandatory: false }) });
		return v;
	}, API);
	await page.goto(`/survey-builder/${vid}`);
	await page.getByLabel('Sprache hinzufügen').selectOption('pl');
	await expect(page.getByText('Übersetzung: Polski')).toBeVisible();
	await expect(page.getByText(/von \d+ übersetzt/)).toBeVisible();
	const first = page.getByPlaceholder('Polski: Fragetext').first();
	await first.fill('Mój przełożony jasno komunikuje oczekiwania.');
	await first.blur();
	await page.getByRole('tab', { name: /Deutsch/ }).click();
	await page.getByRole('tab', { name: 'Polski' }).click();
	await expect(page.getByPlaceholder('Polski: Fragetext').first()).toHaveValue('Mój przełożony jasno komunikuje oczekiwania.');
	await page.screenshot({ path: 'e2e/screens/editor-uebersetzung.png' });

	// Nutzer: eigene Sprache
	await loginAs(page, 'P01900', '/dashboard');
	await page.getByRole('button', { name: /Uma Koch/ }).click();
	const sel = page.getByLabel('Sprache der Umfragen');
	await expect(sel).toBeVisible();
	await sel.selectOption('en');
	await expect(page.getByText('✓ gespeichert')).toBeVisible();
	await sel.selectOption('de');
});

test('Report-Layout: eigene Textbausteine, anpassbare Festtexte und Platzhalter mit Live-Vorschau', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 1100 });
	await loginAs(page, 'P00001', '/report-layout');
	const frame = page.frameLocator('iframe[title="Vorschau des Reports"]');
	await expect(frame.getByText('Beispiel-Runde')).toBeVisible();

	await page.getByRole('button', { name: '＋ Textbaustein hinzufügen' }).click();
	const block = page.getByLabel('Text des Bausteins').last();
	await block.fill('Hallo ');
	await page.getByRole('button', { name: '{leader}' }).click();
	await block.pressSequentially(', dein bestes Thema ist ');
	await page.getByRole('button', { name: '{best_topic}' }).click();
	await expect(frame.getByText('Hallo Alex Beispiel, dein bestes Thema ist Wertschätzung')).toBeVisible();

	const good = page.getByLabel('Stärken: Überschrift');
	await good.fill('Unsere Stärken');
	await expect(frame.getByText('Unsere Stärken')).toBeVisible();
	await page.getByRole('button', { name: 'Standard' }).first().click();
	await expect(frame.getByText('Das läuft gut')).toBeVisible();

	await page.getByLabel('Text „Wie lese ich den Report?“').fill('- **Wichtig:** Werte sind anonym\n- Ab 3 Antworten');
	await expect(frame.getByText('Wichtig:')).toBeVisible();
	await expect(page.getByText('Ungespeicherte Änderungen')).toBeVisible();
	await page.screenshot({ path: 'e2e/screens/report-texte.png' });
});
