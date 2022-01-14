import random
import collections
from sanic.log import logger
from .base_updater import AppUpdater, DEFAULT_VALUE_FLAG

POOLED_FLAG = '_pooled_'

class ResponseFetcher(object):

    @classmethod
    def _find_events(cls, request, n, event_type):
        """ Find latest events in a request.

            Args:
                request (dict): Incoming request to process
                n (int): Number of events to select
                event_type (str): Type of the events to select `action` or `user`
        """
        # When looking at response names, we want to grab the yet-to-be-applied
        # event information
        assert n > 0
        first_event = []
        if event_type == 'action':
            first_event = [{'name': request['response']}]
            n -= 1
        return (first_event
                + [ev for ev in reversed(request['tracker']['events'])
                   if ev['event'] == event_type][:n])

    # Extract group from event or request
    @classmethod
    def _extract_slot_from_request(cls, request, slot_name):
        """Slot extractor"""
        return request['tracker']['slots'].get(slot_name)

    def default_to_none(function):
        """ Decorator for extraction functions: return None if exception is raised"""
        def inner(cls, *args, **kwargs):
            try:
                return function(cls, *args, **kwargs)
            except:
                return None
        return inner

    def vectorise(function):
        """ Decorator for extraction functions: make output a list"""
        def inner(cls, *args, **kwargs):
            if isinstance(args[0], list):
                events, *args = args
                return [function(cls, e, *args, **kwargs) for e in events]
            else:
                return [function(cls, *args, **kwargs)]
        return inner

    @classmethod
    @vectorise
    @default_to_none
    def _extract_entities(cls, event, entity_name):
        """Entity extractor"""
        return [e['value']
                for e in event['parse_data']['entities']
                if e['entity'] == entity_name][0]

    @classmethod
    @vectorise
    @default_to_none
    def _extract_suffixes(cls, event, separator):
        """Suffix extractor"""
        return event['name'].split(separator)[-1]

    @classmethod
    @vectorise
    @default_to_none
    def _extract_last_intent_suffixes(cls, event, separator):
        """Last intent suffix extractor"""
        return event['intent']['name'].split(separator)[-1]

    @classmethod
    def _extract_groups(cls, request, nlg_controls):
        """ Extract group names from the request.

            Details:
                The extraction is done according to the NLG controls defined in
                the configuration:
                - METHOD controls the extraction method to use
                    `entity`, `slot`, `suffix`, `last_intent_suffix` or `pooled`
                - HISTORY controls how far to look back in time (must be 1 or more)
                - NAME controls the entity or slot name to look for (may be None)
                - SEPARATOR controls the separator to use when splitting response
                names or intent names for `suffix` or `last_intent_suffix` methods

            Args:
                request (dict): Incoming request
                nlg_controls (dict): Extraction configuration

            Returns:
                list of dict: The groups found in previous events
        """

        method = nlg_controls['METHOD']
        history = nlg_controls['HISTORY']
        entity_or_slot_name = nlg_controls.get('NAME', None)
        separator = nlg_controls.get('SEPARATOR', None)

        if method == 'pooled':
            return [POOLED_FLAG]
        elif method == 'slot':
            return [cls._extract_slot_from_request(
                request, entity_or_slot_name)]

        event_type, extract_from_events, arg = {
            'entity': ('user', cls._extract_entities, entity_or_slot_name),
            'last_intent_suffix': ('user', cls._extract_last_intent_suffixes, separator),
            'suffix': ('action', cls._extract_suffixes, separator)
        }[method]

        events = cls._find_events(request, history, event_type)
        return extract_from_events(events, arg)

    @classmethod
    def _history_fallback(cls, groups):
        """ Find the likeliest group name in a list.

            Details:
                Assign a score to each group name in the list by counting the
                number of times they occur, weighing the more recent names higher.

            Args:
                groups (list of str): Group names to inspect

            Returns:
                str or None: The highest scoring group

        """
        groups = [g for g in groups if g]
        if not groups:
            return None

        n = len(groups)
        scores = collections.Counter()

        for idx, group in enumerate(groups):
            scores[group] += 1 - (idx/n)
        group, score = scores.most_common(1)[0]

        return group

    @classmethod
    def _select_response_group(cls, groups, allowed_groups, default_group):
        """ Find the group name likeliest to be needed to process the incoming request.

            Details:
                If the first group name in the list is valid, we pick that.
                Otherwise, we attempt to look at the names found in older events
                    and deduce the likeliest one.
                If that fails, we use the default.

            Args:
                groups (list of str): Group names found by `cls._extract_groups`
                allowed_groups (list of str): Valid group names as defined in the
                    configuration
                default_group (str): Default group as define in the configuration

            Returns:
                str: The chosen group
        """

        # Non allowed converted to None
        clean_groups = [g.lower() if g in allowed_groups
                        else None
                        for g in groups]

        group = clean_groups[0]
        # Best effort
        if not group:
            group = cls._history_fallback(clean_groups)

        if not group:
            logger.warning(
                f'Could not find usable NLG response group from: {groups}')
            return default_group

        return group

    @classmethod
    def _fetch_group_responses(cls, app, request):
        """ Fetch the set of responses appropriate for the request

            Args:
                request (dict): The incoming request to the server
                app (sanic.Sanic): Sanic app containing the responses

            Returns:
                dict: Responses for the group identified in the request
        """
        groups = cls._extract_groups(request, app.config.NLG_CONTROLS)
        wanted_group = cls._select_response_group(
            groups,
            app.config.NLG_LABELS,
            app.config.NLG_DEFAULT_VALUE)

        return app.config.RESPONSES[wanted_group]

    @classmethod
    def _filter_wanted_responses(cls, responses, response_key, channel):
        """ Find the possible responses for a given key and channel.

            Args:
                responses (dict): Response group
                response_key (str): Response identifier
                channel (str): Channel

            Returns:
                list of dict: Possible responses
        """

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
        """ Construct a response for the incoming request.

            Args:
                app (sanic.Sanic): App containing the responses to select from
                request (sanic.request.Request): Incoming request to process

            Returns:
                dict: A response sent back to the NLG server
        """

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

        updated = super().refresh(app, caller='NLG')

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
        super().configure(app, config_filename, caller='NLG')

        app.config['RESPONSES'] = {}

        app.config['NLG_LABELS'] = set(
            [k['NAME'] for k in app.config.NLG_CONTROLS['VALUES']]
            + [DEFAULT_VALUE_FLAG, POOLED_FLAG]
        )

        app.config.DEFAULT_RESPONSE = [
            {'text': app.config.NLG_CONTROLS['DEFAULT_RESPONSE']}
        ]

        if 'HISTORY' not in app.config.NLG_CONTROLS.keys():
            app.config.NLG_CONTROLS['HISTORY'] = 1

        cls.refresh(app)

        return None
