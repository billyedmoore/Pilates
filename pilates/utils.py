from typing import Tuple
import zlib
import logging

def get_x_bits(x : int, data:bytes) -> Tuple[bytes,bytes]:
    """
    Get the first x bits from data, modify data to remove these bits.

    @return: the first x bits as an int
    @return: the data without the first x bits
    """
    
    if x == 0:
        return b"",data

    elif len(data) == x:
        return data,b""

    elif len(data) == 0 or len(data) < x:
        raise ValueError("Data cannot be empty.")


    # Doing this via strings seems somwhat cursed but its much more easy to 
    # understand than doing binary maths
    bits_as_string = "".join([f"{x:08b}" for x in list(data)])
    x_bits_as_string = bits_as_string[:x]
    data_as_string = bits_as_string[x:]
    x_bits =  int(x_bits_as_string, 2).to_bytes(-(-x // 8))
    # Append 0s so that the length of data_as_string is a multiple of 8
    data_as_string += "0" * ((8 - (len(data_as_string) % 8)) % 8)
        
    data =  bytes([int(data_as_string[i:i+8],2) for i in range(0,len(data_as_string),8)])

    return x_bits,data

def check_crc(body:bytes,found_crc:bytes):
    """
    Check crc, throw error if not correct
    """
    if found_crc != get_crc(body):
        raise ValueError("CRC check failed")
        


def get_crc(body:bytes):
    """
    Get the crc32 for a given body
    """
    return (zlib.crc32(body)% (1<<32)).to_bytes(4)

    
    
