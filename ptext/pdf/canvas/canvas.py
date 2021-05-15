#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    In computer science and visualization, a canvas is a container that holds various drawing elements
    (lines, shapes, text, frames containing other elements, etc.).
    It takes its name from the canvas used in visual arts.
"""
import io
import logging
import os
import time
import typing

from ptext.io.read.tokenize.high_level_tokenizer import HighLevelTokenizer
from ptext.io.read.types import (
    Dictionary,
    CanvasOperatorName,
)
from ptext.pdf.canvas.canvas_graphics_state import CanvasGraphicsState
from ptext.pdf.canvas.operator.color.set_cmyk_non_stroking import SetCMYKNonStroking
from ptext.pdf.canvas.operator.color.set_cmyk_stroking import SetCMYKStroking
from ptext.pdf.canvas.operator.color.set_color_non_stroking import (
    SetColorNonStroking,
)
from ptext.pdf.canvas.operator.color.set_color_stroking import SetColorStroking
from ptext.pdf.canvas.operator.color.set_gray_non_stroking import SetGrayNonStroking
from ptext.pdf.canvas.operator.color.set_gray_stroking import SetGrayStroking
from ptext.pdf.canvas.operator.color.set_rgb_non_stroking import SetRGBNonStroking
from ptext.pdf.canvas.operator.color.set_rgb_stroking import SetRGBStroking
from ptext.pdf.canvas.operator.compatibility.begin_compatibility_section import (
    BeginCompatibilitySection,
)
from ptext.pdf.canvas.operator.compatibility.end_compatibility_section import (
    EndCompatibilitySection,
)
from ptext.pdf.canvas.operator.marked_content.begin_marked_content import (
    BeginMarkedContent,
)
from ptext.pdf.canvas.operator.marked_content.begin_marked_content_with_property_list import (
    BeginMarkedContentWithPropertyList,
)
from ptext.pdf.canvas.operator.marked_content.end_marked_content import (
    EndMarkedContent,
)
from ptext.pdf.canvas.operator.path_construction.append_cubic_bezier import (
    AppendCubicBezierCurve1,
    AppendCubicBezierCurve2,
    AppendCubicBezierCurve3,
)
from ptext.pdf.canvas.operator.path_construction.append_line_segment import (
    AppendLineSegment,
)
from ptext.pdf.canvas.operator.path_construction.begin_subpath import BeginSubpath
from ptext.pdf.canvas.operator.path_construction.close_subpath import CloseSubpath
from ptext.pdf.canvas.operator.path_painting.close_and_stroke_path import (
    CloseAndStrokePath,
)
from ptext.pdf.canvas.operator.path_painting.stroke_path import StrokePath
from ptext.pdf.canvas.operator.state.modify_transformation_matrix import (
    ModifyTransformationMatrix,
)
from ptext.pdf.canvas.operator.state.pop_graphics_state import PopGraphicsState
from ptext.pdf.canvas.operator.state.push_graphics_state import PushGraphicsState
from ptext.pdf.canvas.operator.state.set_line_width import SetLineWidth
from ptext.pdf.canvas.operator.text.begin_text import BeginTextObject
from ptext.pdf.canvas.operator.text.end_text import EndTextObject
from ptext.pdf.canvas.operator.text.move_text_position import MoveTextPosition
from ptext.pdf.canvas.operator.text.move_text_position_set_leading import (
    MoveTextPositionSetLeading,
)
from ptext.pdf.canvas.operator.text.move_to_next_line import MoveToNextLine
from ptext.pdf.canvas.operator.text.move_to_next_line_show_text import (
    MoveToNextLineShowText,
)
from ptext.pdf.canvas.operator.text.set_character_spacing import SetCharacterSpacing
from ptext.pdf.canvas.operator.text.set_font_and_size import SetFontAndSize
from ptext.pdf.canvas.operator.text.set_horizontal_text_scaling import (
    SetHorizontalScaling,
)
from ptext.pdf.canvas.operator.text.set_spacing_move_to_next_line_show_text import (
    SetSpacingMoveToNextLineShowText,
)
from ptext.pdf.canvas.operator.text.set_text_leading import SetTextLeading
from ptext.pdf.canvas.operator.text.set_text_matrix import SetTextMatrix
from ptext.pdf.canvas.operator.text.set_text_rendering_mode import (
    SetTextRenderingMode,
)
from ptext.pdf.canvas.operator.text.set_text_rise import SetTextRise
from ptext.pdf.canvas.operator.text.set_word_spacing import SetWordSpacing
from ptext.pdf.canvas.operator.text.show_text import ShowText
from ptext.pdf.canvas.operator.text.show_text_with_glyph_positioning import (
    ShowTextWithGlyphPositioning,
)
from ptext.pdf.canvas.operator.xobject.do import Do

logger = logging.getLogger(__name__)


class Canvas(Dictionary):
    """
    In computer science and visualization, a canvas is a container that holds various drawing elements
    (lines, shapes, text, frames containing other elements, etc.).
    It takes its name from the canvas used in visual arts.
    """

    def __init__(self):
        super(Canvas, self).__init__()
        # initialize operators
        self.canvas_operators = {
            x.get_text(): x
            for x in [
                # color
                SetCMYKNonStroking(),
                SetCMYKStroking(),
                SetColorNonStroking(self),
                SetColorStroking(self),
                SetGrayNonStroking(),
                SetGrayStroking(),
                SetRGBNonStroking(),
                SetRGBStroking(),
                # compatibility
                BeginCompatibilitySection(),
                EndCompatibilitySection(),
                # marked content
                BeginMarkedContent(),
                BeginMarkedContentWithPropertyList(),
                EndMarkedContent(),
                # path construction
                AppendCubicBezierCurve1(),
                AppendCubicBezierCurve2(),
                AppendCubicBezierCurve3(),
                AppendLineSegment(),
                BeginSubpath(),
                CloseSubpath(),
                # path painting
                CloseAndStrokePath(),
                StrokePath(),
                # state
                ModifyTransformationMatrix(),
                PopGraphicsState(),
                PushGraphicsState(),
                SetLineWidth(),
                # text
                BeginTextObject(),
                EndTextObject(),
                MoveTextPosition(),
                MoveTextPositionSetLeading(),
                MoveToNextLineShowText(),
                MoveToNextLine(),
                SetCharacterSpacing(),
                SetFontAndSize(),
                SetHorizontalScaling(),
                SetSpacingMoveToNextLineShowText(),
                SetTextLeading(),
                SetTextMatrix(),
                SetTextRenderingMode(),
                SetTextRise(),
                SetWordSpacing(),
                ShowText(),
                ShowTextWithGlyphPositioning(),
                # xobject
                Do(),
            ]
        }

        # compatibility mode
        self.in_compatibility_section = False
        # set initial graphics state
        self.graphics_state = CanvasGraphicsState()
        # canvas tag hierarchy is (oddly enough) not considered to be part of the graphics state
        self.marked_content_stack = []
        # set graphics state stack
        self.graphics_state_stack = []

    def get_operator(self, name: str) -> typing.Optional["CanvasOperator"]:
        """
        This function returns the CanvasOperator matching the given operator-name.
        This allows operator re-use between different implementations of Canvas
        """
        return self.canvas_operators.get(name)

    def read(self, io_source: io.IOBase) -> "Canvas":
        """
        This method reads a byte stream of canvas operators, and processes them, returning this Canvas afterwards
        """
        io_source.seek(0, os.SEEK_END)
        length = io_source.tell()
        io_source.seek(0)

        canvas_tokenizer = HighLevelTokenizer(io_source)

        # process content
        operand_stk = []
        instruction_number: int = 0
        time_per_operator: typing.Dict[str, float] = {}
        calls_per_operator: typing.Dict[str, int] = {}
        while canvas_tokenizer.tell() != length:

            # print("<canvas pos='%d' length='%d' percentage='%d'/>" % ( canvas_tokenizer.tell(), length, int(canvas_tokenizer.tell() * 100 / length)))

            # attempt to read object
            obj = canvas_tokenizer.read_object()
            if obj is None:
                break

            # push argument onto stack
            if not isinstance(obj, CanvasOperatorName):
                operand_stk.append(obj)
                continue

            # process operator
            instruction_number += 1
            operator = self.canvas_operators.get(obj, None)
            if operator is None:
                logger.debug("Missing operator %s" % obj)
                continue

            if not self.in_compatibility_section:
                assert len(operand_stk) >= operator.get_number_of_operands()
            operands: typing.List["CanvasOperator"] = []  # type: ignore [name-defined]
            for _ in range(0, operator.get_number_of_operands()):
                operands.insert(0, operand_stk.pop(-1))

            # debug
            operand_str = str([str(x) for x in operands])
            if len(operands) == 1 and isinstance(operands[0], list):
                operand_str = str([str(x) for x in operands[0]])

            logger.debug("%d %s %s" % (instruction_number, operator.text, operand_str))

            # invoke
            try:
                on: str = operator.get_text()
                if on not in time_per_operator:
                    time_per_operator[on] = 0
                if on not in calls_per_operator:
                    calls_per_operator[on] = 1
                else:
                    calls_per_operator[on] += 1
                delta: float = time.time()
                operator.invoke(self, operands)
                delta = time.time() - delta
                time_per_operator[on] += delta
            except Exception as e:
                if not self.in_compatibility_section:
                    raise e

        # for k,v in time_per_operator.items():
        #    print("operator: %s, cumulative_time: %f, number_of_calls: %d, average_time: %f" % (k, v, calls_per_operator[k], v / calls_per_operator[k]))

        # return
        return self
