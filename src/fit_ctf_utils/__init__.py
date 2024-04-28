from jinja2 import Environment, FileSystemLoader, Template

def get_template(template_filename: str, template_dir: str) -> Template:
    loader = FileSystemLoader(template_dir)
    env = Environment(loader=loader)

    return env.get_template(template_filename)
