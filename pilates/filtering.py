from io import BytesIO
from typing import Dict, Callable, List

"""
Unfilter a series of rows in place.

@param rows: 
@param filter_types: the filter type of each row, must be of the same length as rows
"""
def unfilter(rows: List[bytes], filter_types: List[int]):
    filter_functions: Dict[int, Callable] = {0: lambda *_ : None,
                                             1: reverse_filter_1}
    if len(rows) != len(filter_types):
        raise ValueError("Incorrect number of filter types supplied.")

    for i,ft in enumerate(filter_types):
        if ft not in [0, 1, 2, 3, 4]:
            raise ValueError(f"Invalid filter type {ft} specified.")
        defiltering_fn = filter_functions.get(ft)
        if defiltering_fn:
            defiltering_fn(rows,i)
        else:
            raise NotImplementedError(f"Filter type {ft} not implemented.")



"""
Updates the list rows to unfilter the row rows[index]. Updates the rows 
list inplace.

@param rows: The rows as a list of bytes or length image height
@param index: The row to operate on
"""

def reverse_filter_1(rows: List[bytes], index: int) -> None:
    row = rows[index]
    row_reader = BytesIO(row)
    unfiltered_row: bytes = b""
    a_val = 0
    for _ in range(len(row)):
        x_val = row_reader.read(1)
        new_x_val = int.from_bytes(x_val)+a_val
        unfiltered_row += new_x_val.to_bytes(5)
        a_val = new_x_val
    rows[index] = unfiltered_row


