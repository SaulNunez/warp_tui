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
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Input, Static, Footer, Header
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from rich.console import RenderableType
from typing import List

from warp.representation.markup import Deck
from wap_request.wap_request import request_wap
from renderer import WMLRenderer


from textual.widget import Widget

class ContentView(Vertical):
    """Container content area that displays raw or rendered WML layout components."""
    
    def set_content(self, renderables: List[RenderableType] | str):
        """Mounts rendered WML components or raw text into the container."""
        self.remove_children()
        if isinstance(renderables, str):
            self.mount(Static(renderables))
        else:
            for item in renderables:
                if isinstance(item, Widget):
                    self.mount(item)
                else:
                    self.mount(Static(item))




class StatusBar(Static):
    """A simple status bar to show title and status info."""

    def update_status(self, title: str = "", status: str = ""):
        self.update(f"[b]{title}[/b] — {status}")


class BrowserApp(App):
    CSS = """
    #content {
        overflow-y: scroll;
        height: 1fr;
        padding: 1;
    }
    #toolbar {
        height: 3;
        margin-bottom: 1;
    }
    #url_input {
        width: 1fr;
    }
    """
    BINDINGS = [("d", "debug", "Toggle Debug")]
    TITLE = "WARP WML Browser"


    history = reactive(list)
    history_index = reactive(-1)
    page_title = reactive("")
    page_status = reactive("")
    current_deck = reactive(Deck, init=None)
    card_index = reactive(0)
    input_store = reactive(dict)

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
        self.input_store = {}
        self.query_one("#url_input").focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Stores input values under the current URL for any WML input field."""
        if event.input.id and event.input.id.startswith("wml_input_"):
            input_name = event.input.id.replace("wml_input_", "")
            current_url = self.page_title
            if current_url:
                if current_url not in self.input_store:
                    self.input_store[current_url] = {}
                self.input_store[current_url][input_name] = event.value



    async def action_debug(self) -> None:
        self.log(f"History: {self.history} Index: {self.history_index}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button
        button_id = button.id or ""

        if button_id == "back":
            await self.navigate_back()
            return
        elif button_id == "forward":
            await self.navigate_forward()
            return
        elif button_id == "reload":
            await self.reload()
            return

        # Handle <a> tag buttons
        if hasattr(button, "action_target") and button.action_target:
            target_url = self._resolve_url(button.action_target)
            await self.load_url(target_url, add_to_history=True)
            return

        # Handle WML <anchor> action buttons
        if hasattr(button, "wml_action") and button.wml_action:
            action = button.wml_action
            from warp.representation.navigation import GoElement, PrevElement, RefreshElement

            if isinstance(action, GoElement):
                target_url = self._resolve_url(action.href)
                params = {}

                # Resolve postfields with variable substitution ($(name) or input_store)
                current_url_store = self.input_store.get(self.page_title, {})
                for pf in getattr(action, "postfields", []):
                    val = pf.value
                    if val.startswith("$(") and val.endswith(")"):
                        var_name = val[2:-1]
                        val = current_url_store.get(var_name, "")
                    params[pf.name] = val

                if params:
                    from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
                    parsed = urlparse(target_url)
                    query = parse_qs(parsed.query)
                    for k, v in params.items():
                        query[k] = [v]
                    new_query = urlencode(query, doseq=True)
                    target_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

                await self.load_url(target_url, add_to_history=True)

            elif isinstance(action, PrevElement):
                await self.navigate_back()

    def _resolve_url(self, href: str) -> str:
        """Resolves relative URLs against current page URL."""
        if href.startswith("http://") or href.startswith("https://"):
            return href
        from urllib.parse import urljoin
        base_url = self.page_title
        return urljoin(base_url, href)


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

        content_widget.set_content(f"Loading {url} ...")
        self._update_nav_buttons()

        try:
            status, text = await request_wap(url)
            status = int(status)
            if status >= 400:
                content_widget.set_content(f"Error {status} while fetching {url}")
                self.page_status = f"Error {status}"
                status_bar.update_status(self.page_title, self.page_status)
                return

            # Try parsing WML with warp parser
            try:
                from warp.wml import parse_from_string
                deck_or_text = parse_from_string(text)
            except Exception as parse_err:
                deck_or_text = text


            if isinstance(deck_or_text, Deck):
                self.current_deck = deck_or_text
                if self.current_deck.cards:
                    card = self.current_deck.cards[self.card_index]
                    rendered_items = WMLRenderer.render_card(card)
                    content_widget.set_content(rendered_items)

                    # Restore stored values for input fields on this URL
                    stored_vals = self.input_store.get(url, {})
                    for input_widget in content_widget.query(Input):
                        if input_widget.id and input_widget.id.startswith("wml_input_"):
                            name = input_widget.id.replace("wml_input_", "")
                            if name in stored_vals:
                                input_widget.value = stored_vals[name]

                else:
                    content_widget.set_content("Deck has no cards.")
            else:
                content_widget.set_content(str(deck_or_text))



            self.page_status = "Loaded"

            if add_to_history:
                if self.history_index < len(self.history) - 1:
                    self.history = self.history[: self.history_index + 1]
                self.history.append(url)
                self.history_index = len(self.history) - 1

        except Exception as e:
            content_widget.set_content(f"Failed to fetch {url}: {e}")
            self.page_status = f"Failed: {e}"

        status_bar.update_status(self.page_title, self.page_status)
        self._update_nav_buttons()


if __name__ == "__main__":
    app = BrowserApp()
    app.run()

