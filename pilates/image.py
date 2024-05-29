from typing import IO,Dict,Callable

class Image:
    _header: bytes = bytes.fromhex("89504E470D0A1A0A")

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
            
            # PNGs have a chunk size of 4-bytes
            while (length := f.read(4)):
                image._parse_chunk(f,int.from_bytes(length))

        return image
    
    """
    Parse a single chunk of data.
    @param f: file pointer to the PNG file as a bytes object
    @param length: the length of the chunk
    """
    def _parse_chunk(self,f: IO[bytes],length: int) -> None:
        chunk_types : Dict[bytes,Callable]= {bytes.fromhex("49484452"):self._parse_IHDR_chunk}

        chunk_type =f.read(4)

        if not chunk_type:
            raise ValueError("Not a valid chunk.")

        chunk_parsing_fn = chunk_types.get(chunk_type)
        if not chunk_parsing_fn:
            print(f"Chunk ignored {chunk_type}")
        else:
            chunk_parsing_fn(f,length)


    
    """
    Parse the IDR chunk after it has been identified.
    """
    def _parse_IHDR_chunk(self,f: IO[bytes],length : int) -> None:
        # TODO: implement
        length -= 4 # as the identifier has already been read

        for i in range(length):
            block = f.read(1)
            if not block:
                raise ValueError("Not a valid IHDR chunk.")
            print(f"{i} : {int.from_bytes(block)}")


