import ruamel.yaml as yaml
import os
import collections
from typing import Dict, List, Set, Tuple, Text, Any, Optional

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
    o = []
    for path in paths:
        if not path:
            continue
        if not os.path.exists(path):
            continue

        if os.path.isfile(path):
            o.append(path)
        elif os.path.isdir(path):
            [
                os.path.join(path, filename)
                for filename in os.listdir(path)
                if filename.endswith('.yml')
            ]

    if not o:
        print(f'No valid path found: {args}')
        raise ValueError

    return o

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
    o = {'intents': [],
         'actions': [],
         'forms': {},
         'responses': {}}
    for filepath in domain_files:
        contents = load_yaml(filepath)
        for k, v in contents.items():
            if k in o.keys():
                try:
                    o[k].update(v)
                except AttributeError:
                    o[k].extend(v)

    return read_domain(o)


def run(args):
    data_files = find_yaml_files(
        *args['<data-files>'], './data')

    domain_files = find_yaml_files(
        *args['--domain'], './domain.yml', './domain')

    print(f'Data file(s)  : {data_files}')
    print(f'Domain file(s): {domain_files}')

    intents, actions = build_intents_and_actions(data_files)

    domain = build_domain(domain_files)

    report(domain, intents, actions)
