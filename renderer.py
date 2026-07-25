"""
Renderer module to convert Warp WML AST structures (Deck, Card, Paragraph, Text elements, Tables, Inputs)
into Rich / Textual renderables for Textual UI.
"""
from typing import List, Union
from rich.text import Text
from rich.table import Table as RichTable
from rich.panel import Panel
from rich.console import RenderableType
from textual.widget import Widget
from textual.widgets import Button as TextualButton, Input as TextualInput


from warp.representation.markup import Deck, Card, WMLElement
from warp.representation.html.text import (
    ParagraphHtmlElement, TextContent, TextHtmlSubElement,
    StrongTextHtmlElement, BoldTextHtmlElement, BigTextHtmlElement,
    SmallTextHtmlElement, ItalicTextElement, UnderlineTextElement,
    AHtmlElement, BreakHtmlElement, PreformattedText, AlignTypes
)
from warp.representation.html.table import TableElement, TableRow, TableColumn
try:
    from warp.representation.html.image import Image
except ModuleNotFoundError:
    from warp.representation.markup import HtmlElement
    class Image(HtmlElement):
        def __init__(self, src="", localsrc="", alt="", **kwargs):
            super().__init__()
            self.src = src
            self.localsrc = localsrc
            self.alt = alt
        def get_source(self) -> str:
            return self.localsrc or self.src

from warp.representation.input import Input as WmlInput, Select, Option, OptionGroup


try:
    from warp.representation.navigation import AnchorElement, GoElement, PostFieldElement, PrevElement, RefreshElement
except ImportError:
    AnchorElement = None
    GoElement = None
    PostFieldElement = None
    PrevElement = None
    RefreshElement = None



class WMLRenderer:
    """
    Renders WML AST elements into Rich Text / Renderable objects suitable for Textual widgets.
    """


    @classmethod
    def render_card(cls, card: Card) -> List[Union[RenderableType, Widget]]:
        """Renders a Card's children into a list of Rich Renderables and Textual Widgets."""
        renderables: List[Union[RenderableType, Widget]] = []

        if not card or not hasattr(card, "children"):
            return [Text("Empty or invalid card", style="dim italic")]

        for child in card.children:
            if isinstance(child, ParagraphHtmlElement):
                # Render paragraph children, splitting out inline inputs
                cls._render_paragraph_with_widgets(child, renderables)
            else:
                rendered = cls.render_element(child)
                if rendered is not None:
                    renderables.append(rendered)

        return renderables

    @classmethod
    def _render_paragraph_with_widgets(cls, paragraph: ParagraphHtmlElement, target_list: List[Union[RenderableType, Widget]]):
        """Renders a paragraph, emitting inline WmlInput elements as interactive Input widgets."""
        current_text = Text()
        
        # Alignment setting
        align = getattr(paragraph, "align", AlignTypes.left)
        if align == AlignTypes.center:
            current_text.justify = "center"
        elif align == AlignTypes.right:
            current_text.justify = "right"

        for child in paragraph.children:
            if isinstance(child, WmlInput):
                if len(current_text):
                    target_list.append(current_text)
                    current_text = Text()
                    if align == AlignTypes.center:
                        current_text.justify = "center"
                    elif align == AlignTypes.right:
                        current_text.justify = "right"
                
                input_name = getattr(child, "name", "input")
                widget = TextualInput(placeholder=f"Enter {input_name}...", id=f"wml_input_{input_name}")
                target_list.append(widget)

            elif isinstance(child, AHtmlElement):
                if len(current_text):
                    target_list.append(current_text)
                    current_text = Text()

                href = getattr(child, "href", "")
                label = getattr(child, "content", "") or href or "Link"
                btn = TextualButton(f"🔗 {label}")
                btn.action_target = href
                btn.action_type = "get"
                target_list.append(btn)


            elif AnchorElement and isinstance(child, AnchorElement):
                if len(current_text):
                    target_list.append(current_text)
                    current_text = Text()

                btn = cls.create_anchor_button(child)
                if btn:
                    target_list.append(btn)

            elif isinstance(child, str):
                current_text.append(child)
            elif isinstance(child, BreakHtmlElement):
                current_text.append("\n")
            elif isinstance(child, TextContent):
                cls._append_styled_text(current_text, child)
            else:
                current_text.append(str(child))

        if len(current_text):
            target_list.append(current_text)

    @classmethod
    def create_anchor_button(cls, anchor: AnchorElement) -> Union[Widget, None]:
        """Creates an interactive TextualButton for a WML <anchor> node with its action and postfield data."""
        label_parts = []
        target_action = None

        children = getattr(anchor, "children", [])
        for child in children:
            if isinstance(child, str):
                label_parts.append(child)
            elif isinstance(child, TextContent):
                label_parts.append(getattr(child, "content", str(child)))
            elif isinstance(child, (GoElement, PrevElement, RefreshElement)):
                target_action = child

        label = "".join(label_parts).strip() or "Action"
        btn = TextualButton(f"▶ {label}", variant="primary")
        btn.wml_action = target_action
        return btn



    @classmethod
    def render_element(cls, elem: WMLElement) -> RenderableType:
        """Dispatches rendering for a specific WML element."""
        if AnchorElement and isinstance(elem, AnchorElement):
            return cls.render_anchor(elem)
        elif isinstance(elem, ParagraphHtmlElement):
            return cls.render_paragraph(elem)
        elif isinstance(elem, TableElement):
            return cls.render_table(elem)
        elif isinstance(elem, WmlInput):
            return cls.render_input(elem)
        elif isinstance(elem, Image):
            return cls.render_image(elem)
        elif isinstance(elem, TextContent):
            return cls.render_text_content(elem)
        elif isinstance(elem, str):
            return Text(elem)
        else:
            return Text(str(elem))

    @classmethod
    def render_anchor(cls, anchor: AnchorElement) -> Text:
        """Renders a WML <anchor> element with its nested text and action link."""
        res = Text()
        label_parts = []
        href = ""

        children = anchor.get("children", []) if isinstance(anchor, dict) else getattr(anchor, "children", [])
        for child in children:
            if isinstance(child, str):
                label_parts.append(child)
            elif isinstance(child, TextContent):
                label_parts.append(getattr(child, "content", str(child)))
            elif GoElement and isinstance(child, GoElement):
                href = getattr(child, "href", "")

        label = "".join(label_parts).strip() or "Link"
        res.append(f"🔗 [{label}]", style=f"bold cyan link {href}" if href else "bold cyan underline")
        return res


    @classmethod
    def render_paragraph(cls, paragraph: ParagraphHtmlElement) -> Text:
        """Renders a Paragraph element, building styled Rich Text."""
        rich_text = Text()

        # Handle paragraph alignment
        align = getattr(paragraph, "align", AlignTypes.left)
        if align == AlignTypes.center:
            rich_text.justify = "center"
        elif align == AlignTypes.right:
            rich_text.justify = "right"
        else:
            rich_text.justify = "left"

        for child in paragraph.children:
            if isinstance(child, str):
                rich_text.append(child)
            elif isinstance(child, BreakHtmlElement):
                rich_text.append("\n")
            elif AnchorElement and isinstance(child, AnchorElement):
                rich_text.append(cls.render_anchor(child))
            elif isinstance(child, TextContent):
                cls._append_styled_text(rich_text, child)
            elif isinstance(child, WmlInput):
                # When an input is embedded in a paragraph, we wrap preceding text if any
                pass
            else:
                rich_text.append(str(child))

        return rich_text


    @classmethod
    def _append_styled_text(cls, target: Text, text_elem: TextContent):
        """Recursively formats and appends styled text elements."""
        content = getattr(text_elem, "content", str(text_elem))
        style = ""

        if isinstance(text_elem, (StrongTextHtmlElement, BoldTextHtmlElement)):
            style = "bold"
        elif isinstance(text_elem, ItalicTextElement):
            style = "italic"
        elif isinstance(text_elem, UnderlineTextElement):
            style = "underline"
        elif isinstance(text_elem, BigTextHtmlElement):
            style = "bold yellow"
        elif isinstance(text_elem, SmallTextHtmlElement):
            style = "dim"
        elif isinstance(text_elem, AHtmlElement):
            href = getattr(text_elem, "href", "")
            style = f"link {href}" if href else "underline cyan"

        target.append(content, style=style if style else None)

    @classmethod
    def render_table(cls, table_elem: TableElement) -> RichTable:
        """Renders a TableElement into a formatted Rich Table."""
        grid = RichTable(show_header=False, expand=True, padding=(0, 1))

        cols_count = max(table_elem.columns, 1)
        for i in range(cols_count):
            align_char = table_elem.column_alignment(i)
            justify = "left"
            if align_char == "r":
                justify = "right"
            elif align_char == "c":
                justify = "center"
            grid.add_column(justify=justify)

        for row in table_elem.rows:
            row_cells = []
            for col in row.columns:
                col_text = col.content if hasattr(col, "content") else str(col)
                row_cells.append(col_text)
            # Pad row if columns don't match specified count
            while len(row_cells) < cols_count:
                row_cells.append("")
            grid.add_row(*row_cells[:cols_count])

        return grid

    @classmethod
    def render_input(cls, input_elem: WmlInput) -> Panel:
        """Renders a WML Input prompt box."""
        name = getattr(input_elem, "name", "input")
        return Panel(
            Text(f"[ {name} ] _______________", style="cyan"),
            title=f"Input: {name}",
            border_style="dim"
        )

    @classmethod
    def render_image(cls, img_elem: Image) -> Text:
        """Renders an image fallback/alt text."""
        alt = getattr(img_elem, "alt", "")
        src = img_elem.get_source()
        label = alt if alt else src
        return Text(f"🖼 [{label}]", style="magenta italic")

    @classmethod
    def render_text_content(cls, text_elem: TextContent) -> Text:
        """Renders raw TextContent."""
        res = Text()
        cls._append_styled_text(res, text_elem)
        return res
