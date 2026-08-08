import { computed, Injectable, signal } from '@angular/core';

import { readCookie } from '../api/cookies';

export interface WorkspaceSummary {
  id: string;
  name: string;
}

export interface CurrentUser {
  id: string;
  username: string;
  workspaces: WorkspaceSummary[];
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly currentUser = signal<CurrentUser | null>(null);
  // Distinguishes "haven't checked yet" from "checked, and there's no
  // session" — a guard needs that distinction to know whether to await
  // restoreSession() or trust the (possibly null) currentUser it already has.
  readonly checked = signal(false);
  // Single-workspace assumption: Membership supports a user belonging to
  // several, but nothing in this UI needs a workspace switcher yet — the
  // first one is "the" workspace.
  readonly primaryWorkspace = computed(() => this.currentUser()?.workspaces[0] ?? null);

  async restoreSession(): Promise<void> {
    const response = await fetch('/api/auth/me/', { credentials: 'same-origin' });
    this.currentUser.set(response.ok ? ((await response.json()) as CurrentUser) : null);
    this.checked.set(true);
  }

  async login(username: string, password: string): Promise<void> {
    await this.ensureCsrfCookie();
    const response = await fetch('/api/auth/login/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': readCookie('csrftoken') ?? '',
      },
      body: JSON.stringify({ username, password }),
    });
    const body = (await response.json()) as CurrentUser | { detail: string };
    if (!response.ok) {
      throw new Error('detail' in body ? body.detail : 'Login failed.');
    }
    this.currentUser.set(body as CurrentUser);
    this.checked.set(true);
  }

  async logout(): Promise<void> {
    await fetch('/api/auth/logout/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': readCookie('csrftoken') ?? '' },
    });
    this.currentUser.set(null);
  }

  private async ensureCsrfCookie(): Promise<void> {
    if (!readCookie('csrftoken')) {
      await fetch('/api/auth/csrf/', { credentials: 'same-origin' });
    }
  }
}
