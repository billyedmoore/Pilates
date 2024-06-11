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


def unfilter(rows: List[bytes], filter_types: List[int], pixel_size: int):
    """
    Unfilter a series of rows in place.

    @param rows: 
    @param pixel_size: the number of bytes in each pixel
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
            defiltering_fn(rows, i, pixel_size)
        else:
            raise NotImplementedError(f"Filter type {ft} not implemented.")


def reverse_filter_1(rows: List[bytes], index: int, px_size: int) -> None:
    """
    Updates the list rows to unfilter the row rows[index]. Updates the rows 
    list inplace.

    @param rows: The rows as a list of bytes or length image height
    @param index: The row to operate on
    """
    row = list(rows[index])

    for i in range(0, len(row), px_size):
        x_val = row[i:i+px_size]
        a_val = row[i-px_size:i] if i - \
            px_size >= 0 else [0 for _ in range(px_size)]

        for j in range(px_size):
            row[i+j] = (x_val[j] + a_val[j]) % 256

    rows[index] = bytes(row)


def reverse_filter_2(rows: List[bytes], index: int, px_size: int) -> None:
    """
    Updates the list rows to unfilter the row rows[index]. Updates the rows 
    list inplace. Relies on the fact the previous list should have already
    been unfiltered

    @param rows: The rows as a list of bytes or length image height
    @param index: The row to operate on
    """
    row = list(rows[index])
    above_row = list(
        rows[index-1]) if index > 0 else [0 for _ in range(len(row))]

    for i in range(0, len(row), px_size):
        x_val = row[i:i+px_size]
        b_val = above_row[i:i+px_size]

        for j in range(px_size):
            row[i+j] = (x_val[j] + b_val[j]) % 256

    rows[index] = bytes(row)


def reverse_filter_3(rows: List[bytes], index: int, px_size: int) -> None:
    """
    Updates the list rows to unfilter the row rows[index]. Updates the rows 
    list inplace.

    @param rows: The rows as a list of bytes or length image height
    @param index: The row to operate on
    """
    row = list(rows[index])
    above_row = list(
        rows[index-1]) if index > 0 else [0 for _ in range(len(row))]

    for i in range(0, len(row), px_size):
        x_val = row[i:i+px_size]
        b_val = above_row[i:i+px_size]
        a_val = row[i-px_size:i] if i - \
            px_size >= 0 else [0 for _ in range(px_size)]

        for j in range(px_size):
            row[i+j] = (x_val[j] + ((a_val[j] + b_val[j])//2)) % 256
    rows[index] = bytes(row)


def reverse_filter_4(rows: List[bytes], index: int, px_size: int) -> None:
    """
    Updates the list rows to unfilter the row rows[index]. Updates the rows 
    list inplace.

    @param rows: The rows as a list of bytes or length image height
    @param index: The row to operate on
    """
    row = list(rows[index])
    above_row = list(
        rows[index-1]) if index > 0 else [0 for _ in range(len(row))]

    for i in range(0, len(row), px_size):
        x_val = row[i:i+px_size]
        b_val = above_row[i:i+px_size]
        a_val = row[i-px_size:i] if i - \
            px_size >= 0 else [0 for _ in range(px_size)]
        c_val = above_row[i-px_size:i] if i - \
            px_size >= 0 else [0 for _ in range(px_size)]

        for j in range(px_size):
            row[i+j] = (x_val[j] + paeth_predictor(a_val[j],
                        b_val[j], c_val[j])) % 256
    rows[index] = bytes(row)


def paeth_predictor(a_val, b_val, c_val):

    p = a_val+b_val-c_val

    pa = abs(p-a_val)
    pb = abs(p-b_val)
    pc = abs(p-c_val)

    if pa <= pb and pa <= pc:
        return a_val
    elif pb <= pc:
        return b_val
    else:
        return c_val
