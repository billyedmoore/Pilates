from typing import IO, Dict, Callable
from io import BytesIO

from .compression import inflate
from .filtering import unfilter


class Image:
    _header: bytes = bytes.fromhex("89504E470D0A1A0A")
    _finished_parsing: bool = False
    _parsed_IHDR: bool = False

    def __init__(self):
        print("New image")

    @classmethod
    def fromFile(cls, file_path: str):
        """
        Create an image from a png file.

        @param file_path: the path of the png file to be opened
        @return: created Image object
        @raises: ValueError if PNG is not a valid format
        @raises: FileNotFoundError if PNG is not found
            """
        image = cls()
        with open(file_path, "rb") as f:
            found_header = f.read(8)
            # All PNG files have the same header so if this file
            # doesn't raise a ValueError
            if found_header != image._header:
                raise ValueError("Invalid PNG file.")

            # The length at the start of each chunk is 4 bytes,
            # we read it and parse the chunk untill we cannot anymore
            while (not image._finished_parsing):
                length = f.read(4)
                image._parse_chunk(f, int.from_bytes(length))

        return image


    def _parse_chunk(self, f: IO[bytes], length: int) -> None:
        """
        Parse a single chunk of data.
        @param f: file pointer to the PNG file as a bytes object
        @param length: the length of the chunk
        """
        chunk_types: Dict[bytes, Callable] = {b"IHDR": self._parse_IHDR_chunk,
                                              b"IEND": self._parse_IEND_chunk,
                                              b"IDAT": self._parse_IDAT_chunk}
        chunk_type = f.read(4)
        if not chunk_type:
            raise ValueError("Not a valid chunk.")

        chunk_parsing_fn = chunk_types.get(chunk_type)
        if not chunk_parsing_fn:
            print(f"Chunk ignored {chunk_type}")
            # Data plus the CRC at the end
            f.read(length+4)
        else:
            chunk_parsing_fn(f, length)


    def _parse_IHDR_chunk(self, f: IO[bytes], _: int) -> None:
        """
        Parse a single chunk of type IHDR and store the attributes.

        @param f: file pointer to the PNG file as a bytes object
        @param length: the length of the chunk
        """
        width = f.read(4)
        height = f.read(4)
        bit_depth = f.read(1)
        colour_type = f.read(1)
        compression_method = f.read(1)
        filter_method = f.read(1)
        interlace_method = f.read(1)
        f.read(4)

        # TODO: validate these values
        self._width = int.from_bytes(width)
        self._height = int.from_bytes(height)
        self._bit_depth = int.from_bytes(bit_depth)
        self._colour_type = int.from_bytes(colour_type)
        self._compression_method = int.from_bytes(compression_method)
        self._filter_method = int.from_bytes(filter_method)
        self._interlace_method = int.from_bytes(interlace_method)

        # Confirm that the values are as expected
        if self._interlace_method not in [0, 1]:
            raise ValueError("Invalid interlace method.")
        if self._compression_method != 0:
            raise ValueError("Invalid compression method.")
        if self._colour_type not in [0, 2, 3, 4, 6]:
            raise ValueError("Invalid colour type.")
        # The valid bit_depths by colour_type
        valid_bit_depths = {0: [1, 2, 4, 8, 16],
                            2: [8, 16],
                            3: [1, 2, 4, 8],
                            4: [8, 16],
                            6: [8, 16]}
        if self._bit_depth not in valid_bit_depths[self._colour_type]:
            raise ValueError("Invalid bit depth.")
        if self._width < (2**31)-1 and self._width < 0:
            raise ValueError("Invalid width.")
        if self._height < (2**31)-1 and self._height < 0:
            raise ValueError("Invalid height.")

        self._parsed_IHDR = True


    def _parse_IDAT_chunk(self, f: IO[bytes], length: int) -> None:
        """
        Parse a single chunk of type IDAT get the data and store it somehow.

        @param f: file pointer to the PNG file as a bytes object
        @param length: the length of the chunk
        """
        if not self._parsed_IHDR:
            raise ValueError("IDAT chunk must be preceded by a IHDR chunk.")

        w, h = self.shape

        samples_per_pixel_by_colour_type = {0:1,2:3,3:1,4:2,6:4}


        samples_per_pixel = samples_per_pixel_by_colour_type[self._colour_type]
        sample_depth_in_bits = self._bit_depth if self._colour_type != 3 else 8
        pixel_size_in_bits = sample_depth_in_bits * samples_per_pixel 
        pixel_size_in_bytes = -(-pixel_size_in_bits//8)
            
        compressed_data: bytes = (f.read(length))
        decompressed_data: bytes = inflate(compressed_data)
        decompressed_reader: IO[bytes] = BytesIO(decompressed_data)

        rows = []
        filter_types = []
        
        number_bytes_read = 0
        for _ in range(h):
            filtering_type = decompressed_reader.read(1)
            number_bytes_read += 1
            filter_types.append(int.from_bytes(filtering_type))
            
            number_of_bytes_in_row : int = pixel_size_in_bytes * w

            filtered_row: bytes = decompressed_reader.read(
                number_of_bytes_in_row)
            number_bytes_read += number_of_bytes_in_row

            rows.append(filtered_row)
        unfilter(rows, filter_types)

        _ = f.read(4)

    """
    Parse the IEND chunk and stop further parsing.

    @param f: file pointer to the PNG file as a bytes object
    @param length: the length of the chunk
    """

    def _parse_IEND_chunk(self, f: IO[bytes], _):
        # For the CRC doesn't strictly matter as we are going to stop parsing anyway
        _ = f.read(4)
        self._finished_parsing = True

    @property
    def shape(self):
        return (self._width, self._height)
