import { Component, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import type { FeedbackRating } from '../../core/models';

/** Split out of ChatPage, which had grown its own style budget past the
 * 8kB hard limit — this is exactly the extraction pattern already used
 * elsewhere in the app (SourceListComponent out of ShellComponent) when
 * that happens: the fix is a smaller component, not a bigger budget.
 * Named for what it is — the row of things you can do with one answer,
 * not just "feedback" — since copying the answer joined the rating
 * buttons here rather than getting a component of its own.
 */
@Component({
  selector: 'lorebase-answer-actions',
  imports: [FormsModule],
  templateUrl: './answer-actions.component.html',
  styleUrl: './answer-actions.component.css',
})
export class AnswerActionsComponent {
  readonly rating = input<FeedbackRating | null | undefined>(null);
  readonly comment = input<string | undefined>('');
  /** The raw markdown, not the rendered HTML — what you'd want back if
   * you're pasting this answer into another note. */
  readonly content = input.required<string>();

  readonly rated = output<FeedbackRating>();
  readonly commentSaved = output<string>();

  protected readonly editing = signal(false);
  protected draft = '';

  protected readonly copied = signal(false);
  private copiedTimeout?: ReturnType<typeof setTimeout>;

  protected openEditor(): void {
    this.draft = this.comment() ?? '';
    this.editing.set(true);
  }

  protected save(): void {
    this.editing.set(false);
    this.commentSaved.emit(this.draft.trim());
  }

  protected async copy(): Promise<void> {
    await navigator.clipboard.writeText(this.content());
    this.copied.set(true);
    clearTimeout(this.copiedTimeout);
    this.copiedTimeout = setTimeout(() => this.copied.set(false), 1500);
  }
}
