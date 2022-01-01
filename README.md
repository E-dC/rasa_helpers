# `rasa_helpers`
⚠️ The package is still in its infancy, and unstable ⚠️

`rasa_helpers` is a collection of tools useful for the development and testing of conversational agents based on Rasa.  
So far it consists in three separate tools, more or less polished/finished.

## Table of contents
* [General info](#general-info)
* [Setup](#setup)
* [Building story trackers for testing](#story-trackers-for-testing)
* [Checking domain and data consistency](#checking-domain-and-data-consistency)
* [Configurable NLG and NLU server](#configurable-nlg-and-nlu-server)


## General info
You may find some or all the tools useful if you are looking to:
 - Test Rasa actions code with `Tracker` objects, built from regular Rasa stories
 - Check consistency between your domain and data files _before_ training models
 - Support switching between multiple sets of responses based on some slot value, entity, identifier...  (NLG server)
 - Support switching between multiple NLU models trained with Rasa, based on the output of some of your own code

## Setup

### Dependencies
- `rasa >= 2.8.0`
- `ruamel.yaml >= 0.16.13`
- `mypy-extensions >= 0.4.3`

Note about Rasa: the way models are stored changes from `2.7` to `2.8`, meaning that if you're using a version of Rasa from before `2.8`, the NLU server tool most likely won't work (see https://rasa.com/docs/rasa/2.x/migration-guide#rasa-27-to-28).  

Rasa 3 _is_ supported by the NLU server tool.

### Install

(Navigate to your bot directory, activate your virtual environment)

```bash
git clone https://github.com/E-dC/rasa_helpers.git # or git@github.com:E-dC/rasa_helpers.git
cd rasa_helpers
pip install -e .
```

### Unit tests
If you would like to run the unit tests, you'll need `pytest` and `pytest-cov` (for code coverage). You can install it with  
```bash
pip install pytest pytest-cov
```  

Run the tests with `pytest`. If it doesn't work, try `python3 -m pytest`.

You will likely see at least a couple of tests fail because I have not placed the models used for testing in this repository (too heavy). To deselect them when testing, run  
```bash
pytest -m 'not models_needed'
```

## Story trackers for testing

`tracker_builder` automates the creation of the `dispatcher` (easy), `tracker` (handy) and `domain` (for now, an empty dictionary) objects necessary to run custom actions.  
This is done by reading a story (YAML only) file containing the scenarios to use when testing actions.

### Usage

First, create test stories including the actions to test:

```yaml
version: '2.0'
stories:

# expects SlotSet("my_counter", 1)
- story: test_action_increment_counter
  steps:
    - intent: increment_counter
    - action: utter_i_will_increment_the_counter
    - action: action_increment_counter


# Metadata can be given to initialise slots, set the latest message, etc:

# expects SlotSet("my_counter", 6)
- story: test_action_increment_counter
  metadata:
    latest_message:
      text: "Please increment the counter!"
    slots:
      my_counter: 5
  steps:
    - intent: increment_counter
    - action: utter_i_will_increment_the_counter
    - action: action_increment_counter
```

Then write a `pytest` fixture which instantiates a TestTrackerStore object, reading all the stories from the file just created:

```python
import pytest
from rasa_helpers.tracker_builder import TestTracker, TestTrackerStore
from actions import actions

@pytest.fixture(scope='module')
def tracker_store():
    tracker_store = TestTrackerStore('unit_test_stories.yml')
    return tracker_store
```

Finally, in your unit tests call the `initialise_all` method with the desired story name to obtain a tuple of the structures necessary to run regular actions:

```python
@pytest.mark.action
def test_action_increment_counter(tracker_store):
    obj = actions.IncrementCounter()
    dispatcher, tracker, domain = tracker_store.initialise_all('test_action_increment_counter')
    assert obj.run(dispatcher, tracker, domain) == [SlotSet('my_counter', 1)]

```

## Checking domain and data consistency
`find_elements_missing_from_domain.py` is a stand-alone script, which... finds elements in the data but missing from the domain (and vice-versa)... This is to avoid beginning to train a model and realising halfway through that it crashed. This tool might not be useful any more with Rasa 3, but I haven't checked yet.

### Usage
```bash
find_elements_missing_from_domain.py [<data-files>...] [--domain DOMAIN]
```
If no arguments are given, the script will look for YAML files in `./data` and for a domain file `./domain.yml`.


## Configurable NLG and NLU server
This is by far the most polished tool in the lot, and probably the most useful. The goal of this custom NLG and NLU server is to make it easier to work with multiple sets of responses, and multiple NLU models.
The script name is `nlg_nlu_server.py`, until I find a better name.

### NLG

#### Overview
The typical use case is when you want to show different content to the chatbot user based on a specific slot or entity value.  
For example, your conversational agent could answer questions for users coming from two countries. You could maintain a single set of responses:

```yaml
# responses.yml
responses:
  response1_country1:
    - text: "Text response1 country1"
  response1_country2:
    - text: "Text response1 country2"
  response2_country1:
    - text: "Text response2 country1"
  response2_country2:
    - text: "Text response2 country2"
# ...
```
or maintain two sets of responses, and switch between them based on the value of a `country` slot:
```yaml
# responses_country1.yml
responses:
  response1:
    - text: "Text response1 country1"
  response2:
    - text: "Text response2 country1"
#...
```

```yaml
# responses_country2.yml
responses:
  response1:
    - text: "Text response1 country2"
  response2:
    - text: "Text response2 country2"
#...
```

This is now possible in Rasa directly (condition on slot values in responses, for example): https://rasa.com/docs/rasa/responses#conditional-response-variations  
Use that if you only have a few responses which vary based on slot value, it's easier.  

Still, you might find some advantages to using this NLG server, for example:
  - Your response variations are conditioned on entity value instead of slot value (doesn't seem to be currently possible with Rasa)
  - _All_ or _most_ of your responses must vary based on a slot or entity value
  - You are using the custom NLU server to make your bot multilingual

#### Usage
1. Create separate response files for each possible slot or entity value.
2. Write a config file, using the one in the `examples` directory as a guide (more documentation coming soon).
3. Run the server with `nlg_nlu_server.py nlg <config_path>`

### NLU

#### Overview
The tool allows you to easily work with several NLU models trained with Rasa, and switch between them with custom code.
This is useful when building a multilingual conversational agent, where the user must be able to switch back and forth between two or more languages within the same session.  
I guess you could also use it in a monolingual bot, perhaps as a way to use several specialised NLU models?

#### Usage
1. Train separate NLU only models
2. Implement chooser code, using `tests/chooser_code.py` as a guide (more documentation coming soon)
3. Write a config file, using the one in the `examples` directory as a guide (more documentation coming soon).
4. Run the server with `nlg_nlu_server.py nlu <config_path>`

##### Can't I just use a slot value to choose the model?
As far as I'm aware, no.
The Rasa agent only sends the message text, the conversation ID, and the sender ID to the NLU server.  
This means the NLU server won't have access to the slot values, the previous turns of the conversation, or anything like that.  


### Use case: Multilingual bot with both NLG and NLU

1. Create separate response files, one per language
2. Train one NLU model per language, and a single Core model for all languages
3. Implement a language identification (LI) model to predict which model to use
4. Write a small module which
  - loads the language identification model
  - provides `rasa_helpers` with a function to call the model
5. Write the config file (one config file for both NLU and NLG)
6. Run the server `nlg_nlu_server.py all <config_path>`

When a message arrives to the NLU server:
1. The language of the message is predicted
2. The corresponding NLU model is used to predict intent and entities
3. The NLU server sends back the model's response to the agent, _but adds the prediction of the LI model as a zero-width entity_

Step 3 amends the response to be sent so that the NLG server knows which set of responses it must draw the response from.
This is done as an entity because the response expected by the agent only contains:
- The message text
- The intent predicted (and confidence)
- The intent ranking
- The entities predicted

Once this is done, the next action to take will be predicted by the Core model, and finally the NLG server will be contacted when retrieving responses.  
The NLG server will find the LI model prediction stored in the latest message's entities, and use that to select the correct set of responses.
