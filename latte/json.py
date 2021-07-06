from orjson import (
    loads,
    dumps,
    dumps as dumps_binary,
    JSONDecodeError,
    JSONEncodeError
)
import orjson as json
dumps_string = lambda x: str(dumps_binary(x), 'utf-8')