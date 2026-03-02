"""Tests for shared text utilities."""

from agent.channels.text_utils import strip_markdown


class TestStripMarkdown:
    def test_removes_headers(self):
        assert strip_markdown("## Hello World") == "Hello World"

    def test_removes_bold(self):
        assert strip_markdown("This is **bold** text") == "This is bold text"

    def test_removes_italic(self):
        assert strip_markdown("This is *italic* text") == "This is italic text"

    def test_removes_links(self):
        assert strip_markdown("[click here](https://example.com)") == "click here"

    def test_removes_code_blocks(self):
        text = "Before\n```python\ncode here\n```\nAfter"
        result = strip_markdown(text)
        assert "code here" not in result
        assert "Before" in result
        assert "After" in result

    def test_removes_inline_code(self):
        assert strip_markdown("Use `command` now") == "Use command now"

    def test_preserves_plain_text(self):
        assert strip_markdown("Just plain text") == "Just plain text"
