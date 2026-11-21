"""Every test run keeps the call log and traces out of .progress/ and off the network."""

import os

os.environ["LANTERN_CALL_LOG"] = ""
os.environ["LANTERN_TRACE"] = "0"
os.environ["LANTERN_PREDICT"] = "0"
