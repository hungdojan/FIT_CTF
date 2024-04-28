import string
from pytermgui import InputField, keys


class PasswordField(InputField):
    def __init__(self, value: str = "", prompt: str = "", hide: bool = True, **kwargs):
        super().__init__(value, prompt=prompt, multiline=False, tablength=0, **kwargs)
        self._hide = hide
        self._text = ""

    @property
    def text(self) -> str:
        return self._text

    @property
    def hide(self) -> bool:
        return self._hide

    @hide.setter
    def hide(self, new_val: bool):
        self._hide = new_val

    def toggle_show(self, value: bool):
        self.hide = not value
        if self.hide:
            self.delete_back(len(self.value))
            self.insert_text(len(self._text) * "*")
        else:
            self.delete_back(len(self.value))
            self.insert_text(self._text)

    def handle_key(self, key: str) -> bool:
        """Rewrite a key handler function to hide text.

        Args:
            key (str): Input key.

        Returns:
            bool: Whether something happened (internal state has changed successfully).
        """
        if self.execute_binding(key, ignore_any=True):
            return True

        for name, options in self.keys.items():
            if (
                name.rsplit("_", maxsplit=1)[-1] in ("up", "down")
                and not self.multiline
            ):
                continue

            if key in options:
                return self.handle_action(name)

        if key in string.printable and key not in "\x0c\x0b":
            if key == keys.ENTER:
                return False

            else:
                self._text += key
                # cover text with `*` symbols
                if self.hide:
                    self.insert_text("*")
                else:
                    self.insert_text(key)

            if keys.ANY_KEY in self._bindings:
                method, _ = self._bindings[keys.ANY_KEY]
                method(self, key)

            return True

        if key == keys.BACKSPACE:
            if self._selection_length == 1:
                self.delete_back(1)
            else:
                self.delete_back(-self._selection_length)
            self._text = self._text[: -self._selection_length]

            self._selection_length = 1
            self._styled_cache = None

            return True

        if len(key) > 1 and not key.startswith("\x1b["):
            for char in key:
                self.handle_key(char)

            return True

        return False
