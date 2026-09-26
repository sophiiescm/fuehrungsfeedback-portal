import { defineConfig } from '@playwright/test';

// Laeuft gegen den per `docker compose up` gestarteten Stack (Seed-Daten noetig,
// siehe docs/INSTALLATION.md). Anderer Zielhost: BASE_URL / API_URL setzen.
export default defineConfig({
	testDir: 'e2e',
	testMatch: '**/*.e2e.{ts,js}',
	use: { baseURL: process.env.BASE_URL ?? 'http://localhost:5173' }
});
