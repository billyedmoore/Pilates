from typing import Tuple
import zlib
import logging

def get_x_bits(x: int, data: bytes) -> Tuple[bytes, bytes]:
    """
    Get the first x bits from data, return the modified data without the bits

    @return: the first x bits as an int
    @return: the data without the first x bits
    """
    if x == 0:
        return b"", data

    elif len(data)*8 == x:
        return data, b""

    elif len(data) == 0 or len(data)*8 < x:
        raise ValueError(f"Cannot get more bits than are in data, data is {
                         len(data)*8} bits and x is {x}.")

 
    x_len: int = -(-x//8)
    overhang: int = x % 8

    x_bytes = data[:x_len]

    if overhang:
        mask = (0xFF >> overhang) ^ 0xFF
        x_bytes = bytearray(x_bytes[:-1] + ((x_bytes[-1] & mask)).to_bytes(1,"big"))
        x_bytes[-1] = (x_bytes[-1] >> (8-overhang)) % 256
        x_bytes = bytes(x_bytes)
        modified_data = bytearray((data[x_len-1]).to_bytes(1) + data[x_len:])

        for i in range(0,len(modified_data)-1):
            modified_data[i] = (modified_data[i] << (overhang)) % 256
            modified_data[i] = (modified_data[i]) | (((modified_data[i+1] & mask) >> (8-overhang) ) % 256)

        modified_data[-1] = (modified_data[-1] << (overhang)) % 256
        modified_data = bytes(modified_data) 
    else:
        modified_data = data[x_len:]

    return x_bytes, modified_data

def check_crc(body: bytes, found_crc: bytes):
    """
    Check crc, throw error if not correct
    """
    if found_crc != get_crc(body):
        raise ValueError("CRC check failed")


def get_crc(body: bytes):
    """
    Get the crc32 for a given body
    """
    return (zlib.crc32(body) % (1 << 32)).to_bytes(4)


def bytes_to_binary_string(byts: bytes):
    return "".join([f"{x:08b}" for x in list(byts)])
