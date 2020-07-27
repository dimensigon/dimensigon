import json

from prompt_toolkit.validation import Validator, ValidationError


class JSONValidator(Validator):

    def transform(self, text):
        return json.loads(text)

    def validate(self, document):
        text = document.text

        if text:
            try:
                self.transform(text)
            except Exception as e:
                raise ValidationError(message=str(e))


class BoolValidator(Validator):
    true = ['true', 'yes', 'y']
    false = ['false', 'no', 'n']

    @classmethod
    def transform(cls, x: str):
        if x.strip().lower() in cls.true:
            return True
        elif x.strip().lower() in cls.false:
            return False
        else:
            raise ValueError

    def validate(self, document):
        text = document.text

        if text:
            try:
                self.transform(text)
            except:
                raise ValidationError(message=f'Not a valid bool value ({",".join(self.true)}|{",".join(self.false)})')


class IntValidator(Validator):

    @staticmethod
    def transform(x: str):
        return int(x) if x is not None else x

    def validate(self, document):
        text = document.text

        if text:
            try:
                self.transform(text)
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


import ast


class ListValidator(Validator):

    @staticmethod
    def transform(x: str):
        v = ast.literal_eval(x) if x is not None else '[]'
        if v and not isinstance(v, list):
            raise ValueError()
        return v

    def validate(self, document):
        text = document.text

        if text:
            try:
                self.transform(text)
            except Exception as e:
                raise ValidationError(message='Not a valid list. ' + str(e))
