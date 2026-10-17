from repro.hardware import gpu_gate


def inventory(*rows):
    return {'returncode': 0, 'stdout': 'name, memory.total [MiB], memory.free [MiB], driver_version\n' + '\n'.join(rows)}


def test_cloud_or_failed_inventory_does_not_pass():
    assert not gpu_gate({'error': 'FileNotFoundError'}, 'RTX 5090', 30000)['passed']


def test_5060_and_separate_memory_cannot_be_combined():
    result = gpu_gate(inventory('RTX 5090, 8192, 8000, 616', 'Other GPU, 32768, 30000, 616'), 'RTX 5090', 30000)
    assert not result['passed']


def test_expected_gpu_matches_real_inventory_not_label():
    result = gpu_gate(inventory('NVIDIA GeForce RTX 5090, 32607, 31000, 616.92'), 'RTX 5090', 30000)
    assert result['passed']
    assert len(result['matching_devices']) == 1


def test_malformed_memory_is_blocked():
    assert not gpu_gate(inventory('RTX 5090, N/A, 32000, 616'), 'RTX 5090', 30000)['passed']
