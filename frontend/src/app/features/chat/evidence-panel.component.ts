import { Component, input, output } from '@angular/core';

import type { Citation } from '../../core/models';

/** The sources behind one answer. Split out of ChatPage because it is a
 * self-contained concern with its own markup and styles — and because
 * keeping it there pushed that component past Angular's per-component
 * style budget, which was a fair signal that it had grown too broad.
 */
@Component({
  selector: 'lorebase-evidence-panel',
  templateUrl: './evidence-panel.component.html',
  styleUrl: './evidence-panel.component.css',
})
export class EvidencePanelComponent {
  readonly citations = input.required<Citation[]>();
  readonly focusedId = input<string | null>(null);
  readonly expandedId = input<string | null>(null);

  readonly focusChanged = output<string | null>();
  readonly toggled = output<string>();

  /** Trimmed to a few lines: the panel is for scanning, and the full
   * passage is one click away. */
  protected preview(citation: Citation): string {
    const text = citation.content.trim().replace(/\s+/g, ' ');
    return text.length > 180 ? text.slice(0, 179) + '…' : text;
  }

  /** Scores are not comparable across retrieval strategies, so this is
   * shown as provenance and never as a quality bar or a percentage. */
  protected formatScore(score: number | null | undefined): string | null {
    return score === null || score === undefined ? null : score.toFixed(3);
  }
}
