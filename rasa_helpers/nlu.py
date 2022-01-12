import os
import sys
import importlib
import json
import re
import ruamel.yaml as yaml

import rasa
from rasa.core.agent import Agent
RASA_MAJOR_VERSION = int(rasa.__version__[0])

from sanic.log import logger
from .base_updater import AppUpdater, DEFAULT_VALUE_FLAG

class NLUAppUpdater(AppUpdater):

    @classmethod
    def _build_parse_function(cls, agent):
        if RASA_MAJOR_VERSION == 2:
            return lambda message: agent.parse_message_using_nlu_interpreter(
                message_data=message)
        elif RASA_MAJOR_VERSION == 3:
            return lambda message: agent.parse_message(
                message_data=message)

    @classmethod
    def _load_updated_data(cls, filename):
        """Load Rasa NLU model from a file.

            Args:
                filename (str): Model filename

            Returns:
                rasa.nlu.model.Interpreter loaded
        """
        agent = Agent.load(model_path=filename)
        agent.predict_intent = cls._build_parse_function(agent)

        return agent

    @classmethod
    def _load_chooser_code(cls, filepath, fname):
        """ Load user code to switch between NLU models.

            Details:
                If the config is:

                NLU_CONTROLS:
                    MODEL_CHOOSER:
                        FILEPATH: 'chooser_code.py'
                        FUNCTION: 'chooser'
                    VALUES:
                        - NAME: eng
                          FILENAME: ....
                        - NAME: fra
                          FILENAME: ....

                Then the user must be implement a function `chooser` in
                `chooser_code.py`, and `chooser` must take some text as an input,
                and returns a tuple (label, confidence) where
                label is either 'eng' or 'fra', and confidence is a float.
                These labels will allow the server to choose the suitable NLU model.
                The confidence is included for possible future improvements.

            Args:
                filepath (str): Path to the source code to load
                fname (str): Name of the function to use for switching
                    between models.

            Returns:
                a function

        """
        module_name = 'user_chooser'
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        return sys.modules[module_name].__dict__[fname]

    @classmethod
    def _extract_labels_from_model(cls, loaded_model):
        if RASA_MAJOR_VERSION == 2:
            for component in loaded_model.interpreter.interpreter.pipeline:
                try:
                    return {v for k, v
                            in component.index_label_id_mapping.items()}
                except AttributeError:
                    pass
        elif RASA_MAJOR_VERSION == 3:
            return set(loaded_model.domain.intents)

    @classmethod
    def _find_all_model_labels(cls, app):
        labels = set()
        # This is to avoid processing the DEFAULT_VALUE_FLAG model
        models = [app.config['MODELS'][key]
                  for key in set(app.config['MODELS'].keys())]
        for loaded_model in models:
            labels.update(
                cls._extract_labels_from_model(loaded_model))
        return labels

    @classmethod
    def refresh(cls, app):
        """ Update the app responses if a newer version is available.

            Details:
                `app` MUST have been configured once beforehand.
                `app` is modified in-place.
                `MODELS` field of app config will look like:
                    switching_value1: loaded interpreter for switching_value1
                    switching_value2: loaded interpreter for switching_value2

            Args:
                app (sanic.Sanic): Sanic app to configure

            Returns:
                None
        """

        updated = super().refresh(app, caller='NLU')
        if updated:
            app.config['NLU_LABELS'] = cls._find_all_model_labels(app)
            l = '|'.join(app.config['NLU_LABELS'])
            app.config['NLU_CHOOSER_BYPASSER'] = re.compile(f'/({l})')

        return None

    @classmethod
    def configure(cls, app, config_filename):
        """ Setup the app when first starting the NLU server.

            Details:
                `app` is modified in-place.
                The config settings are stored in `app.config`.

            Args:
                app (sanic.Sanic): Sanic app to configure
                config_filename (str): NLU config to use

            Returns:
                None

        """
        super().configure(app, config_filename, caller='NLU')

        app.config['MODELS'] = {}
        app.config.NLU_CHOOSER = cls._load_chooser_code(
            app.config.NLU_CONTROLS['MODEL_CHOOSER']['FILEPATH'],
            app.config.NLU_CONTROLS['MODEL_CHOOSER']['FUNCTION']
        )

        cls.refresh(app)

        return None

class NLURunner(object):

    @classmethod
    def _unpack_request(cls, request):
        return request.json['text']

    @classmethod
    async def _amend_response(cls, app, response, label, confidence):
        logger.debug(response)
        response = await response

        response['entities'].append({
            'start': 0,
            'end': 0,
            'value': label,
            'entity': app.config['NLU_CONTROLS']['NAME'],
            'confidence': confidence
        })

        return response

    @classmethod
    def _bypass_nlu(cls, app, message):
        return re.match(
            pattern=app.config['NLU_CHOOSER_BYPASSER'],
            string=message.strip()
        )

    @classmethod
    def run_chooser(cls, app, message):
        if cls._bypass_nlu(app, message):
            o = (DEFAULT_VALUE_FLAG, 1)
        else:
            o = app.config['NLU_CHOOSER'](message)

            # try:
            #     assert o[0] in app.config.MODELS.keys()
            # except AssertionError:
            #     logger.error(
            #         f'{o[0]} is not in the allowable labels {app.config.MODELS.keys()}')
            #     raise AssertionError
        return o

    @classmethod
    def run_intent_classification(cls, app, label, message):
        return app.config.MODELS[label].predict_intent(message)

    @classmethod
    def run(cls, app, request):
        message = cls._unpack_request(request)
        label, confidence = cls.run_chooser(app, message)
        response_cl = cls.run_intent_classification(app, label, message)
        response = cls._amend_response(app, response_cl, label, confidence)

        return response
