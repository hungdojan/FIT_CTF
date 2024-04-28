import os
from bson import DBRef, ObjectId
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_db_models.compose_objects import Volume
from jinja2 import Environment, FileSystemLoader
from dataclasses import asdict
from pprint import pprint


def demo_project(db_host: str, db_name: str):
    ctf_mgr = CTFManager(db_host, db_name)
    # prj = ctf_mgr.prj_mgr.get_doc_by_filter(name="demo")
    # if prj:
    #     print("yes")
    #     prj.start()


    # init a project
    # prj = ctf_mgr.init_project(
    #     "demo",
    #     "/home/rebulien/disk/VUT/PP/data/",
    #     "/home/rebulien/disk/VUT/PP/data/mounts",
    # )
    # proc = prj.start()
    # ctf_mgr.start_project("demo")
    # ctf_mgr.stop_project("demo")
    print(ctf_mgr.get_projects_names())
    # ctf_mgr.delete_project("demo")
    # print(ctf_mgr.get_projects_names())

    # prj.start()
    # print(add(5, 6))

    # create 3 users
    lof_users = [f"test{i+1}" for i in range(3)]
    # shadow_dir = "/home/rebulien/disk/VUT/PP/data/shadows"
    # data = ctf_mgr.user_mgr.generate_users(lof_users, shadow_dir)

    # add users to project
    # ctf_mgr.assign_users_to_project(list(data.keys()), prj.name)

    # checkpoint
    # pprint(asdict(ctf_mgr.get_project_info(prj.name)))

    # print([p.name for p in ctf_mgr.user_mgr.get_active_projects_for_user("test1")])
    # print()
    # print([u.username for u in ctf_mgr.prj_mgr.get_active_users_for_project("demo")])

    # delete users
    # ctf_mgr.user_config_mgr.remove_multiple_users_from_project(lof_users[1:], prj.name)
    # print(ctf_mgr.user_mgr.delete_users(lof_users))

    # start a project

    # start user instances

    # stop user instances

    # stop user project
