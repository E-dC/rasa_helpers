import os
import collections
import ruamel.yaml as yaml
from sanic.log import logger

DEFAULT_VALUE_FLAG = 'unk'

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
    def _load_updated_data(cls, *args, **kwargs):
        raise NotImplemented(
            '`_load_updated_data` must be implemented in child classes')

    @classmethod
    def refresh(cls, app, caller):
        """ Update the app responses if a newer version is available.

            Details:
                `app` MUST have been configured once beforehand.
                `app` is modified in-place.
            Args:
                app (sanic.Sanic): Sanic app to configure

            Returns:
                True if app was updated
        """
        if caller == 'NLG':
            output_key = 'RESPONSES'
            controls_key = 'NLG_CONTROLS'
            content_type = 'responses'
        elif caller == 'NLU':
            output_key = 'MODELS'
            controls_key = 'NLU_CONTROLS'
            content_type = 'model'
        default_key = f'{caller}_DEFAULT_VALUE'

        try:
            assert len(app.config[output_key]) == 0
            msg = 'First-time loading {content_type} for {key} from {filename}'
        except AssertionError:
            msg = '{key} {content_type} have changed, loading new data from {filename}'
        except KeyError:
            logger.error('app was not configured before calling `refresh` method')
            raise

        updated = False
        for idx, value in enumerate(app.config[controls_key]['VALUES']):
            # timestamp should be 0 if loading for the first time
            key, filename, timestamp = cls._parse_entry(value)
            stale, latest_timestamp = cls._is_stale(filename, timestamp)

            if stale:
                logger.info(msg.format(
                    key=key, filename=filename, content_type=content_type))
                app.config[output_key][key] = cls._load_updated_data(filename)
                app.config[controls_key]['VALUES'][idx]['TIMESTAMP'] = (latest_timestamp)
                updated = True

        if updated:
            app.config[output_key][DEFAULT_VALUE_FLAG] = (
                app.config[output_key][app.config[default_key]]
            )

        return updated

    @classmethod
    def _configure_network(cls, app, config, caller):

        host = app.config.get('HOST', None)
        port = app.config.get('PORT', None)
        config_host = config['NETWORK']['HOST']
        config_port = config['NETWORK']['PORT']

        try:
            if host:
                assert host == config_host
            if port:
                assert port == config_port
        except AssertionError:
            logger.error(
                'NLU and NLG configs have different network parameters')
            logger.error(
                f'HOST parameters ({host} vs {config_host}) must be identical')
            logger.error(
                f'PORT parameters ({port} vs {config_port}) must be identical')
            logger.warning(
                f'{caller} config will be used, and so HOST will be {config_host} and PORT will be {config_port}')
            logger.warning(
                'If you wish to have different hosts and ports, you\'ll need to start two separate apps, each with their own config.')
            pass

        app.config.HOST = config_host
        app.config.PORT = config_port

        return None

    @classmethod
    def _configure_default(cls, app, caller):
        if len(app.config[f'{caller}_CONTROLS']['VALUES']) > 1:
            app.config[f'{caller}_DEFAULT_VALUE'] = (
                app.config[f'{caller}_CONTROLS']['DEFAULT_VALUE'])
        else:
            app.config[f'{caller}_DEFAULT_VALUE'] = (
                app.config[f'{caller}_CONTROLS']['VALUES'][0]['NAME'])

        return None


    @classmethod
    def configure(cls, app, config_filename, caller):
        """ Setup the app when first starting the server.

            Details:
                `app` is modified in-place.
                The config settings are stored in `app.config`.

            Args:
                app (sanic.Sanic): Sanic app to configure
                config_filename (str): config to use

            Returns:
                None

        """

        config = cls._load_yaml(config_filename)

        assert caller in {'NLG', 'NLU'}
        app.config.update({f'{caller}_CONTROLS': config[f'{caller}_CONTROLS']})
        app.config[f'{caller}_REFRESH'] = app.config[f'{caller}_CONTROLS']['REFRESH']

        cls._configure_network(app, config, caller)
        cls._configure_default(app, caller)

        return None
