import zlib 


def inflate(data : bytes) -> bytes:
    """
    Decompress the data using DEFLATE as specified in the PNG specification.
    Aspirationally would like to write my own version of this.
    
    @param data: the data to be decompressed
    @returns: the decompressed data
        """
    decompress = zlib.decompressobj()
    inflated = decompress.decompress(data)
    inflated += decompress.flush()
    return inflated

def deflate(data: bytes) -> bytes:
    """
    Compress the data using DEFLATE as specified in the PNG specification.
    Aspirationally would like to write my own version of this.
    
    @param data: the data to be decompressed
    @returns: the compressed data
        """
    compress = zlib.compressobj()
    deflated = compress.compress(data)
    deflated += compress.flush()
    return deflated


