import { Pipe, PipeTransform } from '@angular/core';
import { marked } from 'marked';

@Pipe({ name: 'markdown', pure: true })
export class MarkdownPipe implements PipeTransform {
  transform(content: string): string {
    // { async: false } pins marked's synchronous overload — a pure pipe
    // can't return a Promise. The result is bound via [innerHTML], which
    // Angular sanitizes by default (no bypassSecurityTrustHtml here) —
    // this content ultimately comes from an LLM response, not something
    // to trust blindly just because the server validated its citations.
    return marked.parse(content, { async: false, breaks: true });
  }
}
