"""Hardware identity gates; labels and installed CUDA wheels are not evidence."""
import csv
import io
import math


def gpu_gate(probe, required_name, minimum_mib):
    """Check one physical GPU meets BOTH name and total-memory requirements."""
    if not required_name or minimum_mib <= 0:
        raise ValueError('An explicit GPU name and positive minimum VRAM are required')
    matches, devices, errors = [], [], []
    if probe.get('returncode') != 0:
        errors.append('nvidia-smi did not return a successful hardware inventory')
    else:
        try:
            rows = list(csv.reader(io.StringIO(probe.get('stdout', ''))))
            for row in rows[1:]:
                if not row or not any(cell.strip() for cell in row):
                    continue
                if len(row) != 4:
                    raise ValueError('Unexpected GPU inventory columns')
                memory = float(row[1].strip().split()[0])
                if not math.isfinite(memory) or memory <= 0:
                    raise ValueError('Invalid total GPU memory')
                device = {'name': row[0].strip(), 'memory_total_mib': memory,
                          'memory_free_raw': row[2].strip(), 'driver': row[3].strip()}
                devices.append(device)
                if required_name.casefold() in device['name'].casefold() and memory >= minimum_mib:
                    matches.append(device)
        except (ValueError, IndexError, TypeError) as exc:
            errors.append('Cannot interpret GPU inventory: ' + str(exc))
    if not matches:
        errors.append('No single GPU matches the required name and VRAM')
    return {'passed': bool(matches) and not errors, 'required_name': required_name,
            'minimum_total_mib': minimum_mib, 'devices': devices, 'matching_devices': matches,
            'errors': errors, 'scope': 'Hardware inventory only; not CUDA/NF4/model acceptance'}
