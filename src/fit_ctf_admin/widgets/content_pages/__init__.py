"""Content pages and the page factory used by the admin screen shell."""

from __future__ import annotations

from fit_ctf_admin.widgets.core_widget import AdminPage


def build_page(page_id: str) -> AdminPage:
    """Instantiate the content page widget for *page_id*."""
    from fit_ctf_admin.widgets.content_pages.clusters_page import ClustersPage
    from fit_ctf_admin.widgets.content_pages.dashboard_page import DashboardPage
    from fit_ctf_admin.widgets.content_pages.designer_page import DesignerPage
    from fit_ctf_admin.widgets.content_pages.enrollments_page import (
        EnrollmentsPage,
    )
    from fit_ctf_admin.widgets.content_pages.logs_page import LogsPage
    from fit_ctf_admin.widgets.content_pages.modules_page import ModulesPage
    from fit_ctf_admin.widgets.content_pages.progress_page import ProgressPage
    from fit_ctf_admin.widgets.content_pages.projects_page import ProjectsPage
    from fit_ctf_admin.widgets.content_pages.scenarios_page import ScenariosPage
    from fit_ctf_admin.widgets.content_pages.sessions_page import SessionsPage
    from fit_ctf_admin.widgets.content_pages.users_page import UsersPage

    factories: dict[str, type[AdminPage]] = {
        "dashboard-page": DashboardPage,
        "users-page": UsersPage,
        "projects-page": ProjectsPage,
        "enrollments-page": EnrollmentsPage,
        "clusters-page": ClustersPage,
        "scenarios-page": ScenariosPage,
        "designer-page": DesignerPage,
        "modules-page": ModulesPage,
        "progress-page": ProgressPage,
        "logs-page": LogsPage,
        "sessions-page": SessionsPage,
    }
    return factories[page_id](id=page_id)
