import asyncio

from ab_plugin_manager.extensions.jobs import job_op
from ab_plugin_manager.magic_plugin import step_name

name = 'job_calculate_revenue'
version = '0.0.1'


@step_name('calculate-daily-revenue')
@job_op.implementation
async def calculate_revenue():
    print('Calculating daily revenue...')
    await asyncio.sleep(3)
    print('It\'s 0. What did you expect?')
