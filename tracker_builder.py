
from collections import ChainMap

import typing
from typing import Text, List, Any, Dict, Tuple, Optional, Union
from mypy_extensions import TypedDict

import ruamel.yaml as yaml

from rasa.shared.core.training_data.story_reader.yaml_story_reader import YAMLStoryReader, StoryStep
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher

SenderId = Optional[Text]
LatestMessage = Optional[Dict[Text, Any]]
FollowupAction = Optional[Text]
LatestActionName = Optional[Text]
Paused = bool
Slots = Dict[Text, Any]
ActiveLoop = Dict[Text, Text]

Config = TypedDict(
    'Config',
    {
        'sender_id': SenderId,
        'latest_message': LatestMessage,
        'followup_action': FollowupAction,
        'latest_action_name': LatestActionName,
        'paused': Paused,
        'slots': Slots,
        'active_loop': ActiveLoop
    },
    total = False)


GLOBAL_CONFIG = {
    'sender_id': 'default_sender',
    'slots': {
        'feedback_form_completed': False,
        'last_request_counter': 0
    },
    'latest_message': None,
    'paused': False,
    'followup_action': None,
    'active_loop': {},
    'latest_action_name': None
}

class TestTracker(Tracker):
    def __init__(self, events: List[Dict[Text, Any]], config: Config):

        kwargs = {'events': events, **config}

        if not kwargs['latest_action_name']:
            kwargs['latest_action_name'] = self._get_latest_action_name(events)

        super().__init__(**kwargs)

    def _get_latest_action_name(self, events: List[Dict[Text, Any]]) -> Optional[Text]:
        for ev in reversed(events):
            try:
                return ev['action_name']
            except KeyError:
                continue
        else:
            return None

class TestTrackerStore(object):

    reader = YAMLStoryReader()

    def __init__(self, *filenames: str):
        """ Collect test stories and configs from file so that we can
            easily initialise each TestTracker"""

        self.story_events = {}
        self.story_configs = {}
        self.trackers = {}
        self.name2struct = {
            'events': self.story_events,
            'config': self.story_configs,
            'tracker': self.trackers
        }

        for filename in filenames:
            data = self.parse_file(filename)
            file_config = data.get('file_config', {})

            for story_steps, story_config in self.retrieve_stories(data):
                story_name = self.find_story_name(story_steps)
                self.story_events[story_name] = [v.as_dict() for v in story_steps.events]
                self.story_configs[story_name] = self.build_config(
                    GLOBAL_CONFIG, file_config, story_config)

    @classmethod
    def find_story_name(cls, obj: Union[StoryStep, Dict[Text, Any]]) -> Text:
        try:
            return obj.block_name
        except AttributeError:
            return obj['story']

    @classmethod
    def parse_file(cls, filename: Text) -> Dict[Text, Any]:
        with open(filename, 'r') as f:
            return yaml.safe_load(f)

    @classmethod
    def retrieve_stories(
            cls, data: Dict[Text, Any]) -> List[Tuple[StoryStep, Config]]:
        return zip(cls.retrieve_story_steps(data), cls.retrieve_story_configs(data))

    @classmethod
    def retrieve_story_steps(cls, data: Dict[Text, Any]) -> List[StoryStep]:
        return cls.reader.read_from_parsed_yaml(data)

    @classmethod
    def retrieve_story_configs(cls, data: Dict[Text, Any]) -> List[Config]:
        return [x.get('metadata', {}) for x in data['stories']]

    @classmethod
    def build_config(
            cls,
            global_config: Config,
            file_config: Config,
            story_config: Config) -> ChainMap:

        return ChainMap(story_config, file_config, global_config)

    def _get_story_object(
            self,
            story_name: Text,
            category: Text) -> Union[List[Dict[Text,Any]], Config]:

        try:
            container = self.name2struct[category]
        except KeyError:
            raise KeyError(
                f'Unknown `category` when grabbing story events or configs: {category}')

        try:
            return container[story_name]
        except KeyError:
            raise KeyError(
                f'Unit-testing story {category} for `{story_name}` could not be found')

    def get_story_events(self, story_name: Text) -> List[Dict[Text,Any]]:
        return self._get_story_object(story_name, 'events')

    def get_story_config(
            self,
            story_name: Text,
            use_global_config: bool) -> Config:
        if use_global_config:
            return GLOBAL_CONFIG
        return self._get_story_object(story_name, 'config')

    def get_test_tracker(self, story_name: Text) -> TestTracker:
        return self._get_story_object(story_name, 'tracker')

    def initialise_test_tracker(
            self,
            story_name: Text,
            use_global_config: bool = False) -> TestTracker:

        events = self.get_story_events(story_name)
        config = self.get_story_config(story_name,
                                       use_global_config=use_global_config)

        self.trackers[story_name] = TestTracker(events=events, config=config)
        return self.trackers[story_name]

    def initialise_dispatcher(
            self, story_name: Text) -> CollectingDispatcher:
        return CollectingDispatcher()

    def initialise_all(
            self,
            story_name: Text,
            use_global_config: bool = False) -> Tuple[CollectingDispatcher, TestTracker, Dict[Text, Any]]:

        return (self.initialise_dispatcher(story_name),
                self.initialise_test_tracker(story_name, use_global_config),
                {})

