from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, Template

load_dotenv()

def get_template(template_filename: str, template_dir: str) -> Template:
    loader = FileSystemLoader(f"{template_dir}")
    env = Environment(loader=loader)

    return env.get_template(template_filename)

