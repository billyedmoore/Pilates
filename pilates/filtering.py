"""
Unapply (and in the future apply) filters to images. 

Refer to the spec: https://www.w3.org/TR/png/#9Filters

pixels are refered do by there relative position from a pixel x:
```
c b 
a x
```

"""

from io import BytesIO
from typing import Dict, Callable, List


def unfilter(rows: List[bytes], filter_types: List[int]):
    """
    Unfilter a series of rows in place.

    @param rows: 
    @param filter_types: the filter type of each row, must be of the same length as rows
    """
    filter_functions: Dict[int, Callable] = {0: lambda *_: None,
                                             1: reverse_filter_1,
                                             2: reverse_filter_2,
                                             3: reverse_filter_3,
                                             4: reverse_filter_4}
    if len(rows) != len(filter_types):
        raise ValueError("Incorrect number of filter types supplied.")

    for i, ft in enumerate(filter_types):
        if ft not in [0, 1, 2, 3, 4]:
            raise ValueError(f"Invalid filter type {ft} specified.")
        defiltering_fn = filter_functions.get(ft)
        if defiltering_fn:
            defiltering_fn(rows, i)
        else:
            raise NotImplementedError(f"Filter type {ft} not implemented.")


def reverse_filter_1(rows: List[bytes], index: int) -> None:
    """
    Updates the list rows to unfilter the row rows[index]. Updates the rows 
    list inplace.

    @param rows: The rows as a list of bytes or length image height
    @param index: The row to operate on
    """
    row = list(rows[index])

    unfiltered_row: bytes = b""
    for i in range(len(row)):
        x_val = row[i]
        a_val = row[i-1] if i != 0 else 0

        unfiltered_row += ((x_val+a_val) % 256).to_bytes(1)
    rows[index] = unfiltered_row


def reverse_filter_2(rows: List[bytes], index: int) -> None:
    """
    Updates the list rows to unfilter the row rows[index]. Updates the rows 
    list inplace. Relies on the fact the previous list should have already
    been unfiltered

    @param rows: The rows as a list of bytes or length image height
    @param index: The row to operate on
    """
    row = list(rows[index])
    above_row = [0 for _ in range(len(row))]
    if index > 0:
        above_row = list(rows[index-1])

    unfiltered_row: bytes = b""
    for i in range(len(row)):
        x_val = row[i]
        b_val = above_row[i]
        new_x_val = x_val+b_val
        unfiltered_row += (new_x_val % 256).to_bytes(1)
    rows[index] = unfiltered_row


def reverse_filter_3(rows: List[bytes], index: int) -> None:
    """
    Updates the list rows to unfilter the row rows[index]. Updates the rows 
    list inplace.

    @param rows: The rows as a list of bytes or length image height
    @param index: The row to operate on
    """
    row = rows[index]
    row_reader = BytesIO(row)
    unfiltered_row: bytes = b""
    a_val = 0
    for i in range(len(row)):
        b_val = int.from_bytes(bytes(rows[index-1][i]))
        x_val = row_reader.read(1)
        new_x_val = int.from_bytes(x_val)+(a_val+b_val//2)
        unfiltered_row += (new_x_val % 256).to_bytes(1)
        a_val = new_x_val
    rows[index] = unfiltered_row


def reverse_filter_4(rows: List[bytes], index: int) -> None:
    """
    Updates the list rows to unfilter the row rows[index]. Updates the rows 
    list inplace.

    @param rows: The rows as a list of bytes or length image height
    @param index: The row to operate on
    """
    row = list(rows[index])
    above_row = [0 for _ in range(len(row))]
    if index > 0:
        above_row = list(rows[index-1])

    unfiltered_row: bytes = b""
    for i in range(len(row)):
        a_val = row[i-1] if i != 0 else 0
        b_val = above_row[i]
        c_val = above_row[i-1] if i != 0 else 0

        x_val = row[i]

        pa = abs(x_val - a_val)
        pb = abs(x_val - b_val)
        pc = abs(x_val - c_val)

        if pa <= pb and pa <= pc:
            new_x_val = a_val
        elif pb <= pc:
            new_x_val = b_val
        else:
            new_x_val = c_val

        unfiltered_row += (new_x_val % 256).to_bytes(1)
    rows[index] = unfiltered_row
