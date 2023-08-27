# dynamo-items

Experimental Python module for DynamoDB inspired by `aws-sdk-ruby-record`.

DynamoDB item types are defined as `Pydantic` models. Those models are associated to a single table with key prefixes generated and reserved for the different items and their keys.

In `aws-sdk-ruby-record` that package wraps around the AWS SDK for Ruby. The current approach in this package is more opinionated and wrapping the DynamoDB resource operations may not be suited to the same.

This may never become an actual package, but it does serve as a playground for ideas around using Pydantic models with DynamoDB.

### Simple Usage

```python
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel

from dynamo_items import Item

class Statuses(Enum):
    pending = "pending"
    failed = "failed"
    complete = "complete"


class Command(BaseModel):
    command_id: UUID
    status: Statuses = Statuses.pending
    retry: int = 0


# The first field in the Pydantic model is assumed to be the partition key.
# Because this item does not have a sort key, the default table associated with the item will only have a string partition key.
commands = Item(item_model=Command)

new_command = Command(command_id=uuid4())

# Create a new item in the table using the model.
commands.put_item(new_command)

# Get items by passing their primary key. This returns a Pydantic model.
commands.get_item(pk="aaf0637a-6221-4bbb-bf6d-edc4c04a6118")
```

Key prefixes for different items are dynamically created.

```json
{
  "pk": {
    "S": "CC#aaf0637a-6221-4bbb-bf6d-edc4c04a6118"
  },
  "command_id": {
    "S": "aaf0637a-6221-4bbb-bf6d-edc4c04a6118"
  },
  "retry": {
    "N": "0"
  },
  "status": {
    "S": "pending"
  }
}
```

### Multiple Items and Item Collections

Create a `Table` object (optionally setting as the default for all new items) to configure the `pk` and `sk`.

```python
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from dynamo_items import Item, Key, Table


class Statuses(Enum):
    pending = "pending"
    failed = "failed"
    complete = "complete"


class Command(BaseModel):
    command_id: UUID
    status: Statuses = Statuses.pending
    retry: int = 0


# This new version of the command item uses `command_id` as a sort key.
class CommandV2(BaseModel):
    device_id: UUID
    command_id: UUID
    status: Statuses = Statuses.pending
    retry: int = 0


class CommandV2Log(BaseModel):
    device_id: UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    log: str

    
# Pass the types for the partition and sort keys.
items_table = Table(
    name="dynamo-items-2",
    partition_key=str,
    sort_key=str,
    make_default=True
)

# Item order determines key prefixes. Items that are always defined in the same order will be assigned the same prefixes on the same table.
commands = Item(item_model=Command)

# Because the table `commands` is associated to here has a sort key, but the item does not, it will default to using the value "A".

# The `Key` object configures the `pk` and `sk` attributes for an item.
# The `attr` tells the item which field to use for the key's value.
commands_v2 = Item(
    item_model=CommandV2,
    pk=Key(attr="device_id"),
    sk=Key(attr="command_id")
)

# This additional commands V2 item adopts the prefix calculated for the parent item.
commands_v2_logs = Item(
    item_model=CommandV2Log,
    pk=Key(attr="device_id", prefix_value=commands_v2.pk.prefix_value),
    sk=Key(attr="timestamp")
)

# These calls will create an item collection.
device_id = uuid4()

commands_v2.put_item(CommandV2(device_id=device_id, command_id=uuid4()))

commands_v2_logs.put_item(
    CommandV2Log(device_id=device_id, log="Something happened!")
)
```

Here is the DynamoDB JSON for the command V2 items created.

```json
{
  "pk": {
    "S": "CD#3939ba91-7687-4df4-8ed3-db531a66f989"
  },
  "sk": {
    "S": "CCO#186a3ca1-f1df-4975-a9dd-39f11015b4a1"
  },
  "command_id": {
    "S": "186a3ca1-f1df-4975-a9dd-39f11015b4a1"
  },
  "device_id": {
    "S": "3939ba91-7687-4df4-8ed3-db531a66f989"
  },
  "retry": {
    "N": "0"
  },
  "status": {
    "S": "pending"
  }
}
```

```json
{
  "pk": {
    "S": "CD#3939ba91-7687-4df4-8ed3-db531a66f989"
  },
  "sk": {
    "S": "CT#2023-08-27 01:10:36.357227"
  },
  "device_id": {
    "S": "3939ba91-7687-4df4-8ed3-db531a66f989"
  },
  "log": {
    "S": "Something happened!"
  },
  "timestamp": {
    "S": "2023-08-27T01:10:36.357227"
  }
}
```
