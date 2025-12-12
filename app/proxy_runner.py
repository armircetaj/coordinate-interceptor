import threading
import queue
import sys
import asyncio
import mitmproxy.options
import mitmproxy.tools.dump

class ProxyRunner:
    def __init__(self, port=8080):
        self.port = port
        self.master = None
        self.thread = None
        self.loop = None
        self.orig_stdout = None
        self.should_stop = threading.Event()
        # Limit queue size to prevent memory issues
        self.q = queue.Queue(maxsize=1000)

    def _stdout_wrapper(self):
        self.orig_stdout = sys.stdout
        orig = self.orig_stdout
        class W:
            def write(_, s):
                # Only queue non-empty lines to prevent queue overflow
                if s.strip():
                    line = s.strip()
                    try:
                        # Use non-blocking put to prevent queue from filling up
                        self.q.put(line, block=False)
                    except queue.Full:
                        pass  # Drop if queue is full to prevent blocking/memory issues
                orig.write(s)
            def flush(_):
                orig.flush()
            def isatty(_):
                return orig.isatty()
            def fileno(_):
                return orig.fileno()
        sys.stdout = W()

    def _run_proxy(self):
        """Run the mitmproxy master in a new event loop."""
        self._stdout_wrapper()
        opts = mitmproxy.options.Options()
        opts.listen_port = self.port
        opts.listen_host = '127.0.0.1'
        
        # Create event loop for this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        async def setup_and_run():
            # Create DumpMaster within the running event loop context
            # This way get_running_loop() will find the loop
            master = mitmproxy.tools.dump.DumpMaster(opts)
            import app.interceptor as interceptor
            for a in interceptor.addons:
                master.addons.add(a)
            self.master = master
            # run() is a coroutine in mitmproxy - it runs until shutdown is called
            try:
                if asyncio.iscoroutinefunction(master.run):
                    await master.run()
                else:
                    master.run()
            except asyncio.CancelledError:
                pass
            finally:
                # Ensure master is properly shut down
                try:
                    if master:
                        master.shutdown()
                except Exception:
                    pass
        
        # Run the async setup and execution
        try:
            self.should_stop.clear()
            self.loop.run_until_complete(setup_and_run())
        except Exception as e:
            print(f"Proxy error: {e}", flush=True)
        finally:
            # Restore stdout
            if self.orig_stdout:
                sys.stdout = self.orig_stdout
            # Clean up event loop
            try:
                if self.loop and not self.loop.is_closed():
                    # Cancel any remaining tasks
                    pending = asyncio.all_tasks(self.loop)
                    for task in pending:
                        task.cancel()
                    # Give tasks a chance to clean up
                    if pending:
                        self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    self.loop.close()
            except Exception:
                pass
            finally:
                self.loop = None
                self.master = None

    def start(self):
        if self.master:
            return False
        self.thread = threading.Thread(target=self._run_proxy, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        if not self.master and not self.thread:
            return False
        
        # Signal shutdown
        self.should_stop.set()
        
        # Shutdown the master if it exists
        if self.master:
            try:
                self.master.shutdown()
            except Exception:
                pass
        
        # Stop the event loop if it's running
        if self.loop and self.loop.is_running():
            try:
                # Stop the loop from another thread
                self.loop.call_soon_threadsafe(self.loop.stop)
            except Exception:
                pass
        
        # Wait for thread to finish (with timeout)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)
            if self.thread.is_alive():
                # Thread didn't stop gracefully, log warning
                print("Warning: Proxy thread did not stop gracefully", flush=True)
        
        # Restore stdout if still wrapped
        if self.orig_stdout and sys.stdout != self.orig_stdout:
            sys.stdout = self.orig_stdout
        
        self.master = None
        self.loop = None
        return True

    def get_stdout_line(self):
        try:
            return self.q.get_nowait()
        except queue.Empty:
            return None
