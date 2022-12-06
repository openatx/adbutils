#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Fri Dec 02 2022 17:00:03 by codeskyblue
"""

import pytest
from adbutils import StopEvent

def test_stop_event():
    stop_event = StopEvent()
    assert stop_event.is_stopped() == False
    
    stop_event.stop()
    assert stop_event.is_stopped() == False
    
    with pytest.raises(TimeoutError):
        stop_event.stop_wait(timeout=.1)
    assert stop_event.is_stopped() == False

    stop_event.done()
    assert stop_event.is_stopped() == True