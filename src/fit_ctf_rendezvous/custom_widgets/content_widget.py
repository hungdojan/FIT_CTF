from pytermgui import InputField, MouseEvent


class ContentWidget(InputField):
    """A content widget for displaying large text."""

    def __init__(self, value: str, **kwargs):
        super().__init__(value, multiline=True, **kwargs)

    def handle_key(self, key: str) -> bool:
        # make it read only
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
        return False

    def handle_mouse(self, event: MouseEvent) -> bool:
        # make it read only
        return False
