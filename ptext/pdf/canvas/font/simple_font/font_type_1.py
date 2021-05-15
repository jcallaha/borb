#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A Type 1 font program is a stylized PostScript program that describes glyph shapes. It uses a compact
encoding for the glyph descriptions, and it includes hint information that enables high-quality rendering even at
small sizes and low resolutions.
"""
import logging
import typing
from pathlib import Path

from fontTools.afmLib import AFM  # type: ignore [import]
from fontTools.agl import toUnicode  # type: ignore [import]

from ptext.io.read.types import Decimal as pDecimal
from ptext.io.read.types import Name, Dictionary
from ptext.pdf.canvas.font.adobe_standard_encoding import (
    adobe_standard_decode,
    adobe_standard_encode,
)
from ptext.pdf.canvas.font.font import Font
from ptext.pdf.canvas.font.simple_font.simple_font import SimpleFont
from ptext.pdf.canvas.font.symbol_encoding import (
    symbol_decode,
    zapfdingbats_decode,
)

logger = logging.getLogger(__name__)


class Type1Font(SimpleFont):
    """
    A Type 1 font program is a stylized PostScript program that describes glyph shapes. It uses a compact
    encoding for the glyph descriptions, and it includes hint information that enables high-quality rendering even at
    small sizes and low resolutions.
    """

    def __init__(self):
        super(Type1Font, self).__init__()
        self[Name("Type")] = Name("Font")
        self[Name("Subtype")] = Name("Type1")
        self._character_identifier_to_unicode_lookup: typing.Dict[int, str] = {}
        self._unicode_lookup_to_character_identifier: typing.Dict[str, int] = {}

    def _read_encoding_with_differences(self) -> None:

        # check whether we've been here before
        if len(self._unicode_lookup_to_character_identifier) > 0:
            return

        # figure out how many characters we'll need to calculate
        assert "FirstChar" in self
        assert isinstance(self["FirstChar"], pDecimal)
        assert "LastChar" in self
        assert isinstance(self["LastChar"], pDecimal)
        first_char: int = int(self["FirstChar"])
        last_char: int = int(self["LastChar"])
        self._character_identifier_to_unicode_lookup = {}

        # apply differences
        i: int = 0
        j: int = 0
        while i < len(self["Encoding"]["Differences"]):
            assert isinstance(self["Encoding"]["Differences"][i], pDecimal)
            character_code: int = self["Encoding"]["Differences"][i]
            j = i + 1
            while j < len(self["Encoding"]["Differences"]) and not isinstance(
                self["Encoding"]["Differences"][j], pDecimal
            ):
                glyph_name: str = str(self["Encoding"]["Differences"][j])
                self._character_identifier_to_unicode_lookup[
                    int(character_code)
                ] = toUnicode(glyph_name)
                character_code += 1
                j += 1
            i = j

        # build reverse map
        self._unicode_lookup_to_character_identifier = {
            v: k for k, v in self._character_identifier_to_unicode_lookup.items()
        }

    def _read_to_unicode(self):
        if len(self._unicode_lookup_to_character_identifier) > 0:
            return
        assert "ToUnicode" in self
        assert "DecodedBytes" in self["ToUnicode"]
        cmap_bytes: bytes = self["ToUnicode"]["DecodedBytes"]
        self._character_identifier_to_unicode_lookup = self._read_cmap(cmap_bytes)
        self._unicode_lookup_to_character_identifier: typing.Dict[str, int] = {
            v: k for k, v in self._character_identifier_to_unicode_lookup.items()
        }

    def character_identifier_to_unicode(
        self, character_identifier: int
    ) -> typing.Optional[str]:
        """
        This function maps a character identifier to its unicode str.
        If no such mapping exists, this function returns None.
        """

        # If the font dictionary contains a ToUnicode CMap (see 9.10.3, "ToUnicode CMaps"), use that CMap to
        # convert the character code to Unicode.
        if Name("ToUnicode") in self:
            self._read_to_unicode()
            return self._character_identifier_to_unicode_lookup.get(
                character_identifier
            )

        # if "Encoding" is not present, the implied encoding is StandardEncoding
        if "Encoding" not in self:
            self[Name("Encoding")] = Name("StandardEncoding")

        # If the font is a simple font that uses one of the predefined encodings MacRomanEncoding,
        # MacExpertEncoding, or WinAnsiEncoding,
        if isinstance(self["Encoding"], Name) and self["Encoding"] in [
            "MacRomanEncoding",
            "MacExpertEncoding",
            "WinAnsiEncoding",
            "StandardEncoding",
        ]:
            if character_identifier < 0 or character_identifier > 256:
                return None
            if self["Encoding"] == "WinAnsiEncoding":
                return bytes([character_identifier]).decode("cp1252")
            elif self["Encoding"] == "MacRomanEncoding":
                return bytes([character_identifier]).decode("mac-roman")
            elif self["Encoding"] == "MacExpertEncoding":
                # TODO replace by actual MacExpertEncoding
                logger.debug(
                    "Font %s uses MacExpertEncoding, defaulting to MacRomanEncoding"
                    % str(self["BaseFont"])
                )
                return bytes([character_identifier]).decode("mac-roman")
            elif self["Encoding"] == "StandardEncoding":
                return adobe_standard_decode(bytes([character_identifier]))
            else:
                logger.debug(
                    "Font %s uses unknown encoding %s"
                    % (str(self["BaseFont"]), str(self["Encoding"]))
                )

        # or that has an encoding whose Differences array includes
        # only character names taken from the Adobe standard Latin character set and the set of named characters
        # in the Symbol font (see Annex D)
        # a) Map the character code to a character name according to Table D.1 and the font’s Differences
        # array.
        # b) Look up the character name in the Adobe Glyph List (see the Bibliography) to obtain the
        # corresponding Unicode value.
        if (
            isinstance(self["Encoding"], Dictionary)
            and "BaseEncoding" in self["Encoding"]
            and self["Encoding"]["BaseEncoding"]
            in [
                "MacRomanEncoding",
                "MacExpertEncoding",
                "WinAnsiEncoding",
                "StandardEncoding",
            ]
        ):
            if character_identifier < 0 or character_identifier > 256:
                return None
            self._read_encoding_with_differences()
            return self._character_identifier_to_unicode_lookup.get(
                character_identifier
            )

        # default
        return None

    def unicode_to_character_identifier(self, unicode: str) -> typing.Optional[int]:
        """
        This function maps a unicode str to its character identifier.
        If no such mapping exists, this function returns None.
        """
        if Name("ToUnicode") in self:
            self._read_to_unicode()
            return self._unicode_lookup_to_character_identifier.get(unicode)

        # if "Encoding" is not present, the implied encoding is StandardEncoding
        if "Encoding" not in self:
            self[Name("Encoding")] = Name("StandardEncoding")

        if isinstance(self["Encoding"], Name) and self["Encoding"] in [
            "MacRomanEncoding",
            "MacExpertEncoding",
            "WinAnsiEncoding",
            "StandardEncoding",
        ]:
            try:
                if self["Encoding"] == "WinAnsiEncoding":
                    return int(unicode.encode("cp1252"))
                elif self["Encoding"] == "MacRomanEncoding":
                    return int(unicode.encode("mac-roman"))
                elif self["Encoding"] == "MacExpertEncoding":
                    # TODO replace by actual MacExpertEncoding
                    return int(unicode.encode("mac-roman"))
                elif self["Encoding"] == "StandardEncoding":
                    return int(adobe_standard_encode(unicode))
            except:
                return None

        if (
            isinstance(self["Encoding"], Dictionary)
            and "BaseEncoding" in self["Encoding"]
            and self["Encoding"]["BaseEncoding"]
            in [
                "MacRomanEncoding",
                "MacExpertEncoding",
                "WinAnsiEncoding",
                "StandardEncoding",
            ]
        ):
            self._read_encoding_with_differences()
            return self._unicode_lookup_to_character_identifier.get(unicode, None)

        # default
        return None

    def get_width(self, character_identifier: int) -> typing.Optional[pDecimal]:
        """
        This function returns the width (in text space) of a given character identifier.
        If this Font is unable to represent the glyph that corresponds to the character identifier,
        this function returns None
        """
        first_char: int = int(self["FirstChar"])
        last_char: int = int(self["LastChar"])
        if first_char <= character_identifier <= last_char:
            return self["Widths"][character_identifier - first_char]
        return None

    def get_ascent(self) -> pDecimal:
        """
        This function returns the maximum height above the baseline reached by glyphs in this font.
        The height of glyphs for accented characters shall be excluded.
        """
        return self["FontDescriptor"]["Ascent"]

    def get_descent(self) -> pDecimal:
        """
        This function returns the maximum depth below the baseline reached by glyphs in this font.
        The value shall be a negative number.
        """
        return self["FontDescriptor"]["Descent"]

    def _empty_copy(self) -> "Font":
        return Type1Font()

    def __deepcopy__(self, memodict={}):
        # fmt: off
        f_out: Font = super(Type1Font, self).__deepcopy__(memodict)
        f_out[Name("Subtype")] = Name("Type1")
        f_out._character_identifier_to_unicode_lookup: typing.Dict[int, str] = {k: v for k, v in self._character_identifier_to_unicode_lookup.items()}
        f_out._unicode_lookup_to_character_identifier: typing.Dict[str, int] = {k: v for k, v in self._unicode_lookup_to_character_identifier.items()}
        return f_out
        # fmt: on


class StandardType1Font(Type1Font):
    """
    The PostScript names of 14 Type 1 fonts, known as the standard 14 fonts, are as follows: Times-Roman,
    Helvetica, Courier, Symbol, Times-Bold, Helvetica-Bold, Courier-Bold, ZapfDingbats, Times-Italic, Helvetica-
    Oblique, Courier-Oblique, Times-BoldItalic, Helvetica-BoldOblique, Courier-BoldOblique
    These fonts, or their font metrics and suitable substitution fonts, shall be available to the conforming reader.
    """

    STANDARD_14_FONT_NAMES: typing.List[str] = [
        "Courier",
        "Courier-Bold",
        "Courier-Bold-Oblique",
        "Courier-Oblique",
        "Helvetica",
        "Helvetica-Bold",
        "Helvetica-Bold-Oblique",
        "Helvetica-Oblique",
        "Symbol",
        "Times-Bold",
        "Times-Bold-Italic",
        "Times-Italic",
        "Times-Roman",
        "ZapfDingbats",
    ]

    @staticmethod
    def _canonical_name(font_name: str) -> typing.Optional[str]:
        def _to_lower_and_alpha(x: str) -> str:
            return "".join([c for c in x.lower() if c in "abcdefghijklmnopqrstuvwxyz"])

        canonical_name: str = _to_lower_and_alpha(font_name)
        for n in StandardType1Font.STANDARD_14_FONT_NAMES:
            if _to_lower_and_alpha(n) == canonical_name:
                return n

        return None

    @staticmethod
    def is_standard_14_font_name(font_name: str) -> bool:
        """
        This function returns True if the given str represents the name of one of the standard 14 fonts, False otherwise
        """
        return StandardType1Font._canonical_name(font_name) is not None

    # fmt: off
    def __init__(self, font_name: typing.Optional[str] = None):
        super(StandardType1Font, self).__init__()
        if font_name is not None:

            font_name = StandardType1Font._canonical_name(font_name)
            assert font_name is not None

            # assert whether AFM directory exists
            afm_directory: Path = Path(__file__).parent / "afm"
            assert afm_directory.exists()

            # assert whether AFM file exists
            afm_file: Path = afm_directory / (font_name.lower() + ".afm")
            assert afm_file.exists()

            # build AFM datastructure
            self._afm: AFM = AFM(afm_file)

            self[Name("Type")] = Name("Font")
            self[Name("Subtype")] = Name("Type1")
            self[Name("BaseFont")] = Name(self._afm._attrs["FontName"])

            self._character_identifier_to_unicode_lookup: typing.Dict[int, str] = {}
            self._unicode_lookup_to_character_identifier: typing.Dict[str, int] = {}

            if font_name == "Symbol":
                self._character_identifier_to_unicode_lookup  = {c:symbol_decode([c]) for c in range(0, 256)}
                self._unicode_lookup_to_character_identifier = {v:k for k,v in self._character_identifier_to_unicode_lookup.items()}

            elif font_name == "ZapfDingbats":
                self._character_identifier_to_unicode_lookup = {c:zapfdingbats_decode([c]) for c in range(0, 256)}
                self._unicode_lookup_to_character_identifier = {v:k for k,v in self._character_identifier_to_unicode_lookup.items()}

            else:
                for c in range(0, 256):
                    try:
                        self._character_identifier_to_unicode_lookup[c] = bytes([c]).decode("cp1252")
                    except:
                        self._character_identifier_to_unicode_lookup[c] = ""
                self._unicode_lookup_to_character_identifier = {v:k for k,v in self._character_identifier_to_unicode_lookup.items()}

    # fmt: on

    def character_identifier_to_unicode(
        self, character_identifier: int
    ) -> typing.Optional[str]:
        """
        This function maps a character identifier to its unicode str.
        If no such mapping exists, this function returns None.
        """
        return self._character_identifier_to_unicode_lookup.get(character_identifier)

    def unicode_to_character_identifier(self, unicode: str) -> typing.Optional[int]:
        """
        This function maps a unicode str to its character identifier.
        If no such mapping exists, this function returns None.
        """
        return self._unicode_lookup_to_character_identifier.get(unicode)

    def get_width(self, character_identifier: int) -> typing.Optional[pDecimal]:
        """
        This function returns the width (in text space) of a given character identifier.
        If this Font is unable to represent the glyph that corresponds to the character identifier,
        this function returns None
        """
        widths: typing.List[pDecimal] = [
            pDecimal(v[1])
            for k, v in self._afm._chars.items()
            if v[0] == character_identifier
        ]
        if len(widths) == 1:
            return widths[0]
        return pDecimal(0)

    def get_ascent(self) -> pDecimal:
        """
        This function returns the maximum height above the baseline reached by glyphs in this font.
        The height of glyphs for accented characters shall be excluded.
        """
        if "Ascender" in self._afm._attrs:
            return pDecimal(self._afm._attrs["Ascender"])
        return pDecimal(0)

    def get_descent(self) -> pDecimal:
        """
        This function returns the maximum depth below the baseline reached by glyphs in this font.
        The value shall be a negative number.
        """
        if "Descender" in self._afm._attrs:
            return pDecimal(self._afm._attrs["Descender"])
        return pDecimal(0)

    def _empty_copy(self) -> "Font":
        return StandardType1Font()

    def __deepcopy__(self, memodict={}):
        # fmt: off
        f_out: Font = super(StandardType1Font, self).__deepcopy__(memodict)
        f_out[Name("Subtype")] = Name("Type1")
        f_out._character_identifier_to_unicode_lookup: typing.Dict[int, str] = {k: v for k, v in self._character_identifier_to_unicode_lookup.items()}
        f_out._unicode_lookup_to_character_identifier: typing.Dict[str, int] = {k: v for k, v in self._unicode_lookup_to_character_identifier.items()}
        f_out._afm = self._afm
        return f_out
        # fmt: on
