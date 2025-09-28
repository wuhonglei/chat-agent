from abc import ABC, abstractmethod


class BaseVectorStore(ABC):
    @abstractmethod
    def initialize(self, name: str):
        pass

    @abstractmethod
    def add_document(self):
        pass


class PersistentVectorStore(BaseVectorStore):
    def initialize(self, name):
        pass

    def add_document(self):
        pass


persistent_vector_store = PersistentVectorStore()
