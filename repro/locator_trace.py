"""Read-only observations around pinned locator calls, for sequential runs.

Wrappers return the original objects. Budget exceptions and downstream stops
are declared execution controls, not changes to the upstream search algorithm.
Debug defaults remain unchanged; formal guarded conditions use explicit labels.
"""
import functools
import logging
import math
import sys
import time


def safe_value(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {'nonfinite': str(value)}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): safe_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe_value(v) for v in value]
    if hasattr(value, 'item'):
        return safe_value(value.item())
    raise TypeError('Unrecordable trace type: ' + type(value).__name__)


def map_segments(original, segments):
    """Map ordered segments only when gaps contain whitespace exclusively.

    This proves non-whitespace coverage; it never chooses a global first match
    across skipped document text. Any mismatch returns unknown, not fake spans.
    Literal backslash-n expansion follows the exact upstream preprocessing.
    """
    converted, origins = [], []
    i = 0
    while i < len(original):
        if original[i:i+2] == '\\n':
            converted.append('\n')
            origins.append((i, i+2))
            i += 2
        else:
            converted.append(original[i])
            origins.append((i, i+1))
            i += 1
    text = ''.join(converted)
    cursor, mapped = 0, []
    for segment in segments:
        if not isinstance(segment, str) or not segment.strip():
            return {'status': 'UNKNOWN', 'reason': 'Empty or whitespace-only segment', 'spans': None}
        start = text.find(segment, cursor)
        if start < 0 or text[cursor:start].strip():
            return {'status': 'UNKNOWN', 'reason': 'No ordered whitespace-gap alignment', 'spans': None}
        end = start + len(segment)
        mapped.append([origins[start][0], origins[end-1][1]])
        cursor = end
    if text[cursor:].strip():
        return {'status': 'UNKNOWN', 'reason': 'Uncovered non-whitespace suffix', 'spans': None}
    return {'status': 'EXACT_ORDERED_NONWHITESPACE_COVERAGE', 'spans': mapped,
            'coordinate_system': 'original Unicode code points; end-exclusive; inserted spans are not semantic truth'}


class LocatorTrace(logging.Handler):
    def __init__(self, module, *, max_calls=256, max_seconds=1200,
                 whole_label='whole_large_debug_only', budget_error='DEBUG_TRACE_BUDGET_EXCEEDED',
                 record_boundaries=False):
        super().__init__(level=logging.ERROR)
        self.module = module
        self.max_calls = max_calls
        self.max_seconds = max_seconds
        self.whole_label = whole_label
        self.budget_error = budget_error
        self.record_boundaries = record_boundaries
        self.originals = []
        self.reset()

    def reset(self):
        self.events = []
        self.errors = []
        self.nonfinite = False
        self.boundary_nonfinite = False
        self.calls = 0
        self.started = time.monotonic()
        self.segment_mapping = None

    def emit(self, record):
        self.errors.append({'level': record.levelname, 'message': record.getMessage()})

    def check_budget(self):
        self.calls += 1
        if self.calls > self.max_calls or time.monotonic() - self.started > self.max_seconds:
            self.errors.append({'level': 'ERROR', 'message': self.budget_error})
            raise RuntimeError(self.budget_error)

    def wrap(self, owner, name, observe):
        original = getattr(owner, name)

        @functools.wraps(original)
        def wrapper(*args, **kwargs):
            self.check_budget()
            start = time.monotonic()
            event = {'function': name}
            # Append on entry so nested calls retain order and failures persist.
            self.events.append(event)
            try:
                result = original(*args, **kwargs)
                observe(event, args, kwargs, result)
                return result
            except Exception as exc:
                event.update(error_type=type(exc).__name__, error_message=str(exc))
                raise
            finally:
                event['seconds'] = time.monotonic() - start

        self.originals.append((owner, name, original))
        setattr(owner, name, wrapper)

    def observe_query_model(self, detector, label):
        model = detector.model
        def generation(event, args, kwargs, result):
            ids = kwargs['input_ids']
            event.update(role=label, input_token_ids=ids[0].tolist(), input_token_count=int(ids.shape[1]),
                         generated_token_ids=result[0, ids.shape[1]:].tolist(),
                         generation_kwargs=safe_value({k: v for k, v in kwargs.items()
                                                       if k not in {'input_ids', 'attention_mask'}}))
        self.wrap(model.ft_model, 'generate', generation)
        for name in ['query', 'query_localization']:
            def observe(event, args, kwargs, result, label=label):
                event.update(role=label, prompt=args[0], raw_response=result)
            self.wrap(model, name, observe)
        for name in ['detect', 'query']:
            def observe(event, args, kwargs, result, label=label):
                event.update(role=label, data=args[0], binary_result=int(result))
            self.wrap(detector, name, observe)

    def install(self, whole_detector, locator):
        if self.record_boundaries:
            self.install_boundary_observer()
        self.observe_query_model(whole_detector, self.whole_label)
        self.observe_query_model(locator.bd, 'localization_oracle')

        def split(event, args, kwargs, result):
            event.update(input_text=args[0], segments=list(result))
            self.segment_mapping = map_segments(args[0], result)
            event['original_span_mapping'] = self.segment_mapping

        def probability(event, args, kwargs, result):
            avg, total = float(result[0]), float(result[1])
            finite = math.isfinite(avg) and math.isfinite(total)
            self.nonfinite = self.nonfinite or not finite
            event.update(condition_text=args[0], target_text=args[1],
                         average_log_probability=safe_value(avg), total_log_probability=safe_value(total), finite=finite)
            tokenizer = args[2]
            condition_tokens = len(tokenizer(args[0])['input_ids'])
            # Observation only: mirror the full string that the unmodified
            # function just processed, without changing its cropping/indexing.
            full_tokens = len(tokenizer(args[0] + ' ' + args[1])['input_ids'])
            event.update(condition_token_count=condition_tokens, full_token_count_before_crop=full_tokens,
                         upstream_full_token_count_after_crop=min(full_tokens, 1024),
                         condition_exceeds_cropped_length=condition_tokens > min(full_tokens, 1024))

        def influence(event, args, kwargs, result):
            finite = math.isfinite(float(result))
            self.nonfinite = self.nonfinite or not finite
            event.update(prefix=args[0], middle=args[1], suffix=args[2], influence=safe_value(float(result)), finite=finite)

        def search(event, args, kwargs, result):
            event.update(segments=list(args[0]), start=args[1], end=args[2], prefix=args[4],
                         result=safe_value(result))

        def injection(event, args, kwargs, result):
            event.update(raw_segments=list(args[0]), normalized_segments=[' '.join(s.split()) for s in args[0]],
                         intervals_and_query_count=safe_value(result))

        def data_end(event, args, kwargs, result):
            event.update(segments=list(args[0]), injection_start=args[1], start=args[2], end=args[3],
                         prefix=args[4], target_instruction=args[5], result=safe_value(result))

        for name, observer in [('split_sentence', split), ('compute_conditional_probability', probability),
                               ('causal_influence', influence), ('binary_search', search),
                               ('binary_search_injection', injection), ('find_data_end', data_end)]:
            self.wrap(self.module, name, observer)
        logging.getLogger(self.module.__name__).addHandler(self)
        return self

    def install_boundary_observer(self):
        # Replace this module's numpy reference, not global numpy functions.
        # Read the actual split_sentence locals at its original np.where call;
        # return exactly the original result, with no recomputation of scores.
        original = self.module.np
        observer = self

        class NumpyObserver:
            def __getattr__(self, name):
                return getattr(original, name)

            def where(self, *args, **kwargs):
                result = original.where(*args, **kwargs)
                frame = sys._getframe(1)
                values = frame.f_locals
                if frame.f_code.co_name == 'split_sentence' and 'cos_sim' in values:
                    scores = values['cos_sim'].tolist()
                    finite = all(math.isfinite(float(v)) for v in scores)
                    observer.boundary_nonfinite = observer.boundary_nonfinite or not finite
                    row = {'clause': values['sub_sentence'], 'words': list(values['words']),
                           'clause_offsets': safe_value(values['offsets']),
                           'adjacent_word_cosine': safe_value(scores), 'finite': finite,
                           'threshold': float(values['thres']), 'split_positions': result[0].tolist()}
                    event = next(e for e in reversed(observer.events) if e['function'] == 'split_sentence')
                    event.setdefault('boundary_observations', []).append(row)
                return result

        self.originals.append((self.module, 'np', original))
        self.module.np = NumpyObserver()

    def close(self):
        logging.getLogger(self.module.__name__).removeHandler(self)
        for owner, name, original in reversed(self.originals):
            setattr(owner, name, original)
        self.originals.clear()
        super().close()

    def record(self):
        return {'events': self.events, 'logged_errors': self.errors, 'nonfinite_helper': self.nonfinite,
                'nonfinite_boundary': self.boundary_nonfinite,
                'call_count': self.calls, 'segment_mapping': self.segment_mapping,
                'debug_budgets': {'max_observed_calls': self.max_calls, 'max_seconds': self.max_seconds}}
