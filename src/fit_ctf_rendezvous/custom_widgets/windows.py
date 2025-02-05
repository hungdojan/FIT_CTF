from pytermgui import Button, Window, WindowManager


class LoadingWindow(Window):
    """A loading window."""

    def __init__(self, mgr: WindowManager):
        super().__init__("Loading...")
        self.mgr = mgr
        self.center()
        self.is_modal = True
        self.is_static = True
        self.is_noresize = True

    def display_window(self) -> Window:
        self.mgr.add(self)
        return self


class PopUpWindow(Window):
    """A popup window."""

    def __init__(
        self,
        message: str,
        mgr: WindowManager,
        title: str = "",
    ):
        super().__init__(message, Button("Close", lambda *_: mgr.remove(self)))
        self.mgr = mgr

        if title:
            self.set_title(f"[210 bold]{title}")
        self.center()
        self.is_modal = True
        self.is_static = True
        self.is_noresize = True

    def display_window(self) -> Window:
        self.mgr.add(self)
        return self
