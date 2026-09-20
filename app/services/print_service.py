"""
Print service – opens generated HTML in the default system browser.
"""
from app.views.document_preview_dialog import open_html_in_browser


class PrintService:
    def __init__(self, ctx):
        self.ctx = ctx

    def print_html(self, html, parent_widget=None):
        """Open HTML in browser for printing."""
        open_html_in_browser(html, "dokument")
        return True

    def print_with_preview(self, html, title="", parent_widget=None):
        """Open HTML in browser."""
        open_html_in_browser(html, title)
