import { browser } from '$app/environment';

export type Role = 'admin' | 'fuehrungskraft' | 'mitarbeiter';

export interface CurrentUser {
	personalnummer: string;
	full_name: string;
	email: string | null;
	roles: Role[];
}

const STORAGE_KEY = 'ffp_token';

class AuthState {
	token = $state<string | null>(browser ? localStorage.getItem(STORAGE_KEY) : null);
	user = $state<CurrentUser | null>(null);

	get isAuthenticated() {
		return this.token !== null;
	}

	hasRole(role: Role) {
		return this.user?.roles.includes(role) ?? false;
	}

	kiosk = $state(browser ? localStorage.getItem('ffp_kiosk') === '1' : false);

	setKiosk(on: boolean) {
		this.kiosk = on;
		if (browser) on ? localStorage.setItem('ffp_kiosk', '1') : localStorage.removeItem('ffp_kiosk');
	}

	setToken(token: string) {
		this.token = token;
		if (browser) localStorage.setItem(STORAGE_KEY, token);
	}

	setUser(user: CurrentUser) {
		this.user = user;
	}

	logout() {
		this.token = null;
		this.user = null;
		this.kiosk = false;
		if (browser) {
			localStorage.removeItem(STORAGE_KEY);
			localStorage.removeItem('ffp_kiosk');
		}
	}
}

export const auth = new AuthState();
