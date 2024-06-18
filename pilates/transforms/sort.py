from .transform import Transform
from ..image import Image


class SortPixels(Transform):

    def __init__(self, reverse: bool = False):
        self._reverse = reverse

    def apply(self, img: Image):
        pixels = img.get_pixels()
        flat_pixels = sum(pixels, [])
        flat_pixels = sorted(flat_pixels, key=lambda ls: sum(
            ls[:3]), reverse=self._reverse)

        w, h = img.shape
        i = 0
        for y in range(h):
            for x in range(w):
                img.set_pixel(x, y, flat_pixels[i])
                i += 1
