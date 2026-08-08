import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { describe, expect, it, vi } from 'vitest';

import { AuthService } from '../../core/auth/auth.service';
import { LoginPage } from './login.page';

async function setup(login: (username: string, password: string) => Promise<void>) {
  await TestBed.configureTestingModule({
    imports: [LoginPage],
    providers: [provideRouter([]), { provide: AuthService, useValue: { login } }],
  }).compileComponents();

  const fixture = TestBed.createComponent(LoginPage);
  return { fixture, page: fixture.componentInstance };
}

describe('LoginPage', () => {
  it('logs in and navigates to /chat on success', async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    const { fixture, page } = await setup(login);
    const navigateSpy = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);

    page['username'] = 'alice';
    page['password'] = 'secret';
    await page['submit']();

    expect(login).toHaveBeenCalledWith('alice', 'secret');
    expect(navigateSpy).toHaveBeenCalledWith('/chat');
    expect(page['error']()).toBeNull();
    fixture.destroy();
  });

  it('shows the error message when login fails, without navigating', async () => {
    const login = vi.fn().mockRejectedValue(new Error('Invalid credentials.'));
    const { fixture, page } = await setup(login);
    const navigateSpy = vi.spyOn(TestBed.inject(Router), 'navigateByUrl');

    page['username'] = 'alice';
    page['password'] = 'wrong';
    await page['submit']();
    fixture.detectChanges();

    expect(page['error']()).toBe('Invalid credentials.');
    expect(navigateSpy).not.toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Invalid credentials.');
    fixture.destroy();
  });
});
