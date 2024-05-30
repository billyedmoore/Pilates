import zlib 


"""
Decompress the data using DEFLATE as specified in the PNG specification.
Aspirationally would like to write my own version of this.

@param data: the data to be decompressed
@returns: the decompressed data
    """
def inflate(data : bytes) -> bytes:
    decompress = zlib.decompressobj()
    inflated = decompress.decompress(data)
    inflated += decompress.flush()
    return inflated

