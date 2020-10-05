import ast
import json

from prompt_toolkit.validation import Validator, ValidationError


class JSONValidator(Validator):

    @staticmethod
    def load(text):
        return json.loads(text)

    @staticmethod
    def dump(data):
        return json.dumps(data)

    def validate(self, document):
        text = document.text

        if text:
            try:
                self.load(text)
            except Exception as e:
                raise ValidationError(message=str(e))


class BoolValidator(Validator):
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

    def validate(self, document):
        text = document.text

        if text:
            try:
                self.load(text)
            except:
                raise ValidationError(message=f'Not a valid bool value ({",".join(self.true)}|{",".join(self.false)})')


class IntValidator(Validator):

    @staticmethod
    def load(x: str):
        return int(x) if x is not None else x

    @staticmethod
    def dump(data):
        return str(data)

    def validate(self, document):
        text = document.text

        if text:
            try:
                self.load(text)
            except:
                raise ValidationError(message='Not a valid integer')


class ChoiceValidator(Validator):

    def __init__(self, choices) -> None:
        super().__init__()
        self.choices = choices

    def validate(self, document):
        text = document.text

        if text and text not in self.choices:
            raise ValidationError(message='Invalid choice. Choose from ' + ', '.join(self.choices),
                                  cursor_position=0)


class ListConverter(Validator):

    def __init__(self, separator=None) -> None:
        self.separator = separator

    @staticmethod
    def dump(data):
        return ' '.join(data or [])

    def load(self, x: str):
        return x.split(sep=self.separator)

    def validate(self, document):
        return document.text


class ListValidator(Validator):


    @staticmethod
    def load(x: str):
        v = ast.literal_eval(x) if x is not None else '[]'
        if v and not isinstance(v, list):
            raise ValueError()
        return v

    def validate(self, document):
        text = document.text

        if text:
            try:
                self.load(text)
            except Exception as e:
                raise ValidationError(message='Not a valid list. ' + str(e))
