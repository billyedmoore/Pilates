from abc import ABC, abstractmethod
from ..image import Image


class Transform(ABC):

    @abstractmethod
    def apply(self, img: Image):
        pass
