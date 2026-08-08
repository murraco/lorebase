import { Injectable, signal } from '@angular/core';

export type ThemePreference = 'system' | 'light' | 'dark';

const STORAGE_KEY = 'lorebase.theme';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  /** Three states, not two: "system" is a real choice and the default.
   * Collapsing it into a boolean would mean the app stops following the
   * OS the moment anyone touches the toggle, which is not what an
   * untouched preference should imply. */
  readonly preference = signal<ThemePreference>(this.read());

  constructor() {
    this.apply(this.preference());
  }

  /** Cycles system → light → dark → system. A cycle rather than a switch
   * because there are three states and only one control. */
  next(): void {
    const order: ThemePreference[] = ['system', 'light', 'dark'];
    const value = order[(order.indexOf(this.preference()) + 1) % order.length];
    this.preference.set(value);
    this.apply(value);
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Private browsing: the choice still applies for this session.
    }
  }

  /** Absence of the attribute is what lets the prefers-color-scheme media
   * query in styles.css decide, so "system" removes it rather than
   * setting some third value. */
  private apply(value: ThemePreference): void {
    const root = document.documentElement;
    if (value === 'system') {
      root.removeAttribute('data-theme');
    } else {
      root.setAttribute('data-theme', value);
    }
  }

  private read(): ThemePreference {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored === 'light' || stored === 'dark' ? stored : 'system';
    } catch {
      return 'system';
    }
  }
}
