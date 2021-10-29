import os
import random
import collections
import ruamel.yaml as yaml
from sanic.log import logger

POOLED_FLAG = '_pooled_'

class ResponseFetcher(object):


    # To test:
    # request = {'tracker': {'slots': {'test_slot': 'abc'}, 'latest_message': {'intent': {'name': 'affirm_abc'}}}, 'response' : 'res_abc'}
    # _find_wanted_group(request, METHOD='last_intent_suffix', SEPARATOR='_', VALUES=[{'NAME': 'abc'}, {'NAME': 'xyz'}])
    @classmethod
    def _find_wanted_group(cls, request, **kwargs):
        method = kwargs['METHOD']

        if method == 'pooled':
            return POOLED_FLAG
        elif method == 'slot':
            group = request['tracker']['slots'].get(kwargs['NAME'])
        else:
            s = ''
            if method == 'suffix':
                s = request['response']
            elif method == 'last_intent_suffix':
                s = request['tracker']['latest_message']['intent']['name']
            group = s.split(kwargs['SEPARATOR'])[-1]

        if not group:
            logger.warning('Could not find NLG response group')
            return None

        group = group.lower()
        allowed_values = [k['NAME'] for k in kwargs['VALUES']]
        if group not in allowed_values:
            logger.warning(f'Illegal NLG response group: {group}')
            return None

        return group

    @classmethod
    def _fetch_group_responses(cls, app, request):
        wanted_group = cls._find_wanted_group(
            request,
            **app.config.CONTROLS)
        if wanted_group:
            return app.config.RESPONSES[wanted_group]
        else:
            return app.config.RESPONSES[app.config.DEFAULT_RESPONSE_GROUP]

    @classmethod
    def _filter_wanted_responses(cls, responses, response_key, channel):

        def try_filter(c):
            try:
                return [res for res in responses[response_key]
                        if res.get('channel', 'collector') == c]

            except KeyError:
                logger.warning(f'Could not find response `{response_key}`')
                logger.warning(f'Channel: {c}')
                return []

        if response_key == 'utter_restart':
            logger.debug('restart session')
            return [{'text': ''}]

        for c in [channel, 'collector']:
            o = try_filter(c)
            if o:
                break

        return o

    @classmethod
    def construct_response(cls, app, request):

        try:
            request = request.json
        except AttributeError:
            assert isinstance(request, dict)


        args = request['arguments']
        try:
            response_key = request['response']
        except KeyError:
            response_key = request['template']

        # 'collector' is the default channel name within Rasa
        try:
            channel = request['channel']['name']
        except KeyError:
            channel = 'collector'

        responses = cls._fetch_group_responses(app, request)
        responses = cls._filter_wanted_responses(
            responses, response_key, channel)

        if responses:
            res = dict(random.choice(responses))
            res['text'] = res['text'].format(**args)
        else:
            res = app.config.DEFAULT_RESPONSE

        return res

class AppUpdater(object):

    @classmethod
    def _load_yaml(cls, filename):
        with open(filename, 'r') as f:
            try:
                r = yaml.safe_load(f)
            except yaml.composer.ComposerError as e:
                logger.error(
                    f'{filename} does not seem to be a YAML file')
                raise e
            except yaml.YAMLError as e:
                logger.error(
                    f'{filename} could not be read correctly')
                raise e
            return r

    @classmethod
    def _load_responses_from_file(
            cls, filename, format='yaml', key='responses'):
        """Load responses from a file.

            Args:
                filename (str): Responses filename
                format (str): Format in which responses are stored
                key (str or None): Where to find the responses in the file

            Returns:
                A dict of the shape:
                    response_name: [response_dict_1, ..., response_dict_n]
        """

        if format != 'yaml':
            raise NotImplemented

        r = cls._load_yaml(filename)
        if key:
            try:
                return r[key]
            except KeyError as e:
                logger.warning(
                    f'{filename} is missing the `{key}` key')
                raise e
        else:
            return r

    @classmethod
    def _parse_entry(cls, entry):
        """ Strange helper to grab entry from different config formats.

            Details:
                The config format for the entries below the `VALUES` field of the
                config is still a bit unstable.
                This function handles likely (future?) formats for config.
                Uppercase dict:
                    { 'NAME': 'abc'
                      'FILENAME': 'tests/abc_responses.yml'}
                Lowercase dict:
                    { 'name': 'abc'
                      'filename': 'tests/abc_responses.yml'}
                Iterable:
                    ['abc', 'tests/abc_responses.yml']
                    ('abc', 'tests/abc_responses.yml')

                Timestamp is defaulted to 0 if not explicitely given.

            Args:
                entry (dict or iterable): The `VALUES` config entry to parse

            Returns:
                tuple: (name: str, filename: str, timestamp: int)
        """

        mappings = {0: 'name', 1: 'filename', 2: 'timestamp'}

        if not isinstance(entry, dict):
            entry = {mappings[idx]: element for idx, element in enumerate(entry)}
        entry = {key.lower(): value for key, value in entry.items()}

        return (entry['name'], entry['filename'], entry.get('timestamp', 0))

    @classmethod
    def _lookup_file_timestamp(cls, filename):
        return os.lstat(filename).st_mtime

    @classmethod
    def _is_stale(cls, filename, last_known_timestamp=0):
        """ Check when a file was last updated, and determine freshness"""
        o = cls._lookup_file_timestamp(filename)
        return (last_known_timestamp < o, o)


    @classmethod
    def refresh(cls, app):
        """ Update the app responses if a newer version is available.

            Details:
                `app` MUST have been configured once beforehand.
                `app` is modified in-place.
                `RESPONSES` field of app config will look like:
                    switching_value1:
                        response1:
                            - text: "text switching_value1 response 1 variant 1"
                              ...
                            ...
                            - text: "text switching_value1 response 1 variant n"
                              ...
                        ...
                        responseN:
                            - text: "text switching_value1 response N variant 1"

                    switching_value2:
                        response1:
                            - text: "text switching_value2 response 1 variant 1"
                              ...
                            ...
                            - text: "text switching_value2 response 1 variant n"
                              ...
                        responseN:
                            - text: "text switching_value1 response N variant 1"
                    ...

            Args:
                app (sanic.Sanic): Sanic app to configure

            Returns:
                None
        """

        try:
            assert len(app.config['RESPONSES']) == 0
            msg = 'First-time loading responses for {key} from {filename}'
        except AssertionError:
            msg = '{key} responses have changed, loading new data from {filename}'
        except KeyError:
            logger.error('app was not configured before calling `refresh` method')
            raise

        updated = False
        for idx, value in enumerate(app.config.CONTROLS['VALUES']):
            # timestamp should be 0 if loading for the first time
            key, filename, timestamp = cls._parse_entry(value)
            stale, latest_timestamp = cls._is_stale(filename, timestamp)

            if stale:
                logger.info(msg.format(key=key, filename=filename))
                app.config['RESPONSES'][key] = cls._load_responses_from_file(filename)
                app.config.CONTROLS['VALUES'][idx]['TIMESTAMP'] = (latest_timestamp)
                updated = True

        if updated and app.config.CONTROLS['METHOD'] == 'pooled':
            app.config['RESPONSES'][POOLED_FLAG] = (
                collections.ChainMap(*list(app.config['RESPONSES'].values())))

        return None

    @classmethod
    def configure(cls, app, config_filename):
        """ Setup the app when first starting the NLG server.

            Details:
                `app` is modified in-place.
                The config settings are stored in `app.config`.

            Args:
                app (sanic.Sanic): Sanic app to configure
                config_filename (str): NLG config to use

            Returns:
                None

        """

        config = cls._load_yaml(config_filename)

        app.config.update(config)

        app.config['RESPONSES'] = {}

        app.config.REFRESH = app.config.CONTROLS['REFRESH']

        app.config.DEFAULT_RESPONSE = [{'text': app.config.DEFAULTS['RESPONSE']}]
        if len(app.config.CONTROLS['VALUES']) > 1:
            app.config.DEFAULT_RESPONSE_GROUP = app.config.DEFAULTS['GROUP']
        else:
            app.config.DEFAULT_RESPONSE_GROUP = app.config.CONTROLS['VALUES'][0]['NAME']

        app.config.HOST = app.config.NETWORK['HOST']
        app.config.PORT = app.config.NETWORK['PORT']

        cls.refresh(app)

        return None
