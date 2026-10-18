import logging
import math
from types import SimpleNamespace

import pytest

from repro.locator_trace import LocatorTrace, map_segments, safe_value


def test_mapping_repeated_text_follows_complete_document_order():
    result = map_segments('Same.  Same.', ['Same.', 'Same.'])
    assert result['spans'] == [[0, 5], [7, 12]]
    assert map_segments('Dropped. Same.', ['Same.'])['status'] == 'UNKNOWN'
    assert map_segments('Same. Dropped.', ['Same.'])['status'] == 'UNKNOWN'


def test_mapping_tracks_literal_newline_expansion_to_original_codepoints():
    result = map_segments('A\\nB.', ['A', 'B.'])
    assert result['spans'] == [[0, 1], [3, 5]]
    assert map_segments('A\\nB.', ['A\nB.'])['spans'] == [[0, 5]]


def test_nonfinite_serialization_preserves_explicit_marker():
    assert safe_value({'scores': [float('nan'), float('inf'), 1.0]}) == {
        'scores': [{'nonfinite': 'nan'}, {'nonfinite': 'inf'}, 1.0]}


def test_trace_observer_returns_original_objects_and_restores_calls():
    value = [object()]
    owner = SimpleNamespace(call=lambda arg: value)
    original = owner.call
    trace = LocatorTrace(SimpleNamespace(__name__='synthetic_locator'))
    trace.wrap(owner, 'call', lambda event, args, kwargs, result: event.update(arg=args[0], size=len(result)))
    assert owner.call('input') is value
    assert trace.events[0]['arg'] == 'input'
    trace.close()
    assert owner.call is original


def test_budget_failure_is_recorded_and_never_a_successful_observation():
    owner = SimpleNamespace(call=lambda: 42)
    trace = LocatorTrace(SimpleNamespace(__name__='synthetic_locator'), max_calls=1)
    trace.wrap(owner, 'call', lambda *args: None)
    assert owner.call() == 42
    with pytest.raises(RuntimeError, match='DEBUG_TRACE_BUDGET_EXCEEDED'):
        owner.call()
    assert trace.errors and len(trace.events) == 1
    trace.close()


def test_helper_nan_is_observed_without_changing_original_return():
    returned = (float('nan'), 0.0)
    module = SimpleNamespace(__name__='synthetic_helper',
        split_sentence=lambda *a: [], compute_conditional_probability=lambda *a: returned,
        causal_influence=lambda *a: 0, binary_search=lambda *a: (),
        binary_search_injection=lambda *a: (), find_data_end=lambda *a: ())
    original = module.compute_conditional_probability
    def detector():
        return SimpleNamespace(detect=lambda *a: 0, query=lambda *a: 0,
            model=SimpleNamespace(query=lambda *a: '', query_localization=lambda *a: '',
                                  ft_model=SimpleNamespace(generate=lambda *a, **k: None)))
    whole, oracle = detector(), detector()
    trace = LocatorTrace(module).install(whole, SimpleNamespace(bd=oracle))
    try:
        tokenizer = lambda text: {'input_ids': list(text)}
        assert module.compute_conditional_probability('prefix', 'tail', tokenizer, None) is returned
        event = trace.events[0]
        assert trace.nonfinite is True and event['finite'] is False
        assert event['average_log_probability'] == {'nonfinite': 'nan'}
        assert event['condition_token_count'] == 6 and event['full_token_count_before_crop'] == 11
    finally:
        trace.close()
    assert module.compute_conditional_probability is original
