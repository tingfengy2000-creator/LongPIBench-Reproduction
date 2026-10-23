"""Read-only layer identity checks; never changes model weights or precision."""
from collections import Counter


def qualified_class(module):
    return type(module).__module__+'.'+type(module).__qualname__


def inspect_layers(model, native_type, expected_dtype):
    same_name = []
    native = []
    for name, module in model.named_modules():
        if type(module).__name__ == 'Linear4bit':
            same_name.append({'path': name, 'class': qualified_class(module), 'native_type_match': isinstance(module, native_type)})
        if isinstance(module, native_type):
            weight = module.weight
            state = getattr(weight, 'quant_state', None)
            native.append({'path': name, 'class': qualified_class(module),
                           'compute_dtype': str(getattr(module, 'compute_dtype', None)),
                           'expected_compute_dtype': getattr(module, 'compute_dtype', None) == expected_dtype,
                           'quant_state_present': state is not None,
                           'quant_type': getattr(state, 'quant_type', None),
                           'nested_quantization': getattr(state, 'nested', None),
                           'weight_device': str(weight.device)})
    return {'selection_policy': 'isinstance(module, bitsandbytes.nn.Linear4bit), no mutation',
            'legacy_class_name_count': len(same_name), 'native_count': len(native),
            'same_name_class_counts': dict(Counter(r['class'] for r in same_name)),
            'same_name_modules': same_name, 'native_modules': native,
            'native_count_224': len(native) == 224,
            'native_quant_states_present': bool(native) and all(r['quant_state_present'] for r in native),
            'native_compute_dtype_matches': bool(native) and all(r['expected_compute_dtype'] for r in native),
            'native_on_cuda': bool(native) and all(r['weight_device'].startswith('cuda') for r in native)}


def inspect_structure(whole, expected_generation, bnb, torch):
    actual_generation = whole.model.ft_model.generation_config.to_dict()
    active = list(whole.model.ft_model.active_adapters)
    layers = inspect_layers(whole.model.base_model, bnb.nn.Linear4bit, torch.bfloat16)
    generation_diff = {k: {'expected': expected_generation.get(k), 'actual': actual_generation.get(k)}
                       for k in sorted(set(expected_generation) | set(actual_generation))
                       if actual_generation.get(k) != expected_generation.get(k) or (k in actual_generation) != (k in expected_generation)}
    checks = {'active_adapter_default': active == ['default'], 'original_generation_defaults_equal': actual_generation == expected_generation,
              'native_count_224': layers['native_count_224'],
              'native_quant_states_present': layers['native_quant_states_present'],
              'native_compute_dtype_matches': layers['native_compute_dtype_matches'], 'native_on_cuda': layers['native_on_cuda']}
    old_checks = [('active_adapter_default', checks['active_adapter_default']),
                  ('original_generation_defaults_equal', checks['original_generation_defaults_equal']),
                  ('legacy_class_name_count_224', layers['legacy_class_name_count'] == 224)]
    return {'checks': checks, 'failed_checks': [k for k, passed in checks.items() if not passed],
            'active_adapters': active, 'generation_defaults': actual_generation, 'generation_diff': generation_diff,
            'layers': layers,
            'first_failed_004_guard_in_current_loaded_model': next((k for k, passed in old_checks if not passed),
                                                                  'unknown_or_legacy_quant_state_dtype_guard'),
            'historical_004_failure_line_independently_observed': False,
            'method_behavior_modified': False}
