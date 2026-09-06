import os

from fit_ctf_cli.cli import cli


def main():
    # Skip initialization during shell completion for performance. The heavy
    # imports (dotenv, YamlParser -> jsonschema/pymongo chain) are deferred
    # into this function so completion invocations do not pay for them either.
    if "_FIT_CTF_COMPLETE" in os.environ:
        cli()
        return

    from dotenv import load_dotenv

    from fit_ctf.components.data_parser.yaml_parser import YamlParser

    load_dotenv()

    # initialize validators
    YamlParser.init_parser()

    # start cli commands
    cli()


if __name__ == "__main__":
    main()
