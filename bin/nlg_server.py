from docopt import docopt
from sanic import Sanic
from sanic.log import logger
from sanic.response import json
from sanic.response import text
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from rasa_helpers.nlg import AppUpdater, ResponseFetcher


__doc__ = """Start a Natural Language Generation server for Rasa.

Usage:
  nlg_server.py <config>

Optional arguments:
  -h --help                       Show this
"""

app = Sanic("NLG server")

async def tick():
    AppUpdater.refresh(app)

@app.listener('before_server_start')
async def initialize_scheduler(app, loop):
    scheduler = AsyncIOScheduler({'event_loop': loop})
    scheduler.add_job(
        tick, 'interval', seconds=app.config.REFRESH)
    scheduler.start()

@app.post("/nlg")
async def get_response(request):
    res = ResponseFetcher.construct_response(app, request)
    return json(res)

if __name__ == '__main__':
    args = docopt(__doc__)
    config_filename = args['<config>']
    AppUpdater.configure(app, config_filename)

    app.run(
        host=app.config.HOST,
        port=app.config.PORT)
