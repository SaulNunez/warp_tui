import xml
from xml.sax import ContentHandler
from typing import TextIO

from warp.representation.html.table import TableColumn, TableElement, TableRow
from warp.representation.html.text import (
    AHtmlElement, BigTextHtmlElement, BoldTextHtmlElement,
    ItalicTextElement, ParagraphHtmlElement, SmallTextHtmlElement,
    StrongTextHtmlElement, TextContent, UnderlineTextElement
)
from warp.representation.markup import Card, Deck, WMLElement
from warp.representation.navigation import (
    AnchorElement, GoElement, NoOpElement, PrevElement, RefreshElement
)
from warp.representation.input import Input as WmlInput


class RobustWMLParser(ContentHandler):
    def __init__(self):
        super().__init__()
        self.data = Deck()
        self._current_card: Card = None
        self._paragraph_element: ParagraphHtmlElement = None
        self._current_anchor: AnchorElement = None
        self.element_stack = []

    def startElement(self, name, attrs):
        self.element_stack.append(name)

        if name == "card":
            card_id = attrs.get("id", "card")
            card_title = attrs.get("title", "")
            self._current_card = Card(card_id, card_title)
            self.data.cards.append(self._current_card)

        elif name == "p":
            align = attrs.get("align", "left")
            mode = attrs.get("mode", "wrap")
            self._paragraph_element = ParagraphHtmlElement(parent=self._current_card)
            self._paragraph_element.align_from_str(align)
            self._paragraph_element.mode_from_str(mode)
            if self._current_card:
                self._current_card.children.append(self._paragraph_element)

        elif name == "input":
            input_name = attrs.get("name", "input")
            size = int(attrs.get("size", -1))
            fmt = attrs.get("format", "*")
            wml_input = WmlInput(name=input_name, size=size, format=fmt)
            if self._paragraph_element:
                self._paragraph_element.children.append(wml_input)

        elif name == "anchor":
            self._current_anchor = AnchorElement()
            if not isinstance(self._current_anchor, dict) and not hasattr(self._current_anchor, "children"):
                self._current_anchor.children = []
            elif isinstance(self._current_anchor, dict):
                self._current_anchor["children"] = []
            if self._paragraph_element:
                self._paragraph_element.children.append(self._current_anchor)

        elif name == "go":
            href = attrs.get("href", "")
            method = attrs.get("method", "get")
            go_elem = GoElement(href=href, method=method)
            if self._current_anchor:
                children = self._current_anchor["children"] if isinstance(self._current_anchor, dict) else self._current_anchor.children
                children.append(go_elem)

        elif name == "a":
            href = attrs.get("href", "")
            a_elem = AHtmlElement(href=href, parent=self._paragraph_element)
            if self._paragraph_element:
                self._paragraph_element.children.append(a_elem)

    def endElement(self, name):
        if self.element_stack and self.element_stack[-1] == name:
            self.element_stack.pop()

        if name == "p":
            self._paragraph_element = None
        elif name == "anchor":
            self._current_anchor = None

    def characters(self, content):
        text = content.strip()
        if not text:
            return

        if self._current_anchor:
            children = self._current_anchor["children"] if isinstance(self._current_anchor, dict) else self._current_anchor.children
            children.append(text)
        elif self._paragraph_element:
            self._paragraph_element.children.append(text)


def parse_wml_robust(contents: str) -> Deck:
    parser = xml.sax.make_parser()
    handler = RobustWMLParser()
    parser.setContentHandler(handler)
    parser.parseString(contents)
    return handler.data
