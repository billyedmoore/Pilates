from .transform import Transform
from ..image import Image


class Invert(Transform):

    def apply(self, img: Image):
        """
        Apply an Invert on the image, pixel by pixel. For each sample
        new_val = max_val - new_val. Alpha samples are left as they are.
        """
        pix_max_val = (2**img.bit_depth) - 1

        w, h = img.shape
        for y in range(h):
            for x in range(w):
                pix = img.get_pixel(x, y)
                relevant_sample_count = min([len(pix), 3])
                for i in range(relevant_sample_count):
                    pix[i] = (pix_max_val - pix[i]) % pix_max_val
                img.set_pixel(x, y, pix)
