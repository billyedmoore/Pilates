from typing import IO, Dict, Callable, List, Tuple
from io import BytesIO


from .compression import inflate
from .filtering import unfilter
from .utils import get_x_bits


class Image:
    _header: bytes = bytes.fromhex("89504E470D0A1A0A")
    _finished_parsing: bool = False
    _parsed_IHDR: bool = False
    _text_attributes: Dict[str, str] = {}

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
                                              b"IDAT": self._parse_IDAT_chunk,
                                              b"tEXt": self._parse_tEXt_chunk}
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

    def _parse_tEXt_chunk(self, f: IO[bytes], length: int) -> None:
        """
        Parse a single chunk of type tEXt and store the attributes.

        @param f: file pointer to the PNG file as a bytes object
        @param length: the length of the chunk
        """
        key = b""
        value = b""

        data = f.read(length)

        seen_null = False

        for char in list(data):
            if not seen_null and char:
                key += (char.to_bytes(1))
            elif not char:
                seen_null = True
            elif seen_null:
                value += char.to_bytes(1)

        self._text_attributes[key.decode("utf-8")] = value.decode("utf-8")
        _ = f.read(4)

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

        samples_per_pixel_by_colour_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}

        self._numb_samples_per_pixel = samples_per_pixel_by_colour_type[self._colour_type]
        self._sample_depth_in_bits = self._bit_depth if self._colour_type != 3 else 8
        self._pixel_size_in_bits = self._sample_depth_in_bits * self._numb_samples_per_pixel

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

        compressed_data: bytes = (f.read(length))
        rows = self._decompress_and_defilter(compressed_data)
        self._parse_raw_image_data(rows)

        _ = f.read(4)

    def _decompress_and_defilter(self, data: bytes) -> List[bytes]:
        """
        Decompress and defilter the data.

        @param data: the data from the chunk
        @return: a list of rows of bytes representing the image, each row is of len(self.shape[0]).
        """

        w, h = self.shape
        decompressed_data: bytes = inflate(data)
        decompressed_reader: IO[bytes] = BytesIO(decompressed_data)

        rows = []
        filter_types = []

        number_bytes_read = 0
        for _ in range(h):
            filtering_type = decompressed_reader.read(1)
            number_bytes_read += 1
            filter_types.append(int.from_bytes(filtering_type))

            number_of_bytes_in_row: int = -(-(self._pixel_size_in_bits * w)//8)

            filtered_row: bytes = decompressed_reader.read(
                number_of_bytes_in_row)
            number_bytes_read += number_of_bytes_in_row

            rows.append(filtered_row)
        print(rows)
        unfilter(rows, filter_types)
        print(rows)
        return rows

    def _parse_raw_image_data(self, rows: List[bytes]) -> None:
        """
        Parse the raw image data for a piticular image update the attributes 
        of the image

        @param rows: the rows of the image as a list of bytes arrays
        """
        w, h = self.shape

        if self._colour_type == 3:
            raise NotImplementedError("Index based colouring is not yet implemented")
        pixels : List[List[Tuple[int]]] = []
        for row in rows:
            row_pixels :List[Tuple] = []
            for _ in range(w):
                pixel: List[int] = []
                for _ in range(self._numb_samples_per_pixel):
                    val,row = get_x_bits(self._sample_depth_in_bits,row)
                    val = int.from_bytes(val)

                    pixel.append(val)
                row_pixels.append(tuple(pixel))
            pixels.append(row_pixels)
        self._pixels = pixels
        print(pixels)

    def _parse_IEND_chunk(self, f: IO[bytes], _):
        """
        Parse the IEND chunk and stop further parsing.

        @param f: file pointer to the PNG file as a bytes object
        @param length: the length of the chunk
        """
        # For the CRC doesn't strictly matter as we are going to stop parsing anyway
        _ = f.read(4)
        self._finished_parsing = True

    @property
    def shape(self):
        return (self._width, self._height)
