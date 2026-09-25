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
		if (browser) localStorage.removeItem(STORAGE_KEY);
	}
}

export const auth = new AuthState();
