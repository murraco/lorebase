import { Component, inject, OnInit, signal } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { SourcesService } from '../../core/sources/sources.service';
import { AddSourceModalComponent } from './add-source-modal.component';

@Component({
  selector: 'lorebase-shell',
  imports: [RouterOutlet, AddSourceModalComponent],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.css',
})
export class ShellComponent implements OnInit {
  protected readonly auth = inject(AuthService);
  protected readonly sourcesService = inject(SourcesService);
  private readonly router = inject(Router);

  protected readonly showAddSourceModal = signal(false);

  async ngOnInit(): Promise<void> {
    await this.sourcesService.refresh();
  }

  protected async logout(): Promise<void> {
    await this.auth.logout();
    await this.router.navigateByUrl('/login');
  }
}
