"""User management page."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Checkbox, Label

from fit_ctf_admin.core.passwords import resolve_new_password
from fit_ctf_admin.dto import UserRow
from fit_ctf_admin.screens.dialogs.confirm_dialog import ConfirmDialog
from fit_ctf_admin.screens.dialogs.edit_user_dialog import (
    EditUserDialog,
    EditUserRequest,
    EditUserResult,
)
from fit_ctf_admin.screens.dialogs.new_user_dialog import (
    CreatedUser,
    NewUserDialog,
    NewUserRequest,
)
from fit_ctf_admin.screens.dialogs.secret_reveal_dialog import SecretRevealDialog
from fit_ctf_admin.widgets.core_widget import AdminPage
from fit_ctf_admin.widgets.refreshable_table import RefreshableTable

COLUMNS = ("Username", "Role", "Active", "Email", "Projects")


class UsersPage(AdminPage):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._rows: dict[str, UserRow] = {}

    def compose(self) -> ComposeResult:
        yield Label("Users", classes="page-title")
        with Horizontal(classes="page-toolbar"):
            yield Button("New user", variant="primary", id="users-new-btn")
            yield Button("Edit", id="users-edit-btn")
            yield Button("Disable", id="users-disable-btn")
            yield Button("Delete", variant="error", id="users-delete-btn")
            yield Checkbox("Show inactive", id="users-show-inactive")
        yield Label(
            "space marks a row for a bulk action, ctrl+a marks all, ctrl+d clears",
            classes="page-hint",
        )
        yield RefreshableTable(id="users-table", selectable=True)

    def refresh_page(self) -> None:
        include_inactive = self.query_one("#users-show-inactive", Checkbox).value
        self.call_gateway(
            lambda: self.core.gateway.list_users(include_inactive),
            self._fill_table,
            group="users-load",
        )

    def _fill_table(self, rows: list[UserRow]) -> None:
        self._rows = {row.username: row for row in rows}
        self.query_one("#users-table", RefreshableTable).set_data(
            COLUMNS,
            [
                (
                    row.username,
                    row.role,
                    "yes" if row.active else "no",
                    row.email,
                    ", ".join(row.projects),
                )
                for row in rows
            ],
            [row.username for row in rows],
        )

    @property
    def _table(self) -> RefreshableTable:
        return self.query_one("#users-table", RefreshableTable)

    @property
    def _selected_username(self) -> str | None:
        return self._table.selected_key

    def _targets(self, action: str) -> list[str]:
        """Marked rows, else the cursor row; warns and returns ``[]`` when empty."""
        targets = self._table.action_keys
        if not targets:
            self.notify(f"Select a user to {action}.", severity="warning")
        return targets

    @on(Checkbox.Changed, "#users-show-inactive")
    def _filter_changed(self) -> None:
        self.refresh_page()

    @on(RefreshableTable.SelectionChanged, "#users-table")
    def _selection_changed(self, event: RefreshableTable.SelectionChanged) -> None:
        count = len(event.keys)
        suffix = f" ({count})" if count else ""
        self.query_one("#users-disable-btn", Button).label = f"Disable{suffix}"
        self.query_one("#users-delete-btn", Button).label = f"Delete{suffix}"

    # -- create ----------------------------------------------------------------

    @on(Button.Pressed, "#users-new-btn")
    def _new_user(self) -> None:
        self.app.push_screen(NewUserDialog(self._create_user), self._handle_new_user)

    def _create_user(self, request: NewUserRequest):
        # returned to the dialog, which keeps itself open if this raises
        return self.core.gateway.create_user(
            request.username,
            request.password,
            generate_password=request.generate_password,
            email=request.email,
            role=request.role,
        )

    def _handle_new_user(self, result: CreatedUser | None) -> None:
        if result is None:
            return
        row, password = result
        self.app.push_screen(SecretRevealDialog(f"Password for `{row.username}`", password))
        self.refresh_page()

    # -- edit ------------------------------------------------------------------

    @on(Button.Pressed, "#users-edit-btn")
    def _edit_user(self) -> None:
        username = self._selected_username
        row = self._rows.get(username) if username else None
        if row is None:
            self.notify("Select a user to edit.", severity="warning")
            return
        self.app.push_screen(EditUserDialog(row, self._update_user), self._handle_edit_user)

    async def _update_user(self, request: EditUserRequest) -> str | None:
        """Apply the edit; returns the new plaintext password when it changed."""
        await self.core.gateway.update_user(
            request.username, email=request.email, role=request.role
        )
        if not request.changes_password:
            return None
        # same helper both gateways use for new users
        password = resolve_new_password(request.password, request.generate_password)
        await self.core.gateway.change_password(request.username, password)
        return password

    def _handle_edit_user(self, result: EditUserResult | None) -> None:
        if result is None:
            return
        if result.password is not None:
            self.app.push_screen(
                SecretRevealDialog(f"New password for `{result.username}`", result.password)
            )
        self.notify(f"User `{result.username}` updated.")
        self.refresh_page()

    # -- disable / delete ------------------------------------------------------

    @on(Button.Pressed, "#users-disable-btn")
    def _disable_user(self) -> None:
        usernames = self._targets("disable")
        if not usernames:
            return
        self.app.push_screen(
            ConfirmDialog(
                _plural_title("Disable", usernames),
                "The users are deactivated and all their enrollments are cancelled.",
                confirm_label="Disable",
            ),
            lambda confirmed: self._do_disable(usernames) if confirmed else None,
        )

    def _do_disable(self, usernames: list[str]) -> None:
        self.call_gateway(
            lambda: self.core.gateway.disable_users(usernames),
            lambda failures: self._bulk_done("disabled", usernames, failures),
            group="users-mutate",
        )

    @on(Button.Pressed, "#users-delete-btn")
    def _delete_user(self) -> None:
        usernames = self._targets("delete")
        if not usernames:
            return
        self.app.push_screen(
            ConfirmDialog(
                _plural_title("Delete", usernames),
                "Removes the users, their enrollments, and their home directories.",
            ),
            lambda confirmed: self._do_delete(usernames) if confirmed else None,
        )

    def _do_delete(self, usernames: list[str]) -> None:
        self.call_gateway(
            lambda: self.core.gateway.delete_users(usernames),
            lambda failures: self._bulk_done("deleted", usernames, failures),
            group="users-mutate",
        )

    def _bulk_done(self, verb: str, usernames: list[str], failures: list[str]) -> None:
        for failure in failures:
            self.notify(failure, severity="error")
        done = len(usernames) - len(failures)
        self.notify(f"{done} user(s) {verb}.")
        self._table.clear_marks()
        self.refresh_page()


def _plural_title(verb: str, usernames: list[str]) -> str:
    if len(usernames) == 1:
        return f"{verb} user `{usernames[0]}`?"
    listed = ", ".join(f"`{name}`" for name in usernames[:5])
    if len(usernames) > 5:
        listed += f", … (+{len(usernames) - 5})"
    return f"{verb} {len(usernames)} users: {listed}?"
