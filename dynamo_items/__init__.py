import os
from types import UnionType
from typing import Type, Union, get_args, get_origin

import boto3
from pydantic import BaseModel

AllowedPrimaryKeyTypes = Union[str, int, float, bytes]


def is_optional(field) -> bool:
    return get_origin(field) in (Union, UnionType) and type(None) in get_args(field)


class Key(BaseModel):
    attr: str
    prefix: bool = True
    prefix_value: str = None
    seperator: str = "#"


class GSI(BaseModel):
    pk: Key
    sk: Key = None
    name: str = None


class Table:
    """Represents a DynamoDB Table.
    ItemTypes are associated to a Table object.
    A table can be created based upon the ItemTypes that have been associated.
    GSI key types are defined by items. The required GSIs will be derived from the aggragte ItemTypes.
    Key prefix mappings are stored within the Table
    """

    def __init__(
        self,
        name: str,
        partition_key: Type[AllowedPrimaryKeyTypes] = str,
        sort_key: Type[AllowedPrimaryKeyTypes] = None,
        make_default: bool = False,
        session: boto3.Session = None,
    ) -> None:
        self.name = name

        self.partition_key_type = partition_key
        self.sort_key_type = sort_key

        self.key_prefixes: dict[str, str] = dict()
        self._key_prefix_names: set[str] = set()

        self.gsis = list()

        self.dynamodb = (
            session.resource("dynamodb").Table(name)
            if session
            else boto3.resource("dynamodb").Table(name)
        )

        if make_default:
            global _DEFAULT_TABLE
            _DEFAULT_TABLE = self

    def get_prefix(self, item: str, attr: str) -> str:
        try:
            return self.key_prefixes[f"{item}.{attr}"]
        except KeyError:
            prefix = item[0].upper()
            for c in attr:
                prefix += c.upper()
                if prefix not in self._key_prefix_names:
                    self._key_prefix_names.add(prefix)
                    self.key_prefixes[f"{item}.{attr}"] = prefix
                    return prefix

    def add_gsi(self, gsi=GSI, exclude: list[GSI] = None):
        pass


_DEFAULT_TABLE: Table = None


def get_default_table() -> Table:
    global _DEFAULT_TABLE
    if not _DEFAULT_TABLE:
        _DEFAULT_TABLE = Table(name=os.getenv("DYDB_TABLE_NAME", "dynamo-items"))
    return _DEFAULT_TABLE


class Item:
    """Represents an item in a DynamoDB table.

    :param pk: (optional) The definition for the partition key. If this argument is not provided the
        first field of the ``item_model`` is assumed to be the partition key.
    """

    def __init__(
        self,
        item_model: Type[BaseModel],
        pk: Key = None,
        sk: Key = None,
        gsi: list[GSI] = None,
        table: Table = None,
    ) -> None:
        self._table = table if table else get_default_table()

        if pk is None:
            pk = Key(attr=tuple(item_model.model_fields.keys())[0])

        if pk.attr not in item_model.model_fields:
            raise AttributeError(f"The item model does not have the attribute '{pk.attr}'")

        if is_optional(item_model.model_fields[pk.attr].annotation):
            raise TypeError(f"The attribute '{pk.attr}' cannot be optional when used as a key")

        if sk is not None:
            if sk.attr not in item_model.model_fields:
                raise AttributeError(f"The item model does not have the attribute '{sk.attr}'")

            if is_optional(item_model.model_fields[sk.attr].annotation):
                raise TypeError(f"The attribute '{sk.attr}' cannot be optional when used as a key")

        if pk.prefix is True and self._table.partition_key_type is not str:
            raise ValueError("The item 'pk' uses a prefix but 'pk' for the table is not a 'str'")

        if sk is not None and sk.prefix is True and self._table.sort_key_type is not str:
            raise ValueError("The item 'sk' uses a prefix but 'sk' for the table is not a 'str'")

        if pk.prefix_value is None:
            pk.prefix_value = self._table.get_prefix(item_model.__name__, pk.attr)

        if sk is not None and sk.prefix_value is None:
            sk.prefix_value = self._table.get_prefix(item_model.__name__, sk.attr)

        self.pk: Key = pk
        self.sk: Union[Key, None] = sk

        self.item_model = item_model

    def _key_value(self, key: Key, value):
        if key.prefix:
            return f"{key.prefix_value}{key.seperator}{value}"
        else:
            return self._table.partition_key_type(value)

    def put_item(self, item: BaseModel):
        base_item = {"pk": self._key_value(self.pk, getattr(item, self.pk.attr))}
        if self.sk is None and self._table.sort_key_type is not None:
            base_item["sk"] = "A"
        elif self.sk is not None:
            base_item["sk"] = self._key_value(self.sk, getattr(item, self.sk.attr))
        base_item.update(item.model_dump(mode="json"))
        print(base_item)
        resp = self._table.dynamodb.put_item(Item=base_item)
        print(resp)

    def get_item(self, pk: AllowedPrimaryKeyTypes, sk: AllowedPrimaryKeyTypes = None):
        key = {"pk": self._key_value(self.pk, pk)}
        if sk is None and self._table.sort_key_type is not None:
            key["sk"] = "A"
        elif sk is not None:
            key["sk"] = self._key_value(self.sk, sk)
        print(key)
        resp = self._table.dynamodb.get_item(Key=key)
        print(resp)
        return self.item_model.model_validate(resp.get("Item", {}))
