import ruamel.yaml as yaml
import docopt
import os
from typing import Dict, List, Set, Tuple, Text, Any, Optional


__doc__ = """Check consistency between domain and data.

Usage:
  find_elements_missing_from_domain.py [<data-files>...] [--domain DOMAIN]

Details:
  Find actions or intents missing from domain.

Optional arguments:
  -d, --domain DOMAIN             Domain filename or directory
  -h --help                       Show this
"""


def read_nlu(contents: Dict[Text,Any]) -> Set[Text]:
    intents = set()
    # print(contents)
    try:
        for block in contents['nlu']:
            intents.add(block['intent'])
    except KeyError:
        raise KeyError

    return intents


def read_core(contents: Dict[Text,Any]) -> Tuple[Set[Text], Set[Text]]:

    def iter_blocks(key):
        for block in contents[key]:
            for step in block['steps']:
                intents.add(step.get('intent', None))
                actions.add(step.get('action', None))

    intents = set()
    actions = set()

    for key in ['stories', 'rules']:
        if key in contents:
            iter_blocks(key)

    intents.discard(None)
    actions.discard(None)

    return (intents, actions)

def read_domain(contents: Dict[Text,Any]) -> Dict[Text,Set[Text]]:

    def retrieve(contents: Dict[Text,Any], section: Text) -> Set[Text]:
        try:
            return set([x for x in contents[section]])
        except TypeError:
            return set([list(x.keys())[0] for x in contents[section]])
        except KeyError:
            return set()

    return {
        section: retrieve(contents, section)
        for section in ['intents', 'actions', 'forms', 'responses']
    }

def make_header(s, symbol='=', width=40):
    if len(s) > width - 3:
        raise ValueError
    if len(s) % 2 != 0:
        s = s + ' '
    s = f' {s} '

    padding = symbol * ((width - len(s))//2)
    return f'{padding}{s}{padding}'

def report(
        domain: Dict[Text,Set[Text]],
        intents: Set[Text],
        actions: Set[Text]):
    print('\n\n')
    print(make_header('Intents'))
    o = intents - domain['intents']
    if o:
        print('\nIn data but not in domain')
        print(o)

    o = domain['intents'] - intents
    if o:
        print('\nIn domain but not in data')
        print(o)

    print('\n\n')
    print(make_header('Actions'))
    bot_actions = (domain['actions']
                    .union(domain['forms'])
                    .union(domain['responses']))
    o = actions - bot_actions
    if o:
        print('\nIn data but not in domain')
        print(o)

    o = bot_actions - actions
    if o:
        print('\nIn domain but not in data')
        print(o)
    print('\n\n')

def find_yaml_files(*paths):
    for path in paths:
        if not path:
            continue
        if not os.path.exists(path):
            continue
        break
    else:
        print(f'No valid path found: {args}')
        raise ValueError

    if os.path.isfile(path):
        return [path]

    return [
            os.path.join(path, filename)
            for filename in os.listdir(path)
            if filename.endswith('.yml')
        ]

def load_yaml(filepath):
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)

def build_intents_and_actions(filenames):
    intents = set()
    actions = set()

    for filepath in filenames:
        contents = load_yaml(filepath)
        try:
            o = read_nlu(contents)
            intents.update(o)
        except KeyError:
            o, o2 = read_core(contents)
            intents.update(o)
            actions.update(o2)

    return (intents, actions)

def build_domain(domain_files):
    o = collections.defaultdict(dict)
    for filepath in domain_files:
        contents = load_yaml(filepath)
        for k, v in contents.items():
            o[k].update(v)

    return read_domain(o)


def main():
    args = docopt.docopt(__doc__)

    data_files = find_yaml_files(
        args['<data-files>'], './data')

    domain_files = find_yaml_files(
        args['--domain'], './domain.yml', './domain')

    intents, actions = build_intents_and_actions(data_files)

    domain = build_domain(domain_files)

    report(domain, intents, actions)

if __name__ == '__main__':
    main()
