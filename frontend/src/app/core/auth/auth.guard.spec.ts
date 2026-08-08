import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  provideRouter,
  RouterStateSnapshot,
  UrlTree,
} from '@angular/router';
import { describe, expect, it, vi } from 'vitest';

import { authGuard } from './auth.guard';
import { AuthService } from './auth.service';

function runGuard() {
  return TestBed.runInInjectionContext(() =>
    authGuard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
  );
}

describe('authGuard', () => {
  it('allows navigation without re-checking when a session is already known', async () => {
    const restoreSession = vi.fn();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: {
            checked: () => true,
            currentUser: () => ({ id: 'u1', username: 'alice', workspaces: [] }),
            restoreSession,
          },
        },
      ],
    });

    expect(await runGuard()).toBe(true);
    expect(restoreSession).not.toHaveBeenCalled();
  });

  it('awaits restoreSession when unchecked, then redirects to /login if there is no session', async () => {
    const restoreSession = vi.fn().mockResolvedValue(undefined);
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: { checked: () => false, currentUser: () => null, restoreSession },
        },
      ],
    });

    const result = await runGuard();

    expect(restoreSession).toHaveBeenCalled();
    expect(result).toBeInstanceOf(UrlTree);
  });
});
