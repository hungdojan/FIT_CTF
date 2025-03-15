from fit_ctf_utils.exceptions import UserNotExistsException
import fit_ctf_models.user as user
from fit_ctf_utils.auth.auth_interface import AuthInterface


class LocalAuth(AuthInterface):

    def __init__(self, user_mgr: "user.UserManager"):
        self._user_mgr = user_mgr

    def validate_credentials(self, username: str, password: str) -> bool:
        try:
            user = self._user_mgr.get_user(username)
        except UserNotExistsException:
            return False
        return user.password == self.get_password_hash(password)
