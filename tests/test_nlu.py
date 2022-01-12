import pytest
import rasa_helpers.nlu as nlu
import sanic
import time
import os
import shutil
import inspect
import asyncio
from pathlib import Path


@pytest.fixture(scope='module')
@pytest.mark.nlu
@pytest.mark.slow
@pytest.mark.models_needed
def agent():
    if nlu.RASA_MAJOR_VERSION == 2:
        filename = 'nlu_model-eng.tar.gz'
    elif nlu.RASA_MAJOR_VERSION == 3:
        filename = 'nlu_model-test_rasa_3.tar.gz'
    filepath = str(
        Path(Path(__file__).parent,
             'models',
             filename).absolute())

    agent = nlu.NLUAppUpdater._load_updated_data(filepath)
    return agent


@pytest.mark.nlu
@pytest.mark.slow
@pytest.mark.models_needed
def test_model_loading(agent):
    assert hasattr(agent, 'predict_intent')
    assert callable(agent.predict_intent)
    assert 'message' in inspect.signature(agent.predict_intent).parameters


@pytest.mark.nlu
@pytest.mark.slow
@pytest.mark.models_needed
def test_extract_labels_from_model(agent):
    labels = nlu.NLUAppUpdater._extract_labels_from_model(agent)

    assert isinstance(labels, set)
    assert 'greet' in labels and 'goodbye' in labels


@pytest.mark.nlu
@pytest.mark.slow
@pytest.mark.models_needed
def test_predict_intent(agent):

    labels = nlu.NLUAppUpdater._extract_labels_from_model(agent)
    r = asyncio.run(agent.predict_intent(message='Hello world!'))
    assert isinstance(r, dict)
    assert r['intent']['name'] in labels




# ----- Integration tests -----

# @pytest.fixture
# def app():
#     return sanic.Sanic('Test NLU server')
#
# @pytest.fixture
# def configured_app():
#     app = sanic.Sanic('Test NLU server')
#     # Config name says 'nlg' but includes both NLG and NLU settings
#     nlu.NLUAppUpdater.configure(
#         app,
#         Path(
#             Path(__file__).parent,
#             'nlg_test_config.yml'))
#
#     return app
#
# @pytest.mark.nlu
# def test_nlu_configure(app):
#     nlu.NLUAppUpdater.configure(
#         app,
#         Path(
#             Path(__file__).parent,
#             'nlg_test_config.yml'))
#
#     assert app.config.NLU_REFRESH == 1
#     assert app.config.DEFAULT_RESPONSE == [{'text': 'default answer'}]
#     assert app.config.DEFAULT_RESPONSE_GROUP == 'abc'
#     for value in app.config.NLU_CONTROLS['VALUES']:
#         assert value['TIMESTAMP'] == os.lstat(value['FILENAME']).st_mtime
#
#     # assert (
#     #     app.config.RESPONSES['abc']['utter_response_1'][0]['text'] ==
#     #     'abc Text from response 1'
#     # )
#
# @pytest.mark.nlu
# def test_nlu_refresh(configured_app):
#     backup_path = 'backup_abc.yml'
#
#     filename = configured_app.config.NLU_CONTROLS['VALUES'][0]['FILENAME']
#     filename2 = configured_app.config.NLU_CONTROLS['VALUES'][1]['FILENAME']
#
#     original_timestamp = configured_app.config.NLU_CONTROLS['VALUES'][0]['TIMESTAMP']
#     Path(filename).touch()
#     time.sleep(0.5)
#     nlu.NLUAppUpdater.refresh(configured_app)
#
#     assert configured_app.config.NLU_CONTROLS['VALUES'][0]['TIMESTAMP'] > original_timestamp
#
#     shutil.copy(Path(filename), Path(backup_path))
#     shutil.copy(Path(filename2), Path(filename))
#
#     nlu.NLUAppUpdater.refresh(configured_app)
#
#     shutil.move(Path(backup_path), Path(filename))
#
#     # assert (
#     #     configured_app.config.RESPONSES['abc'] == configured_app.config.RESPONSES['xyz']
#     # )
#     #
