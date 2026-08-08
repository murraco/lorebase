import { Component, HostListener, input, output } from '@angular/core';

import type { Citation } from '../../core/models';

/** The cited passage, docked to the viewport.
 *
 * Deliberately not expanded inline in the thread, which is how it worked
 * first: opening a passage under a long answer put it somewhere off
 * screen, and switching between notes meant scrolling back up to reach
 * the list again.
 */
@Component({
  selector: 'lorebase-passage-reader',
  templateUrl: './passage-reader.component.html',
  styleUrl: './passage-reader.component.css',
})
export class PassageReaderComponent {
  readonly citation = input.required<Citation>();
  /** Its number within its own answer, so the panel and the margin note
   * carry the same label. */
  readonly index = input<number | null>(null);

  readonly closed = output<void>();

  /** Escape closes it, like every other transient surface. Bound on the
   * document because focus may still be in the thread behind. */
  @HostListener('document:keydown.escape')
  protected onEscape(): void {
    this.closed.emit();
  }
}
