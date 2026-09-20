"""
Document preview – opens generated HTML in the default web browser.
User can edit/print from there as usual.
"""
import os
import tempfile
import webbrowser


def open_html_in_browser(html_content: str, title: str = "dokument"):
    """Save HTML to a temp file and open it in the default browser."""
    # Create temp file that won't be auto-deleted (browser needs it)
    fd, path = tempfile.mkstemp(suffix=".html", prefix=f"TS_{title}_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html_content)
    webbrowser.open(f"file:///{path}")
    return path


class DocumentPreviewDialog:
    """Compatibility wrapper – just opens in browser instead of a Qt dialog."""

    def __init__(self, html_content, title="Náhled dokumentu", parent=None):
        self.html_content = html_content
        self.title = title

    def exec(self):
        open_html_in_browser(self.html_content, self.title)
        return 0
