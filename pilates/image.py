from typing import IO,Dict,Callable

class Image:
    _header: bytes = bytes.fromhex("89504E470D0A1A0A")
    _finished_parsing: bool = False

    def __init__(self):
        print("New image")
    
    """
    Create an image from a png file.

    @param file_path: the path of the png file to be opened
    @return: created Image object
    @raises: ValueError if PNG is not a valid format
    @raises: FileNotFoundError if PNG is not found
        """
    @classmethod
    def fromFile(cls,file_path: str):
        image = cls()
        with open(file_path,"rb") as f:
            found_header = f.read(8)
            # All PNG files have the same header so if this file 
            # doesn't raise a ValueError
            if found_header != image._header:
                raise ValueError("Invalid PNG file.")
            
            # The length at the start of each chunk is 4 bytes,
            # we read it until we cannot anymore
            while (not image._finished_parsing):
                length = f.read(4)
                print(length,int.from_bytes(length))
                image._parse_chunk(f,int.from_bytes(length))

        return image
    
    """
    Parse a single chunk of data.
    @param f: file pointer to the PNG file as a bytes object
    @param length: the length of the chunk
    """
    def _parse_chunk(self,f: IO[bytes],length: int) -> None:
        chunk_types : Dict[bytes,Callable]= {b"IHDR":self._parse_IHDR_chunk,
                                             b"IEND":self._parse_IEND_chunk}
        chunk_type =f.read(4)
        print(chunk_type)

        if not chunk_type:
            raise ValueError("Not a valid chunk.")

        chunk_parsing_fn = chunk_types.get(chunk_type)
        if not chunk_parsing_fn:
            print(f"Chunk ignored {chunk_type}")
            # Data plus the CRC at the end
            f.read(length+4)
        else:
            chunk_parsing_fn(f,length)


    
    """
    Parse the IDR chunk after it has been identified.
    """
    def _parse_IHDR_chunk(self,f: IO[bytes],length : int) -> None:
        # TODO: implement
        width = f.read(4)
        height = f.read(4)
        bit_depth = f.read(1)
        colour_type  = f.read(1)
        compression_method = f.read(1)
        filter_method = f.read(1)
        interlace_method = f.read(1)
        crc = f.read(4)

        print(f"({int.from_bytes(width)}, {int.from_bytes(height)}) bit_depth={bit_depth} colour_type={colour_type}")
        print(f"compression_method={compression_method} filter_method={filter_method} interlace_method={interlace_method}")
    
    
    """
    Parse the IEND chunk and stop further parsing.
    """
    def _parse_IEND_chunk(self,f: IO[bytes],_ : int):
        f.read(4) # For the CRC doesn't strictly matter as we are going to stop parsing anyway
        self._finished_parsing = True



