import { Component, computed, inject, OnInit, signal } from '@angular/core';

import { AnalyticsService } from '../../core/analytics/analytics.service';
import type { DashboardMetrics } from '../../core/models';

@Component({
  selector: 'lorebase-panel-page',
  templateUrl: './panel.page.html',
  styleUrl: './panel.page.css',
})
export class PanelPage implements OnInit {
  private readonly analyticsService = inject(AnalyticsService);

  protected readonly metrics = signal<DashboardMetrics | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  /** The tallest bar sets the scale for every other bar — without this a
   * quiet 14-day stretch (max 2 queries/day) would draw every bar nearly
   * full height, and a single busy day would make everything else vanish
   * to nothing. */
  protected readonly maxDailyQueries = computed(() => {
    const days = this.metrics()?.queries_by_day ?? [];
    return Math.max(1, ...days.map((d) => d.count));
  });

  async ngOnInit(): Promise<void> {
    try {
      this.metrics.set(await this.analyticsService.dashboard());
    } catch {
      this.error.set("Couldn't load the dashboard.");
    } finally {
      this.loading.set(false);
    }
  }

  protected barPercent(count: number): number {
    return Math.round((count / this.maxDailyQueries()) * 100);
  }

  protected dayLabel(isoDate: string): string {
    // en-US, always: matching the app's answers-in-English decision
    // (see docs/roadmap.md), not the visitor's locale.
    return new Date(isoDate).toLocaleDateString('en-US', { weekday: 'short' });
  }

  // Four decimals, not two: at light usage a month's total is still
  // fractions of a cent, and toFixed(2) prints a misleading "$0.00" for
  // any real, nonzero cost below half a cent (same reasoning as the
  // per-answer cost in chat.page.ts).
  protected formatCost(usd: number | null): string {
    return usd === null ? '—' : `$${usd.toFixed(4)}`;
  }

  protected formatPercent(value: number | null): string {
    return value === null ? '—' : `${value}%`;
  }

  protected formatMs(ms: number | null): string {
    return ms === null ? '—' : `${ms}ms`;
  }
}
