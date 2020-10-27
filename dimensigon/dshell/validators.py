from prompt_toolkit.validation import Validator, ValidationError

from dimensigon.dshell import converters as c


class JSON(Validator):

    def validate(self, document):
        text = document.text

        if text:
            try:
                c.JSON.load(text)
            except Exception as e:
                raise ValidationError(message=str(e))


class Bool(Validator):

    def validate(self, document):
        text = document.text

        if text:
            try:
                c.Bool.load(text)
            except:
                raise ValidationError(
                    message=f'Not a valid bool value ({",".join(c.Bool.true)}|{",".join(c.Bool.false)})')


class Int(Validator):

    def validate(self, document):
        text = document.text

        if text:
            try:
                c.Int.load(text)
            except:
                raise ValidationError(message='Not a valid integer')


class Choice(Validator):

    def __init__(self, choices) -> None:
        super().__init__()
        self.choices = choices

    def validate(self, document):
        text = document.text

        if text and text not in self.choices:
            raise ValidationError(message='Invalid choice. Choose from ' + ', '.join(self.choices),
                                  cursor_position=0)


class List(Validator):

    def __init__(self, sep=','):
        self.sep = sep

    def validate(self, document):
        text = document.text

        if text:
            try:
                c.List(self.sep).load(text)
            except Exception as e:
                raise ValidationError(message='Not a valid list. ' + str(e))
