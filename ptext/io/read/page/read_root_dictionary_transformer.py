#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    This implementation of ReadBaseTransformer is responsible for reading the \Catalog object
"""
import io
import typing
from typing import Optional, List, Any, Union, Dict

from ptext.io.read.object.read_dictionary_transformer import (
    ReadDictionaryTransformer,
)
from ptext.io.read.read_base_transformer import (
    ReadBaseTransformer,
    ReadTransformerContext,
)
from ptext.io.read.types import (
    Dictionary,
    AnyPDFType,
    Decimal,
    Name,
)
from ptext.io.read.types import List as pList
from ptext.pdf.canvas.event.event_listener import EventListener
from ptext.pdf.page.page import Page


class ReadRootDictionaryTransformer(ReadBaseTransformer):
    """
    This implementation of ReadBaseTransformer is responsible for reading the \Catalog object
    """

    def can_be_transformed(
        self, object: Union[io.BufferedIOBase, io.RawIOBase, io.BytesIO, AnyPDFType]
    ) -> bool:
        """
        This function returns True if the object to be converted represents a \Catalog Dictionary
        """
        return (
            isinstance(object, Dict)
            and "Type" in object
            and object["Type"] == "Catalog"
        )

    def transform(
        self,
        object_to_transform: Union[io.BufferedIOBase, io.RawIOBase, AnyPDFType],
        parent_object: Any,
        context: Optional[ReadTransformerContext] = None,
        event_listeners: typing.List[EventListener] = [],
    ) -> Any:
        """
        This function reads a \Catalog Dictionary from a byte stream
        """
        assert isinstance(object_to_transform, Dictionary)

        # add listener(s)
        for l in event_listeners:
            object_to_transform.add_event_listener(l)  # type: ignore [attr-defined]

        # convert using Dictionary transformer
        transformed_root_dictionary: Optional[Dictionary] = None
        for t in self.get_root_transformer().children:
            if isinstance(t, ReadDictionaryTransformer):
                transformed_root_dictionary = t.transform(
                    object_to_transform, parent_object, context, []
                )
                break

        assert transformed_root_dictionary is not None
        assert isinstance(transformed_root_dictionary, Dictionary)

        #
        # rebuild /Pages if needed
        #

        # list to hold Page objects (in order)
        pages_in_order: typing.List[Page] = []

        # stack to explore Page(s) DFS
        stack_to_handle: typing.List[AnyPDFType] = []
        stack_to_handle.append(transformed_root_dictionary["Pages"])

        # DFS
        while len(stack_to_handle) > 0:
            obj = stack_to_handle.pop(0)
            if isinstance(obj, Page):
                pages_in_order.append(obj)
            # \Pages
            if (
                isinstance(obj, Dictionary)
                and "Type" in obj
                and obj["Type"] == "Pages"
                and "Kids" in obj
                and isinstance(obj["Kids"], List)
            ):
                for k in obj["Kids"]:
                    stack_to_handle.append(k)

        # change
        transformed_root_dictionary["Pages"][Name("Kids")] = pList()
        for p in pages_in_order:
            transformed_root_dictionary["Pages"]["Kids"].append(p)
        transformed_root_dictionary["Pages"][Name("Count")] = Decimal(
            len(pages_in_order)
        )

        # return
        return transformed_root_dictionary
