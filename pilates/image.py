from collections.abc import Iterable
from copy import deepcopy
from typing import IO, Dict, Callable, List, Literal
from io import BytesIO
import logging

from .compression import deflate, inflate
from .filtering import unfilter
from .utils import check_crc, get_crc, get_x_bits

logging.basicConfig(level=logging.INFO)


class Image:
    _header: bytes = bytes.fromhex("89504E470D0A1A0A")
    _valid_colour_types = [0, 2, 3, 4, 6]
    _number_samples_per_pixel_by_colour_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    _valid_bit_depths_by_colour_type = {0: [1, 2, 4, 8, 16],
                                        2: [8, 16],
                                        3: [1, 2, 4, 8],
                                        4: [8, 16],
                                        6: [8, 16]}

    def __init__(self):
        print("New image")

        # set our defaults
        self._width: int = 0
        self._height: int = 0
        self._bit_depth: int = 0  # 0 is used for not set
        self._colour_type: int = 2
        self._compression_method: int = 0
        self._filter_method: int = 0
        self._interlace_method: int = 0
        self._pixels: List[List[List[int]]] = []
        self._text_attributes: Dict[str, str] = {}
        self._palette: List[Iterable[int]] = []

        # attributes used in parsing
        self._finished_parsing: bool = False
        self._parsed_chunks: List[bytes] = []
        self._IDAT_stream: bytes = b""
        self._pixels_loaded: bool = False

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

    @classmethod
    def new_image(cls, width=1000, height=1000, colour_type: Literal[0, 2, 3, 4, 6] = 2, bit_depth: Literal[1, 2, 4, 8, 16] = 8, background_colour=[255, 105, 180]):
        """
        Create a new blank image with the given colour_type and bit_depth
        """
        # As types are not enforced
        if colour_type not in cls._valid_colour_types:
            raise ValueError("Invalid colour_type specified.")

        if colour_type != 2:
            raise ValueError("Cannot create index based images.")

        if bit_depth not in cls._valid_bit_depths_by_colour_type[colour_type]:
            raise ValueError("Invalid bit_depth specified")

        image = cls()
        image._width = width
        image._height = height
        image._bit_depth = bit_depth
        image._colour_type = colour_type
        image._compression_method = 0
        image._filter_method = 0
        image._interlace_method = 0

        image._log_state()

        if background_colour == None:
            background_colour = [0 for _ in range(
                image.numb_samples_per_pixel)]
        else:
            image._test_pixel(background_colour)

        image._pixels = [
            [background_colour for _ in range(width)]for _ in range(height)]
        image._finished_parsing = True
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

        img_as_bytes = self._header
        img_as_bytes += add_chunk_length_bytes(
            add_crc(self._generate_IHDR_chunk()))
        img_as_bytes += add_chunk_length_bytes(
            add_crc(self._generate_IDAT_chunk()))
        img_as_bytes += add_chunk_length_bytes(
            add_crc(self._generate_IEND_chunk()))

        return img_as_bytes

    def to_file(self, filename: str):
        """
        Save the image as a png at filename

        @param filename: the filename to save to
        @raises FileNotFoundError: if filename isn't valid
        """
        with open(filename, "wb") as f:
            f.write(self.to_bytes())

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

    def _log_state(self):
        """"
        log the state of the image to INFO 
        """
        logging.info(f"Image shape ({self._width},{self._height})")
        logging.info(f"Bit depth {self._bit_depth}")
        logging.info(f"Colour type {self._colour_type}")
        logging.info(f"Compression method {self._compression_method}")
        logging.info(f"Filter method {self._filter_method}")
        logging.info(f"Interlace method {self._interlace_method}")

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

        self._log_state()

        # Confirm that the values are as expected
        if self._interlace_method not in [0, 1]:
            raise ValueError("Invalid interlace method.")
        if self._compression_method != 0:
            raise ValueError("Invalid compression method.")
        if self._colour_type not in self._valid_colour_types:
            raise ValueError("Invalid colour type.")
        # The valid bit_depths by colour_type
        if self._bit_depth not in self._valid_bit_depths_by_colour_type[self._colour_type]:
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
        for _ in range(h):
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

        pixels: List[List[List[int]]] = []
        bits_read = 0

        for row in rows:
            row_pixels: List[List] = []
            for _ in range(w):
                pixel: List[int] = []
                if self._colour_type == 3:
                    val, row = get_x_bits(self.bit_depth, row)
                    bits_read += self.bit_depth
                    val = int.from_bytes(val)
                    try:
                        pixel = list(self._palette[val])
                    except IndexError:
                        raise ValueError("Invalid palette index.")
                else:
                    for _ in range(self.numb_samples_per_pixel):
                        bits_read += self._bit_depth
                        val, row = get_x_bits(self._bit_depth, row)
                        val = int.from_bytes(val)
                        pixel.append(val)
                row_pixels.append(pixel)
            pixels.append(row_pixels)

        # if the image has index based colour we convert it to the equivilent
        # normal version
        if self._colour_type == 3:
            self._colour_type = 2
            self._bit_depth = 8

        self._pixels = pixels

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
                [f"{s:0{self._bit_depth}b}" for s in samples])

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

    def to_grayscale(self) -> None:
        """
        Convert a truecolour image to grayscale. 

        @raises ValueError if the image isn't truecolour.
        """
        if self.colour_type not in [2, 6]:
            raise ValueError(
                "Can only convert truecolour images to grayscale.")

        def int_average(lst: List[int]) -> int:
            return round(sum(lst) / len(lst))

        # truecolour images must have bit_depth = 8 or 16 which
        # is also valid for grayscale so no need to change
        w, h = self.shape
        new_pixels = [[[] for _ in range(w)]for _ in range(h)]
        self._colour_type = 0 if self._colour_type == 2 else 4
        for x in range(w):
            for y in range(h):
                px = self.get_pixel(x, y)
                if self.colour_type == 0:
                    new_pixels[y][x] = [int_average(px)]
                if self.colour_type == 4:
                    new_pixels[y][x] = [int_average(px[:3]), px[-1]]

        self.replace_pixels(new_pixels)

    def to_truecolour(self) -> None:
        """
        Convert a grayscale image to truecolour. 
        Images should look the same but be represented with 3 samples 
        instead of one.

        @raises ValueError if the image isn't grayscale.
        """
        if self.colour_type not in [0, 4]:
            raise ValueError(
                "Can only convert grayscale images to truecolour.")

        # truecolour images must have bit_depth = 8 or 16 which
        # is also valid for grayscale so no need to change
        w, h = self.shape
        new_pixels = [[[] for _ in range(w)]for _ in range(h)]
        self._colour_type = 2 if self._colour_type == 0 else 6
        for x in range(w):
            for y in range(h):
                px = self.get_pixel(x, y)
                if self.colour_type == 2:
                    new_pixels[y][x] = [px[0], px[0], px[0]]
                if self.colour_type == 6:
                    new_pixels[y][x] = [px[0], px[0], px[0], px[1]]

        self.replace_pixels(new_pixels)

    def add_alpha(self) -> None:
        """
        Add an alpha sample to each pixel in a image that doesn't have one.
        The alpha values are all initalised to the max value (not at all transparent).

        @raises value error if the image already has an alpha channel or colour
                is index based.
        """
        if self.colour_type not in [0, 2]:
            raise ValueError(
                "Can only convert grayscale images to truecolour.")

        w, h = self.shape
        new_pixels = [[[] for _ in range(w)]for _ in range(h)]
        self._colour_type = {0: 4, 2: 6}[self.colour_type]

        for x in range(w):
            for y in range(h):
                px = self.get_pixel(x, y)
                new_pixels[y][x] = px + [(2**self.bit_depth)-1]
        self.replace_pixels(new_pixels)

    @property
    def shape(self):
        return (self._width, self._height)

    def get_pixels(self):
        """
        Get a copy of the 2d list of pixels
        """
        if not self._finished_parsing:
            raise ValueError("Cannot get pixels, we haven't finished parsing.")

        return deepcopy(self._pixels)

    def replace_pixels(self, new_pixels: List[List[List]]) -> None:
        """
        Perform some checks to see if the passed new_pixels is valid,
        if it is then set self._pixels to it. Will change the shape of the 
        image if the dimensions of the new pixels don't match the old ones.

        @param a 2d list of pixels 
        @return whether the pixel list has been changed.

        """
        len_prev_row: int | None = None
        for row in new_pixels:
            if len_prev_row != None and len(row) != len_prev_row:
                raise ValueError("Rows of pixels must be of the same length.")
            for px in row:
                self._test_pixel(px)
            len_prev_row = len(row)

        self._width = len(new_pixels[0])
        self._height = len(new_pixels)

        self._pixels = new_pixels

    def _test_pixel(self, pix: List[int]):
        """
        Test if pixel is valid. Raise an error if not.

        @raises ValueError
        """
        if len(pix) != self.numb_samples_per_pixel:
            raise ValueError("Pixel has the incorrect number of samples.")

        for sample in pix:
            if sample.bit_length() > self.bit_depth or sample < 0:
                raise ValueError("Sample is to large to be represented")

    def set_pixel(self, x: int, y: int, pix: List[int]):
        """
        Set the specified pixel to pix if its valid.
        """
        w, h = self.shape
        if x > w or x < 0 or y > h or y < 0:
            raise ValueError("Cannot set pixel out of bounds.")
        self._test_pixel(pix)

        self._pixels[y][x] = pix

    def get_pixel(self, x: int, y: int):
        """
        Get a copy of the pixel at a given coord.
        """
        w, h = self.shape
        if x >= w or y >= h or x < 0 or y < 0:
            raise IndexError(
                f"Cannot get pixel ({x},{y}) from image of size ({w},{h}).")

        return self._pixels[y][x].copy()

    @property
    def _pixel_size_in_bits(self):
        return self._bit_depth * self.numb_samples_per_pixel

    @property
    def numb_samples_per_pixel(self):
        return self._number_samples_per_pixel_by_colour_type[self.colour_type]

    @property
    def bit_depth(self):
        return self._bit_depth

    @property
    def colour_type(self):
        return self._colour_type

    def set_bit_depth(self, new_bit_depth: int):
        """
        Change the bit depth of the image. Raises a value error if the specified value 
        isn't valid for the current image. Results in a loss of colour depth if 
        the specified bit_depth is less than the original bit depth. 

        @param new_bit_depth: The new bit depth to be specified one of 1,2,4,8,16. 
        @raises ValueError: If the value isn't valid for the colour type. 
        """
        if new_bit_depth not in self._valid_bit_depths_by_colour_type[self.colour_type]:
            ValueError(f"Given bit depth {
                       new_bit_depth} is'nt valid for colour type {self.colour_type}")

        new_max = (2**new_bit_depth)-1
        old_max = (2**self.bit_depth)-1

        old_bit_depth = self.bit_depth

        self._bit_depth = new_bit_depth
        w, h = self.shape
        for y in range(h):
            for x in range(w):
                pixel = self.get_pixel(x, y)
                new_pixel = []
                for i in range(len(pixel)):
                    # scale to new range
                    new_pixel.append(int((pixel[i] / old_max)*new_max))
                self.set_pixel(x, y, new_pixel)
        logging.info(f"Changed the bit_depth from {
                     old_bit_depth} to {new_bit_depth}")

    def apply_transform(self, transform):
        """
        Apply a given transform to the image.
        """
        # this is imported here due to circular import
        from .transforms import Transform

        if not isinstance(transform, Transform):
            raise ValueError(
                "Cannot apply tranform as it doesn't deride from Transform.")
        transform.apply(self)
