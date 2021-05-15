#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    This implementation of Event is triggered right after the Canvas has processed a text-rendering instruction
"""
import typing
from decimal import Decimal

from ptext.io.read.types import String
from ptext.pdf.canvas.canvas_graphics_state import CanvasGraphicsState
from ptext.pdf.canvas.event.event_listener import Event
from ptext.pdf.canvas.font.font import Font
from ptext.pdf.canvas.font.glyph_line import GlyphLine
from ptext.pdf.canvas.geometry.rectangle import Rectangle
from ptext.pdf.canvas.layout.paragraph import ChunkOfText


class ChunkOfTextRenderEvent(Event, ChunkOfText):
    """
    This implementation of Event is triggered right after the Canvas has processed a text-rendering instruction
    """

    def __init__(self, graphics_state: CanvasGraphicsState, raw_bytes: String):
        assert graphics_state.font is not None
        self._glyph_line: GlyphLine = GlyphLine(
            raw_bytes.get_value_bytes(),
            graphics_state.font,
            graphics_state.font_size,
            graphics_state.character_spacing,
            graphics_state.word_spacing,
            graphics_state.horizontal_scaling,
        )
        super(ChunkOfTextRenderEvent, self).__init__(
            font=graphics_state.font,
            font_size=graphics_state.font_size,
            font_color=graphics_state.non_stroke_color,
            text=self._glyph_line.get_text(),
        )
        m = graphics_state.text_matrix.mul(graphics_state.ctm)

        # calculate baseline box
        p0 = m.cross(Decimal(0), graphics_state.text_rise, Decimal(1))
        p1 = m.cross(
            self._glyph_line.get_width_in_text_space(),
            graphics_state.text_rise
            + graphics_state.font.get_ascent() * Decimal(0.001),
            Decimal(1),
        )

        # set baseline box
        self.baseline_bounding_box = Rectangle(
            min(p0[0], p1[0]), min(p0[1], p1[1]), abs(p1[0] - p0[0]), abs(p1[1] - p0[1])
        )

        # calculate bounding box
        uses_descent = any(
            [x in self.text.lower() for x in ["y", "p", "q", "f", "g", "j"]]
        )
        if uses_descent:
            p0 = m.cross(
                Decimal(0),
                graphics_state.text_rise
                + graphics_state.font.get_descent() * Decimal(0.001),
                Decimal(1),
            )
            p1 = m.cross(
                self._glyph_line.get_width_in_text_space(),
                graphics_state.text_rise
                + graphics_state.font.get_ascent() * Decimal(0.001),
                Decimal(1),
            )
            self.set_bounding_box(
                Rectangle(
                    min(p0[0], p1[0]),
                    min(p0[1], p1[1]),
                    abs(p1[0] - p0[0]),
                    abs(p1[1] - p0[1]),
                )
            )
        else:
            self.set_bounding_box(self.baseline_bounding_box)

        # calculate space character width estimate
        current_font: Font = graphics_state.font
        self._space_character_width_estimate = (
            current_font.get_space_character_width_estimate() * graphics_state.font_size
        )
        self._font_size = graphics_state.font_size

        # store graphics state
        self._graphics_state = graphics_state

    def get_font_size(self) -> Decimal:
        """
        This function returns the font size
        """
        return self._font_size

    def get_space_character_width_estimate(self) -> Decimal:
        """
        This function returns the width (in text space) of the space-character.
        """
        return self._space_character_width_estimate

    def get_baseline(self) -> Rectangle:
        """
        This function returns the bounding box of this ChunkOfTextRenderEvent,
        starting at the baseline (not at the descent)
        """
        return self.baseline_bounding_box

    def split_on_glyphs(self) -> typing.List["ChunkOfTextRenderEvent"]:
        """
        This function splits this ChunkOfTextRenderEvent on every Glyph
        """
        chunks_of_text: typing.List[ChunkOfTextRenderEvent] = []
        x: Decimal = Decimal(0)
        y: Decimal = self._graphics_state.text_rise
        font: typing.Optional[Font] = self._graphics_state.font
        assert font is not None
        for g in self._glyph_line.split():
            e = ChunkOfTextRenderEvent(self._graphics_state, String(" "))
            e.font_size = self.font_size
            e.font_color = self.font_color
            e.font = self.font
            e.text = g.get_text()
            e._space_character_width_estimate = self._space_character_width_estimate
            e._graphics_state = self._graphics_state
            e._glyph_line = g

            # set baseline bounding box
            m = self._graphics_state.text_matrix.mul(self._graphics_state.ctm)
            p0 = m.cross(x, y, Decimal(1))
            p1 = m.cross(
                x + g.get_width_in_text_space(),
                y + font.get_ascent() * Decimal(0.001),
                Decimal(1),
            )
            e.baseline_bounding_box = Rectangle(
                p0[0], p0[1], p1[0] - p0[0], p1[1] - p0[1]
            )
            e.bounding_box = e.baseline_bounding_box

            # change bounding box (descent)
            if g.uses_descent():
                p0 = m.cross(
                    x,
                    y + font.get_descent() * Decimal(0.001),
                    Decimal(1),
                )
                p1 = m.cross(
                    x + g.get_width_in_text_space(),
                    y + font.get_ascent() * Decimal(0.001),
                    Decimal(1),
                )
                e.bounding_box = Rectangle(
                    min(p0[0], p1[0]),
                    min(p0[1], p1[1]),
                    abs(p1[0] - p0[0]),
                    abs(p1[1] - p0[1]),
                )

            # update x
            x += g.get_width_in_text_space()

            # append
            chunks_of_text.append(e)

        return chunks_of_text


class LeftToRightComparator:
    """
    This class offers a comparator on ChunkOfTextRenderEvent objects.
    This comparator favors left-to-right, up-to-down text reading order.
    This corresponds to the expected western language reading order.
    """

    @staticmethod
    def cmp(obj0: ChunkOfTextRenderEvent, obj1: ChunkOfTextRenderEvent):
        """
        This function compares two ChunkOfTextRenderEvent objects
        returning a negative number if obj0 occurs first in the (western) reading order,
        and a positive number otherwise.
        """
        # get baseline
        y0_round = obj0.get_baseline().y
        y0_round = y0_round - y0_round % 5

        # get baseline
        y1_round = obj1.get_baseline().y
        y1_round = y1_round - y1_round % 5

        if y0_round == y1_round:
            return obj0.get_baseline().x - obj1.get_baseline().x
        return -(y0_round - y1_round)
