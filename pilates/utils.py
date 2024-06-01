from typing import Tuple

def get_x_bits(x : int, data:bytes) -> Tuple[bytes,bytes]:

    bits_as_string = "".join([f"{x:08b}" for x in list(data)])
    x_bits_as_string = bits_as_string[:x]
    data_as_string = bits_as_string[x:]
    
    x_bits =  int(x_bits_as_string, 2).to_bytes(-(-x // 8))
    data =  bytes([int(data_as_string[i:i+8],2) for i in range(0,len(data_as_string),8)])

    return x_bits,data
    
    
