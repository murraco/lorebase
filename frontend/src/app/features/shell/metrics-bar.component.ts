import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';

import type { SystemStatus } from '../../core/models';
import { SystemService } from '../../core/system/system.service';

/** Always-visible readout of what the system is actually doing. Taken
 * from the console direction: the point of the redesign is that this is
 * an instrument, not a chat, and an instrument shows its state without
 * being asked.
 */
@Component({
  selector: 'lorebase-metrics-bar',
  imports: [DecimalPipe],
  templateUrl: './metrics-bar.component.html',
  styleUrl: './metrics-bar.component.css',
})
export class MetricsBarComponent implements OnInit {
  private readonly systemService = inject(SystemService);

  protected readonly status = signal<SystemStatus | null>(null);

  /** Share of chunks that are searchable. Anything under 100 means part
   * of the corpus is invisible to semantic search right now. */
  protected readonly embeddedPercent = computed(() => {
    const s = this.status();
    if (!s || s.chunks === 0) return null;
    return Math.floor((s.embedded_chunks / s.chunks) * 100);
  });

  /** Answers that cited nothing. The system prompt forbids answering
   * outside the retrieved context, so a non-zero share is a retrieval
   * quality signal, not trivia. */
  protected readonly ungroundedPercent = computed(() => {
    const s = this.status();
    if (!s || s.answers === 0) return null;
    return Math.round((s.ungrounded_answers / s.answers) * 100);
  });

  async ngOnInit(): Promise<void> {
    try {
      this.status.set(await this.systemService.status());
    } catch {
      // A metrics strip that can't load simply doesn't render. It is
      // context, never the reason you came to the page.
    }
  }

  protected latencySeconds(ms: number | null | undefined): string | null {
    return ms === null || ms === undefined ? null : (ms / 1000).toFixed(1);
  }
}
