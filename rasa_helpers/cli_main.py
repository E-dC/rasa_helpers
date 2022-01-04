import docopt
__doc__ = """Access rasa helpers CLI tools.

Usage:
  rh serve (all|nlg|nlu) <config>
  rh check [<data-files>...] [--domain DOMAIN]

Details:
  serve:
    Start a NLG and/or NLU server for Rasa.

  check:
    Find actions or intents missing from domain.

Optional arguments:
  -d, --domain DOMAIN             Domain filename or directory
  -h --help                       Show this
"""

def main():
    args = docopt.docopt(__doc__)
    if args['check']:
        from rasa_helpers.cli_check import run
        args.pop('check')

    if args['serve']:
        from rasa_helpers.cli_serve import run
        args.pop('serve')

    run(args)
