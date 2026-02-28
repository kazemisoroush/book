from abc import ABC, abstractmethod
from src.domain.models import BookMetadata


class BookMetadataParser(ABC):

    @abstractmethod
    def parse(self, content: str) -> BookMetadata:
        pass
