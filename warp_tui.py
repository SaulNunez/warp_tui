"""
Simple browser-like interface using Textual.
Features:
- Back, Forward, Reload buttons
- URL input
- Content area that shows fetched page text (basic HTML stripping)
- Status bar showing current page title and status
- Keeps history stack for back/forward navigation

Dependencies:
- textual
- httpx (or requests as fallback)
- beautifulsoup4 (optional, for nicer text extraction)

Run:
    pip install textual httpx beautifulsoup4
    python textual_browser.py

"""
from textual.app import App, ComposeResult, RenderResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Input, Static, Footer, Header
from textual.widget import Widget
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual import events

from warp.representation.markup import Deck
from wap_request.wap_request import request_wap


class ContentView(ScrollView):
    """Scrollable content area that displays raw or extracted text."""
    def set_text(self, text: str):
        return Static(text, expand=True)

class StatusBar(Static):
    """A simple status bar to show title and status info."""

    def update_status(self, title: str = "", status: str = ""):
        self.update(f"[b]{title}[/b] — {status}")


class BrowserApp(App):
    CSS_PATH = None
    BINDINGS = [("d", "debug", "Toggle Debug")]
    TITLE = "WARP WML Browser"

    history = reactive(list)
    history_index = reactive(-1)
    page_title = reactive("")
    page_status = reactive("")
    current_page = reactive(Deck, init=None)
    card_index = reactive(0)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container():
            with Vertical():
                with Horizontal(id="toolbar"):
                    yield Button("⟨ Back", id="back", disabled=True)
                    yield Button("Forward ⟩", id="forward", disabled=True)
                    yield Button("⟳ Reload", id="reload", disabled=True)
                    yield Input(placeholder="Enter URL (eg wml://example.com)", id="url_input")
                yield ContentView(id="content")
                yield StatusBar(id="status_bar")
        yield Footer()

    async def on_mount(self) -> None:
        self.history = []
        self.history_index = -1
        self.query_one("#url_input").focus()

    async def action_debug(self) -> None:
        self.log(f"History: {self.history} Index: {self.history_index}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            await self.navigate_back()
        elif button_id == "forward":
            await self.navigate_forward()
        elif button_id == "reload":
            await self.reload()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        url = event.value.strip()
        if not url:
            return
        if not url.startswith("http://"):
            url = "http://" + url
        await self.load_url(url, add_to_history=True)

    async def navigate_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            url = self.history[self.history_index]
            await self.load_url(url, add_to_history=False)
        self._update_nav_buttons()

    async def navigate_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            url = self.history[self.history_index]
            await self.load_url(url, add_to_history=False)
        self._update_nav_buttons()

    async def reload(self):
        if 0 <= self.history_index < len(self.history):
            url = self.history[self.history_index]
            await self.load_url(url, add_to_history=False)

    def _update_nav_buttons(self):
        back_btn = self.query_one("#back", Button)
        forward_btn = self.query_one("#forward", Button)
        reload_btn = self.query_one("#reload", Button)

        back_btn.disabled = not (self.history_index > 0)
        forward_btn.disabled = not (self.history_index < len(self.history) - 1)
        reload_btn.disabled = not (0 <= self.history_index < len(self.history))

        try:
            url_input = self.query_one(Input)
            url_input.value = self.history[self.history_index] if 0 <= self.history_index < len(self.history) else ""
        except Exception:
            pass

    async def load_url(self, url: str, add_to_history: bool = True):
        content_widget = self.query_one(ContentView)
        status_bar = self.query_one(StatusBar)

        self.page_title = url
        self.page_status = "Loading..."
        status_bar.update_status(self.page_title, self.page_status)

        content_widget.set_text(f"Loading {url} ...")
        self._update_nav_buttons()

        try:
            text, status = await request_wap(url)
            if status >= 400:
                content_widget.set_text(f"Error {status} while fetching {url}")
                self.page_status = f"Error {status}"
                status_bar.update_status(self.page_title, self.page_status)
                return

            if self.current_page is not None:
                display = str(self.currentPage.cards[self.card_index])

            content_widget.set_text(display)
            self.page_status = f"Loaded ({len(text)} chars)"

            if add_to_history:
                if self.history_index < len(self.history) - 1:
                    self.history = self.history[: self.history_index + 1]
                self.history.append(url)
                self.history_index = len(self.history) - 1

        except Exception as e:
            content_widget.set_text(f"Failed to fetch {url}: {e}")
            self.page_status = f"Failed: {e}"

        status_bar.update_status(self.page_title, self.page_status)
        self._update_nav_buttons()
