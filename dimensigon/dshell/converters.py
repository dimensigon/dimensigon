import json
import typing as t

import yaml


class Converter:

    @staticmethod
    def load(text) -> t.Any:
        return text

    @staticmethod
    def dump(data) -> str:
        return str(data)


class JSON(Converter):

    @staticmethod
    def load(text):
        return json.loads(text)

    @staticmethod
    def dump(data):
        return json.dumps(data)


class Bool(Converter):
    true = ['true', 'yes', 'y']
    false = ['false', 'no', 'n']

    @classmethod
    def load(cls, x: str):
        if x.strip().lower() in cls.true:
            return True
        elif x.strip().lower() in cls.false:
            return False
        else:
            raise ValueError

    @classmethod
    def dump(cls, data):
        if data:
            return cls.true[0]
        else:
            return cls.false[0]


class Int(Converter):

    @staticmethod
    def load(x: str):
        return int(x) if x is not None else x

    @staticmethod
    def dump(data):
        return str(data)


class List(Converter):

    def __init__(self, separator=None) -> None:
        self.separator = separator

    @staticmethod
    def dump(data):
        return ' '.join(data or [])

    def load(self, x: str):
        return x.split(sep=self.separator)


class MultiLine(Converter):

    @staticmethod
    def load(text) -> t.Any:
        return text.split('\n')

    @staticmethod
    def dump(data: t.List) -> str:
        return '\n'.join(data)


class Yaml(Converter):

    @staticmethod
    def load(text):
        return yaml.load(text, Loader=yaml.FullLoader)

    @staticmethod
    def dump(data: dict) -> str:
        if data:
            return yaml.dump(data, Dumper=yaml.Dumper)
        else:
            return ""
