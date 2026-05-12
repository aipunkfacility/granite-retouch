try:
    from retouch.config import DEFAULTS
    print("DEFAULTS imported")
    from retouch.processing.pipeline import PipelineContext
    print("PipelineContext imported")
    import pytest
    print("pytest imported")
    print("All good")
except Exception as e:
    import traceback
    traceback.print_exc()
