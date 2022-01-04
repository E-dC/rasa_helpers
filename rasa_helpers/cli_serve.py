from sanic import Sanic
from sanic.log import logger
from sanic.response import json
from sanic.response import text
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from rasa_helpers.nlg import NLGAppUpdater, ResponseFetcher
from rasa_helpers.nlu import NLUAppUpdater, NLURunner

# __doc__ = """Start a NLG and/or NLU server for Rasa.
#
# Usage:
#   rasa_server.py all <config>
#   rasa_server.py nlg <config>
#   rasa_server.py nlu <config>
#
# Optional arguments:
#   -h --help                       Show this
# """

app = Sanic("NLG/NLU server")

async def nlg_tick():
    NLGAppUpdater.refresh(app)

async def initialize_nlg_scheduler(app, loop):
    scheduler = AsyncIOScheduler({'event_loop': loop})
    scheduler.add_job(
        nlg_tick, 'interval', seconds=app.config.NLG_REFRESH)
    scheduler.start()

async def get_response(request):
    res = ResponseFetcher.construct_response(app, request)
    return json(res)

async def parse_message(request):
    res = NLURunner.run(app, request)
    return json(res)

def run(args):
    nlg = args['all'] or args['nlg']
    nlu = args['all'] or args['nlu']
    config_filename = args['<config>']

    if nlg:
        NLGAppUpdater.configure(app, config_filename)
        app.register_listener(
            initialize_nlg_scheduler, 'before_server_start')
        app.add_route(
            get_response, '/nlg', frozenset({'POST'}))

    if nlu:
        NLUAppUpdater.configure(app, config_filename)
        app.add_route(
            parse_message, '/model/parse', frozenset({'POST'}))


    app.run(
        host=app.config.HOST,
        port=app.config.PORT)
