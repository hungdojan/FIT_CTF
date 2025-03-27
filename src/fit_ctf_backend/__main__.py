from dotenv import load_dotenv

from fit_ctf_backend.cli import cli
from fit_ctf_utils.data_parser.yaml_parser import YamlParser

load_dotenv()


def main():
    # initialize validators
    YamlParser.init_parser()

    # start cli commands
    cli()


if __name__ == "__main__":
    main()
