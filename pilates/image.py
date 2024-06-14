from os import ST_APPEND
from typing import IO, Dict, Callable, List, Tuple
from io import BytesIO
import logging

from .compression import deflate, inflate
from .filtering import unfilter
from .utils import bytes_to_binary_string, check_crc, get_crc, get_x_bits

logging.basicConfig(level=logging.INFO)


class Image:
    _header: bytes = bytes.fromhex("89504E470D0A1A0A")
    _finished_parsing: bool = False
    _parsed_chunks: List[bytes] = []
    _text_attributes: Dict[str, str] = {}
    _palette: List[Tuple[int, int, int]] = []
    _IDAT_stream: bytes = b""
    _pixels: List = []
    _pixels_loaded: bool = False

    def __init__(self):
        print("New image")

    @classmethod
    def from_file(cls, file_path: str):
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

    def to_bytes(self) -> bytes:
        """
        Convert the image to a bytes object that can be saved as a png
        """
        def add_chunk_length_bytes(byts: bytes):
            """
            Add the length byte to a chunk
            """
            length = len(byts) - 8  # the chunk-type field is 4 bytes
            if length < 0:
                raise ValueError("Invalid chunk generated.")
            byts = length.to_bytes(4) + byts
            return byts

        def add_crc(byts: bytes):
            return byts + get_crc(byts)

        if not self._pixels:
            raise ValueError("Cannot conver to bytes as IDAT data not parsed.")

        # If the image currently has a palette we don't respect that
        # and use colour type 2 instead.
        if self._colour_type == 3:
            self._colour_type = 2
            self._bit_depth = 8
            self._sample_depth_in_bits = 8

        img_as_bytes = self._header
        img_as_bytes += add_chunk_length_bytes(
            add_crc(self._generate_IHDR_chunk()))
        img_as_bytes += add_chunk_length_bytes(
            add_crc(self._generate_IDAT_chunk()))
        img_as_bytes += add_chunk_length_bytes(
            add_crc(self._generate_IEND_chunk()))

        return img_as_bytes

    def _parse_chunk(self, f: IO[bytes], length: int) -> None:
        """
        Parse a single chunk of data.
        @param f: file pointer to the PNG file as a bytes object
        @param length: the length of the chunk
        """
        chunk_types: Dict[bytes, Callable] = {b"IHDR": self._parse_IHDR_chunk,
                                              b"IEND": self._parse_IEND_chunk,
                                              b"IDAT": self._parse_IDAT_chunk,
                                              b"tEXt": self._parse_tEXt_chunk,
                                              b"PLTE": self._parse_PLTE_chunk}
        chunk_type = f.read(4)
        if not chunk_type:
            raise ValueError("Not a valid chunk.")

        chunk_parsing_fn = chunk_types.get(chunk_type)
        if not chunk_parsing_fn:
            logging.warning(f"Chunk ignored {chunk_type}")
            # Data plus the CRC at the end
            f.read(length+4)
        else:
            logging.info(f"Parsing {chunk_type}")
            chunk_parsing_fn(f, length)
            self._parsed_chunks.append(chunk_type)

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

        crc = f.read(4)
        check_crc(b"IHDR"+width+height+bit_depth+colour_type +
                  compression_method+filter_method+interlace_method, crc)

        self._width = int.from_bytes(width)
        self._height = int.from_bytes(height)
        self._bit_depth = int.from_bytes(bit_depth)
        self._colour_type = int.from_bytes(colour_type)
        self._compression_method = int.from_bytes(compression_method)
        self._filter_method = int.from_bytes(filter_method)
        self._interlace_method = int.from_bytes(interlace_method)

        samples_per_pixel_by_colour_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}

        self._numb_samples_per_pixel = samples_per_pixel_by_colour_type[self._colour_type]
        self._sample_depth_in_bits = self._bit_depth
        self._pixel_size_in_bits = self._sample_depth_in_bits * self._numb_samples_per_pixel

        logging.info(f"Image shape ({self._width},{self._height})")
        logging.info(f"Bit depth {self._bit_depth}")
        logging.info(f"Colour type {self._colour_type}")
        logging.info(f"Compression method {self._compression_method}")
        logging.info(f"Filter method {self._filter_method}")
        logging.info(f"Interlace method {self._interlace_method}")

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

        if self._interlace_method == 1:
            raise NotImplementedError("Interlace method 1 is not implemented.")

    def _parse_PLTE_chunk(self, f: IO[bytes], length: int) -> None:
        """
        Parse a single chunk of type PLTE get the palette store it as a dict.

        @param f: file pointer to the PNG file as a bytes object
        @param length: the length of the chunk
        """
        palette: bytes = f.read(length)
        crc: bytes = f.read(4)
        check_crc(b"PLTE"+palette, crc)

        # We are only gonna use the PLTE if colour_type is 3
        if self._colour_type != 3:
            return

        palette_as_list = list(palette)
        for i in range(0, length, 3):
            self._palette += [(palette_as_list[i],
                               palette_as_list[i+1],
                               palette_as_list[i+2])]

    def _parse_IDAT_chunk(self, f: IO[bytes], length: int) -> None:
        """
        Parse a single chunk of type IDAT get the data and store it somehow.

        @param f: file pointer to the PNG file as a bytes object
        @param length: the length of the chunk
        """
        if b"IHDR" not in self._parsed_chunks:
            raise ValueError("IDAT chunk must be preceded by a IHDR chunk.")

        if self._colour_type == 3 and b"PLTE" not in self._parsed_chunks:
            raise ValueError("IDAT chunk must be preceded by a PLTE \
                             chunk for colour type 3.")

        compressed_data: bytes = (f.read(length))
        crc = f.read(4)

        check_crc(b"IDAT" + compressed_data, crc)

        self._IDAT_stream += compressed_data

    def _defilter(self, data: bytes) -> List[bytes]:
        """
        Decompress and defilter the data.

        @param data: the data from the chunk
        @return: a list of rows of bytes representing the image, each row is of len(self.shape[0]).
        """

        w, h = self.shape
        decompressed_reader: IO[bytes] = BytesIO(data)

        rows = []
        filter_types = []

        number_bytes_read = 0
        for i in range(h):
            filtering_type = decompressed_reader.read(1)
            number_bytes_read += 1
            filter_types.append(int.from_bytes(filtering_type))

            number_of_bytes_in_row: int = -(-(self._pixel_size_in_bits*w)//8)

            filtered_row: bytes = decompressed_reader.read(
                number_of_bytes_in_row)
            number_bytes_read += number_of_bytes_in_row

            rows.append(filtered_row)

        unfilter(rows, filter_types, -(-self._pixel_size_in_bits//8))
        logging.info(f"Filter types {filter_types}")
        return rows

    def _parse_raw_image_data(self, rows: List[bytes]) -> None:
        """
        Parse the raw image data for a piticular image update the attributes 
        of the image

        @param rows: the rows of the image as a list of bytes arrays
        """
        w, h = self.shape
        print(w, h)

        pixels: List[List[Tuple[int]]] = []
        bits_read = 0

        for row in rows:
            row_pixels: List[Tuple] = []
            for _ in range(w):
                pixel: List[int] = []
                if self._colour_type == 3:
                    val, row = get_x_bits(self._sample_depth_in_bits, row)
                    bits_read += self._sample_depth_in_bits
                    val = int.from_bytes(val)
                    try:
                        pixel = list(self._palette[val])
                    except IndexError:
                        raise ValueError("Invalid palette index.")
                else:
                    for _ in range(self._numb_samples_per_pixel):
                        bits_read += self._sample_depth_in_bits
                        val, row = get_x_bits(self._sample_depth_in_bits, row)
                        val = int.from_bytes(val)
                        pixel.append(val)
                row_pixels.append(tuple(pixel))
            pixels.append(row_pixels)
        self._pixels = pixels
        # For debugging
        if 0:
            for row in pixels:
                print()
                print(row[0:10])
                print(row[10:20])
                print(row[20:30])
                print(row[30:])
                print()

    def _parse_IEND_chunk(self, f: IO[bytes], _):
        """
        Parse the IEND chunk and stop further parsing.

        @param f: file pointer to the PNG file as a bytes object
        @param length: the length of the chunk
        """
        print("Decompressed")
        decompressed_data: bytes = inflate(self._IDAT_stream)
        rows = self._defilter(decompressed_data)
        self._parse_raw_image_data(rows)
        print("Parsed")

        # For the CRC doesn't strictly matter as we are going to stop parsing anyway
        _ = f.read(4)
        self._finished_parsing = True

    def _generate_IHDR_chunk(self) -> bytes:
        """
        Generate the IHDR chunk as a bytes, doesn't include the size.
        """
        chunk: bytes = b"IHDR"

        chunk += self._width.to_bytes(4)
        chunk += self._height.to_bytes(4)

        chunk += self._bit_depth.to_bytes(1)
        chunk += self._colour_type.to_bytes(1)

        chunk += int(0).to_bytes(1)  # Compression method (only 0 is supported)
        chunk += int(0).to_bytes(1)  # Filter method (only 0 is supported)
        # Interlace method (we won't apply any interlacing)
        chunk += int(0).to_bytes(1)

        return chunk

    def _generate_IDAT_chunk(self) -> bytes:
        """
        Generate the IDAT chunk as a bytes, doesn't include the size.
        """
        chunk: bytes = b""
        logging.info(f"Found pixels in shape ({
                     len(self._pixels[0])},{len(self._pixels)})")

        for pix_row in self._pixels:
            # TODO: Add support for other filtering methods we only apply no filter here
            row: bytes = int(0).to_bytes(1)
            samples = []
            for pix in pix_row:
                for sample in pix:
                    samples.append(sample)

            str_row = "".join(
                [f"{s:0{self._sample_depth_in_bits}b}" for s in samples])

            # If len(str_row) is not devisible by 8 then pad with 0s
            str_row += "0" * ((8 - (len(str_row) % 8)) % 8)

            row += bytes([int(str_row[i:i+8], 2)
                         for i in range(0, len(str_row), 8)])

            chunk += row

        chunk = b"IDAT" + deflate(chunk)
        return chunk

    def _generate_IEND_chunk(self) -> bytes:
        """
        Generate the IEND chunk as a bytes, doesn't include the size.
        """
        return b"IEND"

    @property
    def shape(self):
        return (self._width, self._height)
    
    def get_pixels(self):
        """
        Get a copy of the 2d list of pixels
        """
        if self._finished_parsing:
            return self._pixels.copy()
        else:
            return []

    def set_pixels(self,new_pixels: List[List[Tuple]]) -> bool:
        """
        Perform some checks to see if the passed new_pixels is valid,
        if it is then set self._pixels to it.
        
        @param a 2d list of pixels 
        @return whether the pixel list has been changed.
        
        """
        w,h = self.shape
        if len(new_pixels) != h:
            return False

        for row in new_pixels:
            if len(row) != w:
                return False
            for px in row:
                if len(px) != self._numb_samples_per_pixel:
                    return False
                for sample in px:
                    if not isinstance(sample,int):
                        return False
                    if sample.bit_length() > self._sample_depth_in_bits:
                        return False
        
        return True




