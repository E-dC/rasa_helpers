from docopt import docopt
from sanic import Sanic
from sanic.log import logger
from sanic.response import json
from sanic.response import text
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from rasa_helpers.nlg import NLGAppUpdater, ResponseFetcher


__doc__ = """Start a Natural Language Generation server for Rasa.

Usage:
  nlg_server.py <config>

Optional arguments:
  -h --help                       Show this
"""

app = Sanic("NLG server")

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

if __name__ == '__main__':
    args = docopt(__doc__)
    config_filename = args['<config>']

    nlg = True
    if nlg:
        NLGAppUpdater.configure(app, config_filename)
        app.register_listener(
            initialize_nlg_scheduler, 'before_server_start')
        app.add_route(
            get_response, '/nlg', frozenset({'POST'}))

    app.run(
        host=app.config.HOST,
        port=app.config.PORT)
