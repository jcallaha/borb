import types
import unittest
from decimal import Decimal

import requests
from PIL import Image as PILImage  # type: ignore [import]

from ptext.io.read.types import (
    Dictionary,
    Name,
    Reference,
    Boolean,
    List,
    add_base_methods,
)


class TestHashTypes(unittest.TestCase):
    def test_hash_types(self):

        obj0 = Dictionary()
        obj0[Name("Root")] = Reference(object_number=10)
        obj0[Name("Marked")] = Boolean(True)

        obj1 = List()
        obj1.append(Name("Red"))
        obj1.append(Decimal(0.5))

        print(hash(obj1))
