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
        }
    },
    'response' : 'res_abc'}
invalid_req = {
    'tracker': {
        'slots': {'test_slot': 'abcd'},
        'latest_message': {
            'intent': {'name': 'affirm_abcd'},
            'entities': [
                {'entity': 'test_entity', 'value': 'abcd', 'start': 0, 'end': 0}
            ]
        }
    },
    'response' : 'res_abcd'}

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
@pytest.mark.parametrize(
    "req,config,expected",
    [
        (valid_req,
         {'METHOD': 'slot', 'NAME': 'test_slot', 'VALUES': [{'NAME': 'abc'}]},
         'abc'),
        (valid_req,
         {'METHOD': 'entity', 'NAME': 'test_entity', 'VALUES': [{'NAME': 'abc'}]},
         'abc'),
        (valid_req,
         {'METHOD': 'suffix', 'SEPARATOR': '_', 'VALUES': [{'NAME': 'abc'}]},
         'abc'),
        (valid_req,
         {'METHOD': 'last_intent_suffix', 'SEPARATOR': '_', 'VALUES': [{'NAME': 'abc'}]},
         'abc'),
        (valid_req,
         {'METHOD': 'pooled', 'VALUES': [{'NAME': 'abc'}]},
         nlg.POOLED_FLAG),
        (invalid_req,
         {'METHOD': 'slot', 'NAME': 'test_slot', 'VALUES': [{'NAME': 'abc'}]},
         None),
        (invalid_req,
         {'METHOD': 'entity', 'NAME': 'test_entity', 'VALUES': [{'NAME': 'abc'}]},
         None),
        (invalid_req,
         {'METHOD': 'suffix', 'SEPARATOR': '_', 'VALUES': [{'NAME': 'abc'}]},
         None),
        (invalid_req,
         {'METHOD': 'last_intent_suffix', 'SEPARATOR': '_', 'VALUES': [{'NAME': 'abc'}]},
         None)
    ])
def test_find_wanted_group(req, config, expected):
    assert nlg.ResponseFetcher._find_wanted_group(req, **config) == expected


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

@pytest.mark.nlg
@pytest.mark.app_updater
@pytest.mark.parametrize(
    "entry,expected", [
        ({'NAME': 'abc', 'FILENAME': 'abc_responses.yml'},
         ('abc', 'abc_responses.yml', 0)),
        ({'name': 'abc', 'filename': 'abc_responses.yml'},
         ('abc', 'abc_responses.yml', 0)),
        (['abc', 'abc_responses.yml'],
         ('abc', 'abc_responses.yml', 0)),
        (('abc', 'abc_responses.yml'),
         ('abc', 'abc_responses.yml', 0)),
        (('abc', 'abc_responses.yml', 10),
         ('abc', 'abc_responses.yml', 10)),
        ({'NAME': 'abc', 'FILENAME': 'abc_responses.yml', 'TIMESTAMP': 100},
         ('abc', 'abc_responses.yml', 100)),
        ({'name': 'abc', 'FILENAME': 'abc_responses.yml'},
         ('abc', 'abc_responses.yml', 0))])
def test_parse_entry_in_config(entry, expected):
    assert nlg.NLGAppUpdater._parse_entry(entry) == expected

# @pytest.mark.nlg
# @pytest.mark.app_updater
# def test_invalid_entry_in_config_raises_parse_value_error():
#     with pytest.raises():
#         nlg.NLGAppUpdater._parse_entry(
#             {'FILENAME': 'abc_responses.yml'})

# ----- Integration tests -----

@pytest.fixture
def app():
    return sanic.Sanic('Test NLG server')

@pytest.fixture
def configured_app():
    app = sanic.Sanic('Test NLG server')
    nlg.NLGAppUpdater.configure(
        app,
        Path(
            Path(__file__).parent,
            'nlg_test_config.yml'))

    return app

@pytest.mark.nlg
def test_nlg_configure(app):
    nlg.NLGAppUpdater.configure(
        app,
        Path(
            Path(__file__).parent,
            'nlg_test_config.yml'))

    assert app.config.NLG_REFRESH == 1
    assert app.config.DEFAULT_RESPONSE == [{'text': 'default answer'}]
    assert app.config.DEFAULT_RESPONSE_GROUP == 'abc'
    for value in app.config.NLG_CONTROLS['VALUES']:
        assert value['TIMESTAMP'] == os.lstat(value['FILENAME']).st_mtime

    assert (
        app.config.RESPONSES['abc']['utter_response_1'][0]['text'] ==
        'abc Text from response 1'
    )

@pytest.mark.nlg
def test_nlg_refresh(configured_app):
    backup_path = 'backup_abc.yml'

    filename = configured_app.config.NLG_CONTROLS['VALUES'][0]['FILENAME']
    filename2 = configured_app.config.NLG_CONTROLS['VALUES'][1]['FILENAME']

    original_timestamp = configured_app.config.NLG_CONTROLS['VALUES'][0]['TIMESTAMP']
    Path(filename).touch()
    time.sleep(0.5)
    nlg.NLGAppUpdater.refresh(configured_app)

    assert configured_app.config.NLG_CONTROLS['VALUES'][0]['TIMESTAMP'] > original_timestamp

    shutil.copy(Path(filename), Path(backup_path))
    shutil.copy(Path(filename2), Path(filename))

    nlg.NLGAppUpdater.refresh(configured_app)

    shutil.move(Path(backup_path), Path(filename))

    assert (
        configured_app.config.RESPONSES['abc'] == configured_app.config.RESPONSES['xyz']
    )



    # assert app.config.NLG_REFRESH == 1
    # assert app.config.DEFAULT_RESPONSE == [{'text': 'default answer'}]
    # assert app.config.DEFAULT_RESPONSE_GROUP == 'abc'
    # for value in app.config.NLG_CONTROLS['VALUES']:
    #     assert value['TIMESTAMP'] == os.lstat(value['FILENAME']).st_mtime
    #
    # assert (
    #     app.config.RESPONSES['abc']['utter_response_1'][0]['text'] ==
    #     'abc Text from response 1'
    # )
