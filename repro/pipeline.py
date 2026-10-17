"""Per-case detect/localize/recover/target orchestration for offline contracts.

No model factory or formal runner is provided yet. GPU validation, detailed
locator span/helper tracing and a frozen config remain required before formal
execution. Tests use doubles and are never experiment results.
"""
import logging
from time import perf_counter

from .scoring import evaluate_response


class _LocatorErrors(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.messages = []

    def emit(self, record):
        self.messages.append({'level': record.levelname, 'message': record.getMessage()})


def run_debug_case(example, *, condition, target, parse, score, detector=None, locator=None):
    """Retain raw strings and surface swallowed localization error logs as F6.

    Deliberately debug-only: impossible to label this unfinished runner formal.
    Locator log capture is single-thread use; no parallel case execution.
    """
    if condition not in {'no_defense', 'promptlocate'}:
        raise ValueError('Unsupported condition')
    if (example.get('suite'), example.get('goal')) not in {('email', '0'), ('resume', '2')}:
        raise ValueError('Only frozen primary goals are supported')
    if not isinstance(example.get('data_prompt'), str) or not isinstance(example.get('system_prompt'), str):
        raise TypeError('Full system_prompt and data_prompt must be retained')
    if condition == 'promptlocate' and (detector is None or locator is None):
        raise ValueError('Distinct whole detector and locator must be provided')
    result = {'schema_version': 1, 'run_kind': 'debug', 'not_a_formal_result': True,
              'input': dict(example), 'condition': condition, 'detector_flag': None,
              'detector_score': None, 'score_available': False, 'localized_text': None,
              'cleaned_input': example['data_prompt'], 'raw_response': None,
              'evaluation': None, 'validity': 'F6', 'error_stage': None,
              'timings_seconds': {}, 'locator_logged_errors': [],
              'formal_readiness': False,
              'missing_formal_features': ['internal locator/helper traces', 'original span mapping',
                                          'actual token and GPU runtime metadata', 'frozen formal config']}
    stage = 'initialization'

    def timed(name, call):
        start = perf_counter()
        try:
            return call()
        finally:
            result['timings_seconds'][name] = perf_counter() - start

    try:
        if condition == 'promptlocate':
            stage = 'detection'
            flag = timed(stage, lambda: detector.detect(example['data_prompt']))
            if type(flag) not in (int, bool) or flag not in (0, 1):
                raise ValueError('Detector must return binary 0/1, not a probability')
            result['detector_flag'] = int(flag)
            if flag:
                stage = 'localization'
                errors = _LocatorErrors()
                logger = logging.getLogger(type(locator).__module__)
                logger.addHandler(errors)
                try:
                    recovered = timed(stage, lambda: locator.locate_and_recover(example['data_prompt'], example['system_prompt']))
                finally:
                    logger.removeHandler(errors)
                    result['locator_logged_errors'] = errors.messages
                if not isinstance(recovered, tuple) or len(recovered) != 2 or not all(isinstance(v, str) for v in recovered):
                    raise TypeError('Locator must return two strings')
                result['cleaned_input'], result['localized_text'] = recovered
                if errors.messages:
                    raise RuntimeError('Locator logged an error; returned text is not accepted as a valid recovery')
        stage = 'target'
        result['raw_response'] = timed(stage, lambda: target.query(example['system_prompt'], result['cleaned_input']))
        stage = 'evaluation'
        result['evaluation'] = evaluate_response(example['suite'], example['goal'], result['raw_response'], parse=parse, score=score)
        result['validity'] = result['evaluation']['validity']
    except Exception as exc:
        result.update(error_stage=stage, error_type=type(exc).__name__, error_message=str(exc), validity='F6')
    return result
