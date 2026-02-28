from abc import ABC, abstractmethod
from src.domain.models import Section, Segment


class BookSectionParser(ABC):

    @abstractmethod
    def parse(self, section: Section) -> list[Segment]:
        pass
