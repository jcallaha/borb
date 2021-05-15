#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    This class is the base implementation of a transformer pattern.
    It reads bytes from a PDF document, and converts it to JSON-like datastructures.
"""
import io
import typing
from typing import Optional

from ptext.io.read.types import AnyPDFType, Reference


class WriteTransformerContext:
    """
    This class represents all the meta-information used in the process of persisting a PDF document.
    This includes:
    - the root object (the Document itself)
    - a cache of indirect objects (by id and hash)
    - references that have been resolved (to avoid endless loops)
    - the default compression level
    - etc
    """

    def __init__(
        self,
        destination: Optional[typing.Union[io.BufferedIOBase, io.RawIOBase]] = None,
        root_object: Optional[AnyPDFType] = None,
    ):
        self.destination = (
            destination  # this is the destination to write to (file, byte-buffer, etc)
        )
        self.root_object: Optional[
            AnyPDFType
        ] = root_object  # this is the root object (PDF)
        self.indirect_objects_by_id: typing.Dict[int, AnyPDFType] = {}
        self.indirect_objects_by_hash: typing.Dict[
            int, typing.List[AnyPDFType]
        ] = {}  # these are all the indirect objects
        self.resolved_references: typing.List[
            Reference
        ] = []  # these references have already been written
        self.compression_level = 9


class WriteBaseTransformer:
    """
    <<<<<<< HEAD
        This class represents the base transformer for persisting a PDF Document.
        It allows you to add child BaseWriteTransformer implementations to handle specific cases,
        such as persisting Image objects, or Dictionary objects, etc.
    =======
        This class is the base implementation of a transformer pattern.
        It reads bytes from a PDF document, and converts it to JSON-like datastructures.
    >>>>>>> feature/font-improvements
    """

    def __init__(self):
        self.handlers = []
        self.parent = None

    def add_child_transformer(
        self, handler: "WriteBaseTransformer"  # type: ignore [name-defined]
    ) -> "WriteBaseTransformer":  # type: ignore [name-defined]
        """
        <<<<<<< HEAD
                This function allows you to add BaseWriteTransformer implementations to handle specific
                cases, such as a BaseWriteTransformer specifically designed to persist Image objects.
        =======
                This function adds a BaseWriteTransformer to this WriteBaseTransformer.
                Children of this WriteBaseTransformer will be called in turn, and their
                `can_be_transformed` method should return True if the child WriteBaseTransformer
                can handle the object to be transformed. The first child to return True will have its
                `transform` method called.
        >>>>>>> feature/font-improvements
                This function returns self.
        """
        self.handlers.append(handler)
        handler.parent = self
        return self

    def get_root_transformer(self) -> "WriteBaseTransformer":  # type: ignore [name-defined]
        """
        <<<<<<< HEAD
                This function returns the WriteBaseTransformer at the root of this WriteBaseTransformer hierarchy.
                This allows child WriteBaseTransformer implementations to call the root transformer.
                This is useful for instance when transforming a dictionary, where each key/value would then be transformed
                by delegating the call to the root WriteBaseTransformer.
        =======
                This function gets the root WriteBaseTransformer of this WriteBaseTransformer.
                WriteBaseTransformer implementations can be nested to allow a facade design pattern.
        >>>>>>> feature/font-improvements
        """
        p = self
        while p.parent is not None:
            p = p.parent
        return p

    def can_be_transformed(self, any: AnyPDFType):
        """
        This function returns True if this WriteBaseTransformer can transform the input object,
        false otherwise
        """
        return False

    def transform(
        self,
        object_to_transform: AnyPDFType,
        context: Optional[WriteTransformerContext] = None,
    ):
        """
        This method writes an object (of type AnyPDFType) to a byte stream (specified in the WriteTransformerContext)
        """
        # transform object
        return_value = None
        for h in self.handlers:
            if h.can_be_transformed(object_to_transform):
                return_value = h.transform(
                    object_to_transform,
                    context=context,
                )
                break

        # return
        return return_value

    def _start_object(
        self,
        object_to_transform: AnyPDFType,
        context: Optional[WriteTransformerContext],
    ):
        """
        This function starts a new direct object by writing
        its reference number followed by "obj" (e.g. "12 0 obj").
        It also does some bookkeeping to ensure the byte offset is stored in the XREF
        """
        # get offset position
        assert context is not None
        assert context.destination is not None
        byte_offset = context.destination.tell()

        # update offset
        ref = object_to_transform.get_reference()  # type: ignore [union-attr]
        assert ref is not None
        assert isinstance(ref, Reference)
        ref.byte_offset = byte_offset

        # write <object number> <generation number> obj
        assert ref.object_number is not None
        context.destination.write(
            bytes(
                "%d %d obj\n" % (ref.object_number, ref.generation_number or 0),
                "latin1",
            )
        )

    def _end_object(
        self,
        object_to_transform: AnyPDFType,
        context: Optional[WriteTransformerContext],
    ):
        """
        This function writes the "endobj" bytes whenever a direct object needs to be closed
        """
        # write endobj
        assert context is not None
        assert context.destination is not None
        context.destination.write(bytes("endobj\n\n", "latin1"))

    @staticmethod
    def _hash(obj: typing.Any) -> int:
        h: Optional[int] = None
        # hash
        try:
            h = hash(obj)
        except:
            pass
        # __hash__
        try:
            h = obj.__hash__()
        except:
            pass
        if h is None:
            raise TypeError("unhashable type: %s" % obj.__class__.__name__)
        return h

    def get_reference(
        self, object: AnyPDFType, context: WriteTransformerContext
    ) -> Reference:
        """
        This function builds a Reference for the input object
        References are re-used whenever possible (hashing is used to detect duplicate objects)
        """
        obj_id = id(object)
        if obj_id in context.indirect_objects_by_id:
            cached_indirect_object: AnyPDFType = context.indirect_objects_by_id[obj_id]
            assert not isinstance(cached_indirect_object, Reference)
            return cached_indirect_object.get_reference()  # type: ignore [union-attr]

        # look through existing indirect object hashes
        obj_hash: int = self._hash(object)
        if obj_hash in context.indirect_objects_by_hash:
            for obj in context.indirect_objects_by_hash[obj_hash]:
                if obj == object:
                    ref = obj.get_reference()  # type: ignore [union-attr]
                    assert ref is not None
                    assert isinstance(ref, Reference)
                    object.set_reference(ref)  # type: ignore [union-attr]
                    return ref

        # generate new object number
        existing_obj_numbers = set(
            [
                item.get_reference().object_number  # type: ignore [union-attr]
                for sublist in [v for k, v in context.indirect_objects_by_hash.items()]
                for item in sublist
            ]
        )
        obj_number = len(existing_obj_numbers) + 1
        while obj_number in existing_obj_numbers:  # type: ignore [union-attr]
            obj_number += 1

        # build reference
        ref = Reference(object_number=obj_number)
        object.set_reference(ref)  # type: ignore [union-attr]

        # insert into context.indirect_objects_by_hash
        if obj_hash in context.indirect_objects_by_hash:
            context.indirect_objects_by_hash[obj_hash].append(object)
        else:
            context.indirect_objects_by_hash[obj_hash] = [object]

        # insert into context.indirect_objects_by_id
        context.indirect_objects_by_id[obj_id] = object

        # return
        return ref
