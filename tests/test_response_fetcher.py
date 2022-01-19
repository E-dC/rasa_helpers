import pytest
import rasa_helpers.nlg as nlg
import sanic
import time
import os
import shutil
from pathlib import Path

valid_req = {
    'tracker': {
        'slots': {'test_slot': 'abc'},
        'latest_message': {
            'intent': {'name': 'affirm_abc'},
            'entities': [
                {'entity': 'test_entity', 'value': 'abc', 'start': 0, 'end': 0}
            ]
        },
        'events': [
            {
                'event': 'user',
                'intent': {'name': 'affirm_abc'},
                'parse_data': {
                    'entities': [
                        {'entity': 'test_entity',
                         'value': 'abc', 'start': 0, 'end': 0}
                    ]
                }
            }
        ]
    },
    'response' : 'res_abc'
}
valid_events = valid_req['tracker']['events']

invalid_req = {
    'tracker': {
        'slots': {'test_slot': 'abcd'},
        'latest_message': {
            'intent': {'name': 'affirm_abcd'},
            'entities': [
                {'entity': 'test_entity', 'value': 'abcd', 'start': 0, 'end': 0}
            ]
        },
        'events': [
            {
                'event': 'user',
                'intent': {'name': 'affirm_abcd'},
                'parse_data': {
                    'entities': [
                        {'entity': 'test_entity',
                         'value': 'abcd', 'start': 0, 'end': 0}
                    ]
                }
            }
        ]
    },
    'response' : 'res_abcd'
}
invalid_events = invalid_req['tracker']['events']

test_responses = {
    'res1': [
        {'text': 'text res1 default channel'},
        {'text': 'text res1 facebook channel', 'channel': 'facebook'},
        {'text': 'text res1 whatsapp channel', 'channel': 'whatsapp'}
    ],
    'res2': [{
        'text': 'text res2 buttons default channel',
        'buttons': [
            {'payload': 'button1', 'text': 'text button1'},
            {'payload': 'button2', 'text': 'text button2'}
        ]
    },
    {
        'text': 'text res2 buttons facebook channel',
        'buttons': [
            {'payload': 'button1', 'text': 'text facebook button1'},
            {'payload': 'button2', 'text': 'text facebook button2'}
        ],
        'channel': 'facebook'
    }],
    'res3': [
        {'text': 'text res3 default channel variation 1'},
        {'text': 'text res3 default channel variation 2'},
        {'text': 'text res3 whatsapp channel variation 1', 'channel': 'whatsapp'},
        {'text': 'text res3 whatsapp channel variation 2', 'channel': 'whatsapp'}
    ]
}

@pytest.mark.nlg
@pytest.mark.response_fetcher
@pytest.mark.extractors
@pytest.mark.parametrize(
    "events,entity_name,expected",
    [
        (valid_events[0], 'test_entity', ['abc']),
        (invalid_events[0], 'test_entity', ['abcd']),
        (valid_events, 'test_entity', ['abc']),
        (invalid_events, 'test_entity', ['abcd']),
        ([valid_events[0], valid_events[0]],
         'test_entity', ['abc', 'abc']),
        ([invalid_events[0], valid_events[0]],
         'test_entity', ['abcd', 'abc']),
        ([invalid_events[0], invalid_events[0]],
         'test_entity', ['abcd', 'abcd'])
    ])
def test_extract_entity_from_events(events, entity_name, expected):
    assert (
        nlg.ResponseFetcher._extract_entities(events, entity_name) == expected
    )

@pytest.mark.nlg
@pytest.mark.response_fetcher
@pytest.mark.parametrize(
    "req,config,expected",
    [
        (valid_req,
         {'METHOD': 'slot',
          'NAME': 'test_slot',
          'VALUES': [{'NAME': 'abc'}],
          'HISTORY': 1},
         ['abc']),
        (valid_req,
         {'METHOD': 'entity',
          'NAME': 'test_entity',
          'VALUES': [{'NAME': 'abc'}],
          'HISTORY': 1},
         ['abc']),
        (valid_req,
         {'METHOD': 'suffix',
          'SEPARATOR': '_',
          'VALUES': [{'NAME': 'abc'}],
          'HISTORY': 1},
         ['abc']),
        (valid_req,
         {'METHOD': 'last_intent_suffix',
          'SEPARATOR': '_',
          'VALUES': [{'NAME': 'abc'}],
          'HISTORY': 1},
         ['abc']),
        (valid_req,
         {'METHOD': 'pooled',
          'VALUES': [{'NAME': 'abc'}],
          'HISTORY': 1},
         [nlg.POOLED_FLAG]),
        (invalid_req,
         {'METHOD': 'slot',
          'NAME': 'test_slot',
          'VALUES': [{'NAME': 'abc'}],
          'HISTORY': 1},
         ['abcd']),
        (invalid_req,
         {'METHOD': 'entity',
          'NAME': 'test_entity',
          'VALUES': [{'NAME': 'abc'}],
          'HISTORY': 1},
         ['abcd']),
        (invalid_req,
         {'METHOD': 'suffix',
          'SEPARATOR': '_',
          'VALUES': [{'NAME': 'abc'}],
          'HISTORY': 1},
         ['abcd']),
        (invalid_req,
         {'METHOD': 'last_intent_suffix',
          'SEPARATOR': '_',
          'VALUES': [{'NAME': 'abc'}],
          'HISTORY': 1},
         ['abcd'])
    ])
def test_extract_groups(req, config, expected):
    # allowed_groups = (
    #     [k['NAME'] for k in config.pop('VALUES')]
    #     + [nlg.DEFAULT_VALUE_FLAG, nlg.POOLED_FLAG]
    # )
    assert nlg.ResponseFetcher._extract_groups(
        req, config) == expected


@pytest.mark.nlg
@pytest.mark.response_fetcher
@pytest.mark.parametrize(
    "req,config,expected",
    [
        (valid_req,
         {
             'NLG_CONTROLS': {
                 'METHOD': 'slot',
                 'NAME': 'test_slot',
                 'VALUES': [{'NAME': 'abc'}],
                 'HISTORY': 1},
             'NLG_LABELS': ['abc', 'xyz'],
             'RESPONSES': {'abc': {'res1': 'my response'}},
             'NLG_DEFAULT_VALUE': 'xyz'
            },
         {'res1': 'my response'})
        # (valid_req,
        #  {'METHOD': 'entity',
        #   'NAME': 'test_entity',
        #   'VALUES': [{'NAME': 'abc'}],
        #   'HISTORY': 1},
        #  ['abc']),
        # (valid_req,
        #  {'METHOD': 'suffix',
        #   'SEPARATOR': '_',
        #   'VALUES': [{'NAME': 'abc'}],
        #   'HISTORY': 1},
        #  ['abc']),
        # (valid_req,
        #  {'METHOD': 'last_intent_suffix',
        #   'SEPARATOR': '_',
        #   'VALUES': [{'NAME': 'abc'}],
        #   'HISTORY': 1},
        #  ['abc']),
        # (valid_req,
        #  {'METHOD': 'pooled',
        #   'VALUES': [{'NAME': 'abc'}],
        #   'HISTORY': 1},
        #  [nlg.POOLED_FLAG]),
        # (invalid_req,
        #  {'METHOD': 'slot',
        #   'NAME': 'test_slot',
        #   'VALUES': [{'NAME': 'abc'}],
        #   'HISTORY': 1},
        #  ['abcd']),
        # (invalid_req,
        #  {'METHOD': 'entity',
        #   'NAME': 'test_entity',
        #   'VALUES': [{'NAME': 'abc'}],
        #   'HISTORY': 1},
        #  ['abcd']),
        # (invalid_req,
        #  {'METHOD': 'suffix',
        #   'SEPARATOR': '_',
        #   'VALUES': [{'NAME': 'abc'}],
        #   'HISTORY': 1},
        #  ['abcd']),
        # (invalid_req,
        #  {'METHOD': 'last_intent_suffix',
        #   'SEPARATOR': '_',
        #   'VALUES': [{'NAME': 'abc'}],
        #   'HISTORY': 1},
        #  ['abcd'])
    ])
def test_fetch_group_responses(req, config, expected):
    # allowed_groups = (
    #     [k['NAME'] for k in config.pop('VALUES')]
    #     + [nlg.DEFAULT_VALUE_FLAG, nlg.POOLED_FLAG]
    # )
    # print(app)
    # print(app.config)
    app = sanic.Sanic('Test_app_response_fetcher'
    app.config.update(config)
    assert nlg.ResponseFetcher._fetch_group_responses(
        app, req) == expected




@pytest.mark.nlg
@pytest.mark.response_fetcher
@pytest.mark.parametrize(
    "groups,expected",
    [
        (['abc', 'xyz'], 'abc'),
        (['abc', 'xyz', 'xyz', 'xyz'], 'xyz'),
        ([None, 'xyz', 'ijk', None, 'ijk', 'ijk' 'xyz'], 'ijk'),
        ([None, None], None),
    ])
def test_history_fallback(groups, expected):
    assert nlg.ResponseFetcher._history_fallback(
        groups) == expected


@pytest.mark.nlg
@pytest.mark.response_fetcher
@pytest.mark.parametrize(
    "groups,allowed_groups,default_group,expected",
    [
        (['abc', 'xyz'], ['abc', 'xyz'], 'xyz', 'abc'),
        (['axc', 'xyz'], ['abc', 'xyz'], 'abc', 'xyz'),
        (['axc', 'ijk', 'xyz'], ['abc', 'xyz', 'ijk'], 'xyz', 'ijk'),
        (['aaa', 'bbb', 'ccc'], ['abc', 'xyz'], 'xyz', 'xyz')
    ])
def test_select_response_group(
    groups, allowed_groups, default_group, expected):

    assert nlg.ResponseFetcher._select_response_group(
        groups, allowed_groups, default_group) == expected


@pytest.mark.nlg
@pytest.mark.response_fetcher
@pytest.mark.parametrize(
    "responses,response_key,channel,expected",
    [
        (test_responses, 'res1', 'collector', [
            {'text': 'text res1 default channel'}
        ]),
        (test_responses, 'res1', 'facebook', [
            {'text': 'text res1 facebook channel', 'channel': 'facebook'}
        ]),
        (test_responses, 'not_a_res', 'faceboo', []),
        (test_responses, 'utter_restart', 'collector', [{'text': ''}]),
        (test_responses, 'res2', 'facebook', [
            {
                'text': 'text res2 buttons facebook channel',
                'buttons': [
                    {'payload': 'button1', 'text': 'text facebook button1'},
                    {'payload': 'button2', 'text': 'text facebook button2'}
                ],
                'channel': 'facebook'
            }
        ]),
        (test_responses, 'res3', 'coll', [
            {'text': 'text res3 default channel variation 1'},
            {'text': 'text res3 default channel variation 2'},
        ]),
        (test_responses, 'res3', 'whatsapp', [
            {'text': 'text res3 whatsapp channel variation 1', 'channel': 'whatsapp'},
            {'text': 'text res3 whatsapp channel variation 2', 'channel': 'whatsapp'}
        ])
    ])
def test_filter_wanted_responses(responses, response_key, channel, expected):
    assert nlg.ResponseFetcher._filter_wanted_responses(
        responses, response_key, channel) == expected
