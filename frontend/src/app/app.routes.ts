import { Routes } from '@angular/router';

import { authGuard } from './core/auth/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/login/login.page').then((m) => m.LoginPage),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./features/shell/shell.component').then((m) => m.ShellComponent),
    children: [
      { path: '', redirectTo: 'chat', pathMatch: 'full' },
      {
        path: 'chat',
        loadComponent: () => import('./features/chat/chat.page').then((m) => m.ChatPage),
      },
      {
        path: 'corpus',
        loadComponent: () => import('./features/corpus/corpus.page').then((m) => m.CorpusPage),
      },
      {
        path: 'panel',
        loadComponent: () => import('./features/panel/panel.page').then((m) => m.PanelPage),
      },
      {
        path: 'chat/:conversationId',
        loadComponent: () => import('./features/chat/chat.page').then((m) => m.ChatPage),
      },
    ],
  },
];
