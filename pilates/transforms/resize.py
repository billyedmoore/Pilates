import math
from typing import List

from .transform import Transform
from ..image import Image


class Resize(Transform):

    def __init__(self, new_w: int, new_h: int):
        self._new_w = new_w
        self._new_h = new_h

    def apply(self, img: Image):
        """
        Apply resize using bi-linear sampling.
        """

        def list_mul(lst: List[float] | List[int], x: float) -> List[float] | List[int]:
            new_lst = []
            for e in lst:
                new_lst.append(e*x)

            return new_lst

        def list_add(lst1: List[float] | List[int], lst2: List[float] | List[int], lst3: List[float] | List[int], lst4: List[float] | List[int]) -> List[int]:
            """
            Add each element of each list. ie lst1[i]+lst2[i]+... Convert the result to an 
            int 
            """
            if not (len(lst1) == len(lst2)) or not (len(lst2) == len(lst3)) or not (len(lst3) == len(lst4)):
                raise ValueError(
                    "To add the values of the lists they must be of the same length.")
            new_lst = []
            for i in range(len(lst1)):
                e = sum([lst1[i], lst2[i], lst3[i], lst4[i]])
                e = min(round(e), 2**img.bit_depth)
                new_lst.append(e)
            return new_lst

        w, h = img.shape
        new_w, new_h = self.new_shape
        resized_pixels = [[[] for _ in range(new_w)] for _ in range(new_h)]

        x_ratio = (w-1)/(new_w-1) if new_w > 1 else 0
        y_ratio = (h-1)/(new_h-1) if new_h > 1 else 0

        for new_x in range(new_w):
            for new_y in range(new_h):
                x1 = min(math.floor(x_ratio * new_x), w-1)
                y1 = min(math.floor(y_ratio*new_y), h-1)
                x2 = min(math.ceil(x_ratio * new_x), w-1)
                y2 = min(math.ceil(y_ratio*new_y), h-1)
                # print(f"x {new_x} y {new_y} x1 {x1} x2 {x2} y1 {y1} y2 {y2}")

                x_weight = (x_ratio * new_x) - x1
                y_weight = (y_ratio * new_y) - y1

                a = img.get_pixel(x1, y1)
                b = img.get_pixel(x2, y1)
                c = img.get_pixel(x1, y2)
                d = img.get_pixel(x2, y2)

                pixel = list_add(list_mul(a, (1-x_weight)*(1-y_weight)),
                                 list_mul(b, x_weight*(1-y_weight)),
                                 list_mul(c, y_weight*(1-x_weight)),
                                 list_mul(d, x_weight*y_weight))

                resized_pixels[new_y][new_x] = pixel

        img.replace_pixels(resized_pixels)

        print("Resized")

    @property
    def new_shape(self):
        return self._new_w, self._new_h

    @new_shape.setter
    def new_shape(self, w: int, h: int):
        self._new_w = w
        self._new_h = h
