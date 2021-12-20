import pytest
import rasa_helpers.nlg as nlg
import sanic
import time
import os
import shutil
from pathlib import Path


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
    assert app.config.NLG_DEFAULT_VALUE == 'abc'
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
