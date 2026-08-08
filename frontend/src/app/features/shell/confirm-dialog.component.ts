import { Component, input, output } from '@angular/core';

/** One confirmation dialog, used for every destructive action. The
 * delete-source and delete-conversation dialogs were near-identical
 * copies of the same markup, which meant an accessibility fix or a style
 * change had to be made twice to stay consistent.
 */
@Component({
  selector: 'lorebase-confirm-dialog',
  templateUrl: './confirm-dialog.component.html',
  styleUrl: './confirm-dialog.component.css',
})
export class ConfirmDialogComponent {
  readonly title = input.required<string>();
  readonly message = input.required<string>();
  readonly busy = input(false);
  readonly error = input<string | null>(null);
  readonly confirmLabel = input('Delete');
  readonly busyLabel = input('Deleting…');

  readonly confirmed = output<void>();
  readonly cancelled = output<void>();
}
