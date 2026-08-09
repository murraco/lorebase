import { Injectable, signal } from '@angular/core';

export type ThemePreference = 'light' | 'dark';

const STORAGE_KEY = 'lorebase.theme';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  /** Two states, not three. "System" was a real option but it made the
   * control a three-way cycle for something people treat as a switch —
   * you had to click twice to get back to where you were. The OS
   * preference still decides the *initial* value on a machine that has
   * never chosen; after that the choice is explicit and sticky.
   */
  readonly preference = signal<ThemePreference>(this.read());

  constructor() {
    this.apply(this.preference());
  }

  toggle(): void {
    const value: ThemePreference = this.preference() === 'dark' ? 'light' : 'dark';
    this.preference.set(value);
    this.apply(value);
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Private browsing: the choice still applies for this session.
    }
  }

  private apply(value: ThemePreference): void {
    document.documentElement.setAttribute('data-theme', value);
  }

  private read(): ThemePreference {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === 'light' || stored === 'dark') return stored;
    } catch {
      // Fall through to the OS preference.
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
}
