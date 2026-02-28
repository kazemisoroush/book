from abc import ABC, abstractmethod


class BookDownloader(ABC):

    @abstractmethod
    def parse(self, url: str) -> bool:
        pass
