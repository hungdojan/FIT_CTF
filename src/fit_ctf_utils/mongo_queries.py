import fit_ctf_models.project as prj
import fit_ctf_models.user as user


class MongoQueries:

    @staticmethod
    def user_enrollment_port_collision(
        forwarded_port: int, container_port: int
    ) -> list:
        return [
            {
                "$match": {
                    "$and": [
                        {"active": True},
                        {
                            "$or": [
                                {"forwarded_port": forwarded_port},
                                {"container_port": container_port},
                            ]
                        },
                    ]
                }
            }
        ]

    @staticmethod
    def user_enrollment_get_enrolled_users_raw(
        project: "prj.Project", include_inactive: bool = False
    ) -> list:
        """Query for fetching raw data of active user enrolled to a project.

        :param project: The project in question.
        :type project: prj.Project
        :param include_inactive: Search for inactive enrollments as well.
            Defaults to False.
        :type include_inactive: bool
        """
        _filter: dict = {
            "project_id.$id": project.id,
        }
        if not include_inactive:
            _filter["active"] = True
        return [
            {
                # search only user_enrollment for the given user
                "$match": _filter
            },
            {
                # get project info
                "$lookup": {
                    "from": "user",
                    "localField": "user_id.$id",
                    "foreignField": "_id",
                    "as": "users",
                    "pipeline": [
                        {"$match": {"active": True}},
                        {"$project": {"password": 0, "_id": 0}},
                    ],
                }
            },
            {
                # since lookup returns array
                # pop the first element from the array
                "$unwind": "$users"
            },
            {
                "$project": {
                    "_id": 0,
                    "project_id": 0,
                    "user_id": 0,
                    "services": 0,
                }
            },
        ]

    @staticmethod
    def user_enrollment_get_enrolled_users(
        project: "prj.Project", include_inactive: bool = False
    ) -> list:
        """Query for fetching users enrolled to the chosen project.

        The output data are of type `user.User`.
        :param project: The project in question.
        :type project: prj.Project
        :param include_inactive: Search for inactive enrollments as well.
            Defaults to False.
        :type include_inactive: bool
        """
        _filter: dict = {
            "project_id.$id": project.id,
        }
        if not include_inactive:
            _filter["active"] = True
        return [
            {
                # search only user_enrollment for the given user
                "$match": _filter
            },
            {
                # get project info
                "$lookup": {
                    "from": "user",
                    "localField": "user_id.$id",
                    "foreignField": "_id",
                    "as": "users",
                    "pipeline": [
                        {"$match": {"active": True}},
                    ],
                }
            },
            {
                # since lookup returns array
                # pop the first element from the array
                "$unwind": "$users"
            },
            {"$project": {"_id": 0, "users": 1}},
            # flatten data by one level
            {"$replaceRoot": {"newRoot": "$users"}},
        ]

    @staticmethod
    def user_enrollment_get_enrolled_projects(
        user: "user.User", include_inactive: bool = False
    ) -> list:
        _filter: dict = {
            "user_id.$id": user.id,
        }
        if not include_inactive:
            _filter["active"] = True
        return [
            {
                # search only user_enrollment for the given user
                "$match": _filter
            },
            {
                # get project info
                "$lookup": {
                    "from": "project",
                    "localField": "project_id.$id",
                    "foreignField": "_id",
                    "as": "project",
                    "pipeline": [{"$match": {"active": True}}],
                }
            },
            {
                # since lookup returns array
                # pop the first element from the array
                "$unwind": "$project"
            },
            {"$project": {"project": 1, "_id": 0}},
            # flatten data by one level
            {"$replaceRoot": {"newRoot": "$project"}},
        ]

    @staticmethod
    def user_enrollment_get_enrolled_projects_raw(
        user: "user.User", include_inactive: bool = False
    ) -> list:
        # query to retrieve number or enrolled users
        project_pipeline = [
            {"$match": {"active": True}},
            {
                "$lookup": {
                    "from": "user_enrollment",
                    "localField": "_id",
                    "foreignField": "project_id.$id",
                    "as": "user_enrollments",
                    "pipeline": [{"$match": {"active": True}}],
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "name": 1,
                    "active": 1,
                    "max_nof_users": 1,
                    "active_users": {"$size": "$user_enrollments"},
                }
            },
        ]
        _filter: dict = {
            "user_id.$id": user.id,
        }
        if not include_inactive:
            _filter["active"] = True
        return [
            {
                # search only user_enrollment for the given user
                "$match": _filter
            },
            {
                # get project info
                "$lookup": {
                    "from": "project",
                    "localField": "project_id.$id",
                    "foreignField": "_id",
                    "as": "project",
                    "pipeline": project_pipeline,
                }
            },
            {
                # since lookup returns array
                # pop the first element from the array
                "$unwind": "$project"
            },
            {"$project": {"project": 1, "_id": 0}},
            {"$replaceRoot": {"newRoot": "$project"}},
        ]

    @staticmethod
    def user_get_users(include_inactive: bool):
        _filter = {}
        if not include_inactive:
            _filter["active"] = True

        return [
            # get active/all users
            {"$match": _filter},
            {
                # get all the projects that they are enrolled to
                "$lookup": {
                    "from": "user_enrollment",
                    "localField": "_id",
                    "foreignField": "user_id.$id",
                    "as": "user_enrollments",
                    "pipeline": [
                        # get only enrolled projects and their names
                        {"$match": {"active": True}},
                        {"$project": {"project_id": 1, "_id": 0}},
                    ],
                }
            },
            {
                # look up the project information
                "$lookup": {
                    "from": "project",
                    "localField": "user_enrollments.project_id.$id",
                    "foreignField": "_id",
                    "as": "projects",
                    "pipeline": [
                        # get only project name
                        {"$project": {"name": 1, "_id": 0}}
                    ],
                }
            },
            {
                # list field to display
                "$project": {
                    "username": 1,
                    "_id": 0,
                    "projects": 1,
                    "active": 1,
                }
            },
        ]

    @staticmethod
    def user_enrollment_multiple_user_pipeline(
        project: "prj.Project", lof_usernames: list[str]
    ) -> list:
        """A multiple user pipeline query template.

        :param project: Project object.
        :type project: _project.Project
        :param lof_usernames: A list of usernames to find.
        :type lof_usernames: list[str]
        :return: Generated query.
        :rtype: list
        """
        return [
            {
                # get configs for a given project
                "$match": {"project_id.$id": project.id, "active": True}
            },
            {
                # get user info
                "$lookup": {
                    "from": "user",
                    "localField": "user_id.$id",
                    "foreignField": "_id",
                    "as": "user",
                    "pipelineuser_enrollment": [
                        {
                            "$match": {
                                "active": True,
                                "username": {"$in": lof_usernames},
                            }
                        }
                    ],
                }
            },
            {
                # pop first element from the array
                "$unwind": "$user"
            },
            {
                # transform to the final internet format
                "$project": {"username": "$user.username", "user_id": "$user._id"}
            },
        ]

    @staticmethod
    def user_enrollment_all_users_pipeline(project: "prj.Project") -> list:
        """An all users pipeline query template.

        :param project: Project object.
        :type project: _project.Project
        :return: Generated query.
        :rtype: list
        """
        return [
            {
                # get configs for a given project
                "$match": {"project_id.$id": project.id, "active": True}
            },
            {
                # get user info
                "$lookup": {
                    "from": "user",
                    "localField": "user_id.$id",
                    "foreignField": "_id",
                    "as": "user",
                    "pipeline": [
                        {
                            "$match": {
                                "active": True,
                            }
                        }
                    ],
                }
            },
            {
                # pop first element from the array
                "$unwind": "$user"
            },
            {
                # transform to the final internet format
                "$project": {
                    "username": "$user.username",
                }
            },
        ]

    @staticmethod
    def user_enrollment_get_all_enrolled_projects(user: "user.User") -> list:
        return [
            {"$match": {"user_id.$id": user.id}},
            {
                "$lookup": {
                    "from": "project",
                    "localField": "project_id.$id",
                    "foreignField": "_id",
                    "as": "project",
                }
            },
            {"$unwind": "$project"},
        ]

    @staticmethod
    def project_get_projects_raw(include_inactive: bool) -> list:
        _filter = {}
        if not include_inactive:
            _filter["active"] = True
        return [
            {"$match": _filter},
            {
                "$lookup": {
                    "from": "user_enrollment",
                    "localField": "_id",
                    "foreignField": "project_id.$id",
                    "as": "user_enrolls",
                    "pipeline": [{"$match": {"active": True}}],
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "name": 1,
                    "max_nof_users": 1,
                    "active_users": {"$size": "$user_enrolls"},
                    "active": 1,
                }
            },
        ]

    @staticmethod
    def project_get_reserved_ports() -> list:
        return [
            {"$match": {"active": True}},
            {
                "$project": {
                    "_id": 1,
                    "name": 1,
                    "min_port": "$starting_port_bind",
                    "max_port": {"$add": ["$max_nof_users", "$starting_port_bind"]},
                }
            },
        ]

    @staticmethod
    def user_enrollment_aggregate_pairs_user_project(
        user_project_pairs: list[tuple["user.User", "prj.Project"]],
    ) -> list:
        return [
            {
                "$match": {
                    "$or": [
                        {"user_id.$id": u.id, "project_id.$id": p.id, "active": False}
                        for u, p in user_project_pairs
                    ]
                }
            },
            {
                "$lookup": {
                    "from": "user",
                    "localField": "user_id.$id",
                    "foreignField": "_id",
                    "as": "user",
                }
            },
            {"$unwind": "$user"},
            {
                "$lookup": {
                    "from": "project",
                    "localField": "project_id.$id",
                    "foreignField": "_id",
                    "as": "project",
                }
            },
            {"$unwind": "$project"},
        ]

    @staticmethod
    def count_module_name_occurences() -> list[dict]:
        # XXX: does not do matching
        return [
            {"$unwind": "$services"},
            {
                "$project": {
                    "_id": 0,
                    "services": {
                        "$map": {
                            "input": {"$objectToArray": "$services"},
                            "as": "item",
                            "in": "$$item.v",
                        }
                    },
                }
            },
            {"$unwind": "$services"},
            {"$group": {"_id": "$services.module_name", "count": {"$sum": 1}}},
        ]

    @staticmethod
    def export_user_enrollments(
        project: "prj.Project | None" = None, include_inactive: bool = False
    ) -> list[dict]:
        _filter = {}
        if project is not None:
            _filter["project_id.$id"] = project.id
        if not include_inactive:
            _filter["active"] = True

        return [
            {"$match": _filter},
            {
                "$lookup": {
                    "from": "project",
                    "localField": "project_id.$id",
                    "foreignField": "_id",
                    "as": "project",
                    "pipeline": [{"$project": {"_id": 0, "name": 1}}],
                }
            },
            {
                "$lookup": {
                    "from": "user",
                    "localField": "user_id.$id",
                    "foreignField": "_id",
                    "as": "user",
                    "pipeline": [{"$project": {"_id": 0, "username": 1}}],
                }
            },
            {"$unwind": "$project"},
            {"$unwind": "$user"},
            {
                "$project": {
                    "_id": 0,
                    "user": "$user.username",
                    "project": "$project.name",
                    "container_port": 1,
                    "forwarded_port": 1,
                    "progress": 1,
                    "services": 1,
                    "networks": 1,
                }
            },
        ]
