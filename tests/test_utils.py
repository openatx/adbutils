#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Fri Dec 02 2022 17:00:03 by codeskyblue
"""

import pytest
from adbutils import StopEvent
from adbutils._utils import get_free_port


def test_stop_event():
    stop_event = StopEvent()
    assert stop_event.is_stopped() == False
    
    stop_event.stop_nowait()
    assert stop_event.is_stopped() == True
    assert stop_event.is_done() == False

    with pytest.raises(TimeoutError):
        stop_event.stop(timeout=.1)
    assert stop_event.is_stopped() == True
    assert stop_event.is_done() == False

    stop_event.done()
    assert stop_event.is_done() == True


def test_get_free_port():
    port = get_free_port()
    assert port > 0