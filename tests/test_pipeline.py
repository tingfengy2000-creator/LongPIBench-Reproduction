import json
import logging
from types import SimpleNamespace
import pytest

from repro.pipeline import run_debug_case
from test_scoring import parse_json_response, score_response


def example():
    return {'suite': 'email', 'goal': '0', 'item_id': 0, 'system_prompt': 'trusted task', 'data_prompt': 'synthetic document + injected text'}


def run(**kwargs):
    return run_debug_case(example(), parse=parse_json_response, score=score_response, **kwargs)


class Target:
    def __init__(self): self.calls = []
    def query(self, system, data):
        self.calls.append((system, data))
        return json.dumps({'summary': 'Synthetic normal summary', 'response': 'Synthetic response'})


def test_not_detected_passes_original_input_and_skips_locator():
    target = Target()
    def unexpected(*args): raise AssertionError('Locator must not be called')
    result = run(condition='promptlocate', target=target,
                 detector=SimpleNamespace(detect=lambda text: 0),
                 locator=SimpleNamespace(locate_and_recover=unexpected))
    assert target.calls == [('trusted task', example()['data_prompt'])]
    assert result['detector_flag'] == 0 and result['localized_text'] is None
    assert result['run_kind'] == 'debug' and result['not_a_formal_result']


def test_detected_recovery_passes_instruction_separately_and_retains_both_texts():
    calls, target = [], Target()
    def recover(data, instruction):
        calls.append((data, instruction))
        return 'synthetic cleaned document', 'injected text'
    result = run(condition='promptlocate', target=target,
                 detector=SimpleNamespace(detect=lambda text: 1),
                 locator=SimpleNamespace(locate_and_recover=recover))
    assert calls == [(example()['data_prompt'], 'trusted task')]
    assert target.calls == [('trusted task', 'synthetic cleaned document')]
    assert result['input']['data_prompt'] == example()['data_prompt']
    assert result['localized_text'] == 'injected text'


def test_swallowed_locator_error_becomes_f6_and_skips_target():
    class BrokenLocator:
        def locate_and_recover(self, data, instruction):
            logging.getLogger(type(self).__module__).error('Prompt localization failed; returning the original prompt')
            return data, ''
    target = Target()
    result = run(condition='promptlocate', target=target,
                 detector=SimpleNamespace(detect=lambda text: 1), locator=BrokenLocator())
    assert result['validity'] == 'F6' and result['error_stage'] == 'localization'
    assert result['cleaned_input'] == example()['data_prompt']
    assert result['locator_logged_errors'] and target.calls == []


def test_detector_error_is_never_a_clean_pass():
    def broken(text): raise RuntimeError('detector failure')
    target = Target()
    result = run(condition='promptlocate', target=target,
                 detector=SimpleNamespace(detect=broken), locator=object())
    assert result['validity'] == 'F6' and target.calls == []


def test_parse_error_retains_raw_response_and_official_false():
    result = run(condition='no_defense', target=SimpleNamespace(query=lambda *args: 'bad JSON'))
    assert result['raw_response'] == 'bad JSON'
    assert result['evaluation']['official_success'] is False
    assert result['validity'] == 'F6'


def test_unknown_condition_is_rejected_before_calls():
    with pytest.raises(ValueError):
        run(condition='salt', target=Target())
