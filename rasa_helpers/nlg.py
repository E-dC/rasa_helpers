import random
import collections
from sanic.log import logger
from .base_updater import AppUpdater

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
        elif method == 'entity':
            entities =  request['tracker']['latest_message']['entities']
            try:
                group = [e['value']
                         for e in entities
                         if e['entity'] == kwargs['NAME']][0]
            except IndexError:
                group = None
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
            **app.config.NLG_CONTROLS)
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


class NLGAppUpdater(AppUpdater):

    @classmethod
    def _load_updated_data(
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

        updated = cls._base_refresh(app, caller='nlg')

        if updated and app.config.NLG_CONTROLS['METHOD'] == 'pooled':
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
        cls._base_configure(app, config_filename, caller='nlg')

        app.config['RESPONSES'] = {}

        app.config.NLG_REFRESH = app.config.NLG_CONTROLS['REFRESH']

        app.config.DEFAULT_RESPONSE = [
            {'text': app.config.NLG_CONTROLS['DEFAULTS']['RESPONSE']}
        ]

        if len(app.config.NLG_CONTROLS['VALUES']) > 1:
            app.config.DEFAULT_RESPONSE_GROUP = (
                app.config.NLG_CONTROLS['DEFAULTS' ]['GROUP'])
        else:
            app.config.DEFAULT_RESPONSE_GROUP = (
                app.config.NLG_CONTROLS['VALUES'][0]['NAME'])
        cls.refresh(app)

        return None
