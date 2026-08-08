import { Component, inject, OnInit, output, signal } from '@angular/core';

import type { SystemStatus } from '../../core/models';
import { SystemService } from '../../core/system/system.service';

@Component({
  selector: 'lorebase-system-status-modal',
  templateUrl: './system-status-modal.component.html',
  styleUrl: './system-status-modal.component.css',
})
export class SystemStatusModalComponent implements OnInit {
  private readonly systemService = inject(SystemService);

  readonly closed = output<void>();

  protected readonly status = signal<SystemStatus | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  async ngOnInit(): Promise<void> {
    try {
      this.status.set(await this.systemService.status());
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to load system status.');
    } finally {
      this.loading.set(false);
    }
  }

  /** Percentage of indexed chunks that have an embedding. Anything below
   * 100 means retrieval is running on partial data. */
  protected embeddedPercent(status: SystemStatus): number {
    if (status.chunks === 0) return 100;
    return Math.floor((status.embedded_chunks / status.chunks) * 100);
  }
}
