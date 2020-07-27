import os
import typing as t

from prompt_toolkit.history import History

from dimensigon.utils.helpers import get_now


class FileTagHistory(History):
    """
    :class:`.History` class that stores all strings in a file.
    """

    def __init__(self, filename: str, tag: str) -> None:
        self.tag = tag
        self.filename = filename
        super(FileTagHistory, self).__init__()

    def load_history_strings(self) -> t.Iterable[str]:
        strings: t.List[str] = []
        lines: t.List[str] = []

        def add() -> None:
            if lines:
                # Join and drop trailing newline.
                string = "".join(lines)[:-1]

                strings.append(string)

        if os.path.exists(self.filename):
            with open(self.filename, "rb") as f:
                for line_bytes in f:
                    line = line_bytes.decode("utf-8")

                    if line.startswith(f"{self.tag}+"):
                        lines.append(line.split('+', 1)[1])
                    else:
                        add()
                        lines = []

                add()

        # Reverse the order, because newest items have to go first.
        return reversed(strings)

    def store_string(self, string: str) -> None:
        # Save to file.
        with open(self.filename, "ab") as f:
            def write(t: str) -> None:
                f.write(t.encode("utf-8"))

            write("\n# %s\n" % get_now())
            for line in string.split("\n"):
                write("%s+%s\n" % (self.tag, line))
