from abc import ABC, abstractmethod
from src.domain.models import BookContent


class BookContentParser(ABC):

    @abstractmethod
    def parse(self, content: str) -> BookContent:
        pass
