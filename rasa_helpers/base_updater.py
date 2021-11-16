
import os
import collections
import ruamel.yaml as yaml
from sanic.log import logger

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
    def _base_refresh(cls, app, caller):
        """ Update the app responses if a newer version is available.

            Details:
                `app` MUST have been configured once beforehand.
                `app` is modified in-place.
            Args:
                app (sanic.Sanic): Sanic app to configure

            Returns:
                True if app was updated
        """
        if caller == 'nlg':
            output_key = 'RESPONSES'
            controls_key = 'NLG_CONTROLS'
            content_type = 'responses'
        elif caller == 'nlu':
            output_key = 'MODELS'
            controls_key = 'NLU_CONTROLS'
            content_type = 'model'

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

        return updated

    @classmethod
    def _base_configure(cls, app, config_filename, caller):
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

        if caller == 'nlg':
            app.config.update({'NLG_CONTROLS': config['NLG_CONTROLS']})
        elif caller == 'nlu':
            app.config.update({'NLU_CONTROLS': config['NLU_CONTROLS']})

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
            logger.warning(
                'NLU and NLG configs have different network parameters')
            logger.warning(
                f'HOST parameters ({host} vs {config_host}) must be identical')
            logger.warning(
                f'PORT parameters ({port} vs {config_port}) must be identical')
            logger.warning(
                f'HOST will be {config_host} and PORT will be {config_port}')
            logger.warning(
                'If you wish to have different hosts and ports, you\'ll need to start two separate apps, each with their own config.')
            pass

        app.config.HOST = config_host
        app.config.PORT = config_port

        return None
