import { describe, expect, it } from 'vitest';

import { MarkdownPipe } from './markdown.pipe';

describe('MarkdownPipe', () => {
  const pipe = new MarkdownPipe();

  it('renders bold text as a strong element', () => {
    expect(pipe.transform('**important**')).toContain('<strong>important</strong>');
  });

  it('renders a list as actual list markup', () => {
    const html = pipe.transform('- one\n- two');
    expect(html).toContain('<ul>');
    expect(html).toContain('<li>one</li>');
  });

  it('renders a single newline as a line break (GFM-style)', () => {
    expect(pipe.transform('line one\nline two')).toContain('<br>');
  });
});
