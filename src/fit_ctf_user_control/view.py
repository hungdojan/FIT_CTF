from pytermgui import (
    Checkbox,
    Overflow,
    Window,
    WindowManager,
    Button,
    Label,
    HorizontalAlignment,
    Container,
    InputField,
    Splitter,
)
from fit_ctf_user_control.actions import Actions
from fit_ctf_user_control.custom_widgets import (
    PasswordField,
    PopUpWindow,
    LoadingWindow,
    ContentWidget
)

RANDOM_TEXT = """ Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Nulla est. Pellentesque arcu. Praesent id justo in neque elementum ultrices. Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Etiam posuere lacus quis dolor. Curabitur vitae diam non enim vestibulum interdum. Aenean fermentum risus id tortor. Morbi scelerisque luctus velit. Quisque tincidunt scelerisque libero. Integer malesuada. Aliquam ante. Nunc tincidunt ante vitae massa. Nulla non arcu lacinia neque faucibus fringilla. Class aptent taciti sociosqu ad litora torquent per conubia nostra, per inceptos hymenaeos.

Etiam egestas wisi a erat. Morbi scelerisque luctus velit. Nam sed tellus id magna elementum tincidunt. Etiam dui sem, fermentum vitae, sagittis id, malesuada in, quam. Duis risus. Pellentesque pretium lectus id turpis. Quisque tincidunt scelerisque libero. Praesent in mauris eu tortor porttitor accumsan. In convallis. Fusce tellus odio, dapibus id fermentum quis, suscipit id erat. Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla pariatur? Suspendisse sagittis ultrices augue. Duis pulvinar. Nullam faucibus mi quis velit. In rutrum. Cum sociis natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus. Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla pariatur?

Etiam neque. Praesent in mauris eu tortor porttitor accumsan. Maecenas fermentum, sem in pharetra pellentesque, velit turpis volutpat ante, in pharetra metus odio a lectus. Nunc auctor. Integer tempor. Duis viverra diam non justo. In sem justo, commodo ut, suscipit at, pharetra vitae, orci. Duis viverra diam non justo. Curabitur vitae diam non enim vestibulum interdum. Mauris suscipit, ligula sit amet pharetra semper, nibh ante cursus purus, vel sagittis velit mauris vel metus. Maecenas libero. Proin in tellus sit amet nibh dignissim sagittis. Donec ipsum massa, ullamcorper in, auctor et, scelerisque sed, est. Aliquam erat volutpat.
"""

class View:
    def __init__(self, act: Actions):
        self._actions = act

    def _render_start_instance(self):
        """Fire up an user's container.

        Display additional information.
        """
        # waiting for the container to finish booting up
        _loading_win = LoadingWindow(self._win_mgr).display_window()
        res, data = self._actions.start_user_instance()
        self._win_mgr.remove(_loading_win)

        if not res:
            PopUpWindow("Something failed.", self._win_mgr).display_window()
            return

        # render a window with information
        _win = Window(
            "Start Instance",
            Container(
                ContentWidget(RANDOM_TEXT),
                height=12,
                overflow=Overflow.SCROLL,
            ),
            ["Close", lambda *_: self._win_mgr.remove(_win)],
            width=60,
        ).center()

        _win.is_modal = True
        _win.is_noresize = True
        self._win_mgr.add(_win)

    def _render_update_password(self):
        """Update user's password."""

        def _submit_password():
            new_pass = new_pass_field._text
            confirm_pass = confirm_pass_field._text

            if new_pass == confirm_pass:
                self._actions.change_password(new_pass)
                self._win_mgr.remove(_win)
            elif warning_label.value != "Passwords don't match":
                warning_label.value = "Passwords don't match"
                warning_label.print()

        # window elements
        new_pass_field = PasswordField("", prompt="Enter new password:   ")
        confirm_pass_field = PasswordField("", prompt="Confirm new password: ")
        show_pass_cb = Checkbox(new_pass_field.toggle_show)
        warning_label = Label("")

        # render window
        _win = Window(
            "Change Password",
            new_pass_field,
            confirm_pass_field,
            Splitter(
                "Show password",
                show_pass_cb
            ),
            warning_label,
            Splitter(
                ["Change password", lambda *_: _submit_password()],
                ["Close", lambda *_: self._win_mgr.remove(_win)],
            ),
            width=50,
        ).center()
        _win.is_modal = True
        _win.is_noresize = True
        self._win_mgr.add(_win)

    def _render_generate_new_password(self):
        """Update user's password."""

        def _gen_pass():
            text = self._actions.generate_password()
            password_field.delete_back(len(password_field.value))
            password_field.insert_text(text)

        def _submit_pass():
            self._actions.change_password(password_field.value)
            self._win_mgr.remove(_win)

        # window elements
        password_field = InputField(self._actions.generate_password(), prompt="Generated password: ")

        # render window
        _win = Window(
            password_field,
            Splitter(
                ["Generate", lambda *_: _gen_pass()],
                ["Accept", lambda *_: _submit_pass()],
                ["Close", lambda *_: self._win_mgr.remove(_win)],
            ),
            width=50,
        ).center().set_title("Generate a new password")
        _win.is_modal = True
        _win.is_noresize = True
        self._win_mgr.add(_win)

    def _render_download_private_key(self):
        _win = (
            Window(
                "Download private key", ["Close", lambda *_: self._win_mgr.remove(_win)]
            )
            .center()
            .set_title("Download private key")
        )
        _win.is_modal = True
        _win.is_static = True
        _win.is_noresize = True
        self._win_mgr.add(_win)

    def _render_upload_public_key(self):
        # TODO: create a how-to window with
        _win = (
            Window(
                "Download private key", ["Close", lambda *_: self._win_mgr.remove(_win)]
            )
            .center()
            .set_title("Download private key")
        )
        _win.is_modal = True
        _win.is_static = True
        _win.is_noresize = True
        self._win_mgr.add(_win)

    def _render_login(self):
        """Render a login window."""

        def _submit_login():
            """Submit a login attempt and update the window accordingly."""
            username = username_field.value
            password = password_field._text

            if self._actions.check_login(username, password):
                self._render_menu()
            elif warning_label.value != "Login failed.":
                warning_label.value = "Login failed."
                warning_label.print()

        # window elements
        username_field = InputField("", prompt="Username: ", tablength=0)
        password_field = PasswordField("", prompt="Password: ")
        warning_label = Label("")
        show_pass_cb = Checkbox(password_field.toggle_show)
        exit_button = Button("Exit", lambda *_: self._win_mgr.stop())

        # render a window
        _win = (
            Window(
                username_field,
                password_field,
                Splitter(
                    "Show password",
                    show_pass_cb,
                    padding=10
                ),
                warning_label,
                Splitter(
                    Button("Login", lambda *_: _submit_login()),
                    exit_button,
                ),
            )
            .center()
            .set_title("Login")
        )
        _win.is_static = True
        _win.is_noresize = True

        # set bindings
        # username_field.bind(key=keys.ENTER, action=lambda *_: _submit_login())
        # password_field.bind(key=keys.ENTER, action=lambda *_: _submit_login())
        # exit_button.bind(key=keys.ENTER, action=lambda *_: self._win_mgr.stop())
        # _win.bind(key="q", action=lambda *_: self._win_mgr.stop())

        self._win_mgr.add(_win)

    def _render_menu(self):
        window = (
            Window(
                Label("Basic operations"),
                Container(
                    Button(
                        "Start instance",
                        lambda *_: self._render_start_instance(),
                        parent_align=HorizontalAlignment.LEFT,
                    ),
                    Button(
                        "Change password",
                        lambda *_: self._render_update_password(),
                        parent_align=HorizontalAlignment.LEFT,
                    ),
                    Button(
                        "Generate a new password",
                        lambda *_: self._render_generate_new_password(),
                        parent_align=HorizontalAlignment.LEFT,
                    ),
                ),
                Label("How to login with SSH key"),
                Container(
                    Button(
                        "Download private key",
                        lambda *_: self._render_download_private_key(),
                        parent_align=HorizontalAlignment.LEFT,
                    ),
                    Button(
                        "Upload public key",
                        lambda *_: self._render_upload_public_key(),
                        parent_align=HorizontalAlignment.LEFT,
                    ),
                ),
                Button(
                    "Exit",
                    lambda *_: self._win_mgr.stop(),
                ),
                width=70,
            )
            .set_title("[210 bold] CTF Control")
            .center()
        )
        window.is_static = True
        window.is_noresize = True
        self._win_mgr.add(window)

    def render_view(self):
        with WindowManager() as mgr:
            self._win_mgr = mgr
            self._render_login()
