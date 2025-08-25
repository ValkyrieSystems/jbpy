import asyncio
import contextlib
import os
import pathlib
import queue
import threading

from aiohttp import web


def find_jitcs_test_files():
    # See https://jitc.fhu.disa.mil/projects/nitf/testdata.aspx
    root_dir = os.environ.get("JBPY_JITC_QUICKLOOK_DIR")
    files = []
    if root_dir is not None:
        root_dir = pathlib.Path(root_dir)
        files += list(root_dir.glob("**/*.NTF"))
        files += list(root_dir.glob("**/*.ntf"))
    return files


# Python's built in http.server does not support the Range header.  aoihttp does
def _run_aiohttp_server(app, loop, ready_event, stop_event, msg_queue):
    asyncio.set_event_loop(loop)
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, "127.0.0.1", 8080)
    loop.run_until_complete(site.start())

    ready_event.set()
    msg_queue.put(site.name)
    # Wait for the stop event to be set
    loop.run_until_complete(stop_event.wait())

    # Cleanup when stop event is set
    loop.run_until_complete(runner.cleanup())
    loop.close()


@contextlib.contextmanager
def static_http_server(static_dir):
    ready_event = threading.Event()
    stop_event = asyncio.Event()
    msg_queue = queue.Queue()

    app = web.Application()
    app.add_routes([web.static("/", static_dir)])

    loop = asyncio.new_event_loop()
    thread = threading.Thread(
        target=_run_aiohttp_server,
        args=(app, loop, ready_event, stop_event, msg_queue),
        daemon=True,
    )
    thread.start()

    if ready_event.wait(timeout=10):
        url = msg_queue.get()
        yield url

    loop.call_soon_threadsafe(stop_event.set)
    thread.join()
