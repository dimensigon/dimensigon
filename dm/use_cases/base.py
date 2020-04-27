from dataclasses import dataclass


@dataclass
class Token:
    """
    Class that saves relation between a sent message and its asynchronous return.
    """
    id: int
    source: str
    destination: str

    @property
    def uid(self):
        return self.source + '.' + self.destination + '.' + str(self.id)



