import tiktoken

# A consistent sizing proxy, not a match for any specific LLM's tokenizer —
# chunk-size decisions only need "roughly how much text is this", not exact
# billing-accurate counts.
_encoding = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoding.encode(text))
