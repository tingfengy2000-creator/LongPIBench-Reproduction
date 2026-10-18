"""Fixed local target inference used by the declared formal R1 condition."""
import hashlib
import random
import time


def stop_reason(ids, eos_ids, budget):
    if not ids or len(ids) > budget:
        raise ValueError('Empty generation or token budget exceeded')
    if ids[-1] in eos_ids:
        return 'EOS'
    return 'TOKEN_LIMIT' if len(ids) == budget else 'OTHER_STOP'


def check_context(input_tokens, generation_budget, context_limit):
    if input_tokens + generation_budget > context_limit:
        raise ValueError('Input plus generation budget exceeds context; no truncation allowed')


class FixedLocalTarget:
    def __init__(self, spec, config):
        import numpy as np
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.config = config
        self.last_attempt = None
        target = config['target']
        random.seed(config['seed'])
        np.random.seed(config['seed'])
        torch.manual_seed(config['seed'])
        local = {'local_files_only': True, 'token': False, 'trust_remote_code': False}
        self.tokenizer = AutoTokenizer.from_pretrained(spec['resolved_path'], **local)
        started = time.monotonic()
        self.model = AutoModelForCausalLM.from_pretrained(spec['resolved_path'], **local,
            use_safetensors=True, torch_dtype=torch.bfloat16, device_map={'': 0}, low_cpu_mem_usage=True).eval()
        torch.cuda.synchronize()
        if any(p.device.type != 'cuda' for p in self.model.parameters()):
            raise RuntimeError('Target parameters are not wholly on CUDA')
        if self.model.get_input_embeddings().weight.dtype != torch.bfloat16 or getattr(self.model, 'is_quantized', False):
            raise RuntimeError('Unexpected target precision or quantization')
        digest = hashlib.sha256(self.tokenizer.chat_template.encode()).hexdigest()
        eos = self.model.generation_config.eos_token_id
        eos = eos if isinstance(eos, list) else [eos]
        if digest != target['chat_template_sha256'] or eos != target['eos_token_ids']:
            raise RuntimeError('Fixed chat template or EOS configuration changed')
        self.metadata = {'model_source': spec, 'model_class': type(self.model).__name__,
            'tokenizer_class': type(self.tokenizer).__name__, 'chat_template_sha256': digest,
            'generation_config_from_fixed_snapshot': self.model.generation_config.to_dict(),
            'embedding_dtype': str(self.model.get_input_embeddings().weight.dtype),
            'load_seconds_including_disk_io': time.monotonic()-started,
            'attention_implementation': getattr(self.model.config, '_attn_implementation', None),
            'max_position_embeddings': self.model.config.max_position_embeddings,
            'torch_cuda_build': torch.version.cuda,
            'cudnn_benchmark': torch.backends.cudnn.benchmark,
            'cudnn_deterministic': torch.backends.cudnn.deterministic,
            'deterministic_algorithms_enabled': torch.are_deterministic_algorithms_enabled()}

    def generate(self, system, data):
        self.last_attempt = None
        target = self.config['target']
        messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': data}]
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        batch = self.tokenizer(prompt, return_tensors='pt', add_special_tokens=False, truncation=False).to('cuda:0')
        ids = batch['input_ids'][0].tolist()
        if ids != self.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True):
            raise RuntimeError('Actual token IDs differ from direct chat template')
        overrides = {'max_new_tokens': target['max_new_tokens'], 'do_sample': target['do_sample'],
                     'pad_token_id': target['pad_token_id']}
        self.last_attempt = {'messages': messages, 'rendered_prompt': prompt, 'input_token_ids': ids,
            'input_token_count': len(ids), 'generation_overrides': overrides, 'generation_attempted': False,
            'chat_template_sha256': self.metadata['chat_template_sha256']}
        check_context(len(ids), target['max_new_tokens'], self.model.config.max_position_embeddings)
        self.torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()
        self.last_attempt['generation_attempted'] = True
        with self.torch.inference_mode():
            output = self.model.generate(**batch, **overrides)
        self.torch.cuda.synchronize()
        elapsed = time.monotonic()-started
        generated = output[0, len(ids):].tolist()
        self.last_attempt = {'messages': messages, 'rendered_prompt': prompt, 'input_token_ids': ids,
            'input_token_count': len(ids), 'generated_token_ids': generated, 'output_token_count': len(generated),
            'raw_response': self.tokenizer.decode(generated, skip_special_tokens=True).strip(),
            'stop_reason': stop_reason(generated, target['eos_token_ids'], target['max_new_tokens']),
            'generation_overrides': overrides, 'generation_seconds': elapsed,
            'peak_allocated_bytes': self.torch.cuda.max_memory_allocated(),
            'peak_reserved_bytes': self.torch.cuda.max_memory_reserved(),
            'chat_template_sha256': self.metadata['chat_template_sha256'], 'generation_attempted': True}
        return self.last_attempt
