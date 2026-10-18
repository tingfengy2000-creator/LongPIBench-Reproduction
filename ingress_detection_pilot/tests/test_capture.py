"""Adapter unit tests only: toy logits below are never experimental data."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from collect_scores import capture, original_score
from prepare_samples import benchmark


class CaptureTest(unittest.TestCase):
    def test_label_mapping_is_max_component_not_sum_or_calibrated_probability(self):
        self.assertEqual(original_score([.2,.4,.4],{0:'BENIGN',1:'INJECTION',2:'JAILBREAK'}),.4)
        self.assertEqual(original_score([.8,.2],{0:'LABEL_0',1:'LABEL_1'}),.2)

    def test_original_early_exit_and_shadow_coverage_preserve_official_result(self):
        import torch
        benchmark()
        from longpibench.detectors import TransformerDetector
        class Classifier(torch.nn.Module):
            config=SimpleNamespace(id2label={0:'SAFE',1:'INJECTION'})
            def forward(self,input_ids):
                positive=input_ids[0,0].item()==512
                return SimpleNamespace(logits=torch.tensor([[0.,3.]] if positive else [[3.,0.]]))
        detector=SimpleNamespace(torch=torch,chunk_tokens=512,threshold=.5,device='cpu',
            tokenizer=lambda *a,**k:{'input_ids':list(range(1700))},model=Classifier().eval())
        detector.predict=lambda text:TransformerDetector.predict(detector,text)
        result=capture(detector,'unit-test only')
        self.assertEqual(result['official_prediction'],1)
        self.assertEqual(result['official_evaluated_chunks'],2)
        self.assertEqual(result['shadow_suffix_chunks'],2)
        self.assertEqual([(c['start_token'],c['end_token']) for c in result['chunks']],[(0,512),(512,1024),(1024,1536),(1536,1700)])
        self.assertEqual(len(detector.model._forward_hooks),0)


if __name__=='__main__': unittest.main()
