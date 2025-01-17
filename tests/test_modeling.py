# Copyright 2022 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import tempfile
import unittest

import torch
from transformers import AutoModelForCausalLM

from trl import AutoModelForCausalLMWithValueHead, create_reference_model


ALL_CAUSAL_LM_MODELS = [
    "trl-internal-testing/tiny-random-CodeGenForCausalLM",
    "trl-internal-testing/tiny-random-GPTJForCausalLM",
    "trl-internal-testing/tiny-random-GPTNeoForCausalLM",
    "trl-internal-testing/tiny-random-GPTNeoXForCausalLM",
    "trl-internal-testing/tiny-random-OPTForCausalLM",
    "trl-internal-testing/tiny-random-BloomForCausalLM",
    "trl-internal-testing/tiny-random-GPT2LMHeadModel",
]


class BaseModelTester:
    all_model_names = None
    trl_model_class = None

    def test_from_save(self):
        """
        Test if the model can be saved and loaded from a directory and get the same weights
        """
        for model_name in self.all_model_names:
            torch.manual_seed(0)
            model = self.trl_model_class.from_pretrained(model_name)

            with tempfile.TemporaryDirectory() as tmp_dir:
                model.save_pretrained(tmp_dir)

                torch.manual_seed(0)
                model_from_save = self.trl_model_class.from_pretrained(tmp_dir)

            # Check if the weights are the same
            for key in model_from_save.state_dict():
                self.assertTrue(torch.allclose(model_from_save.state_dict()[key], model.state_dict()[key]))

    def test_from_save_transformers(self):
        """
        Test if the model can be saved and loaded using transformers and get the same weights
        """
        for model_name in self.all_model_names:
            transformers_model = self.trl_model_class.transformers_parent_class.from_pretrained(model_name)

            trl_model = self.trl_model_class.from_pretrained(model_name)

            with tempfile.TemporaryDirectory() as tmp_dir:
                trl_model.save_pretrained(tmp_dir)
                transformers_model_from_save = self.trl_model_class.transformers_parent_class.from_pretrained(tmp_dir)

            # Check if the weights are the same
            for key in transformers_model.state_dict():
                self.assertTrue(
                    torch.allclose(
                        transformers_model_from_save.state_dict()[key], transformers_model.state_dict()[key]
                    )
                )


class ValueHeadModelTester(BaseModelTester, unittest.TestCase):
    """
    Testing suite for v-head models.
    """

    all_model_names = ALL_CAUSAL_LM_MODELS
    trl_model_class = AutoModelForCausalLMWithValueHead

    def test_value_head(self):
        r"""
        Test if the v-head is added to the model succesfully
        """
        for model_name in self.all_model_names:
            model = AutoModelForCausalLMWithValueHead.from_pretrained(model_name)
            self.assertTrue(hasattr(model, "v_head"))

    def test_value_head_shape(self):
        r"""
        Test if the v-head has the correct shape
        """
        for model_name in self.all_model_names:
            model = AutoModelForCausalLMWithValueHead.from_pretrained(model_name)
            self.assertTrue(model.v_head.summary.weight.shape[0] == 1)

    def test_value_head_init_random(self):
        r"""
        Test if the v-head has been randomly initialized.
        We can check that by making sure the bias is different
        than zeros by default.
        """
        for model_name in self.all_model_names:
            model = AutoModelForCausalLMWithValueHead.from_pretrained(model_name)
            self.assertFalse(torch.allclose(model.v_head.summary.bias, torch.zeros_like(model.v_head.summary.bias)))

    def test_value_head_not_str(self):
        r"""
        Test if the v-head is added to the model succesfully
        """
        for model_name in self.all_model_names:
            pretrained_model = AutoModelForCausalLM.from_pretrained(model_name)
            model = AutoModelForCausalLMWithValueHead.from_pretrained(pretrained_model)
            self.assertTrue(hasattr(model, "v_head"))

    def test_inference(self):
        r"""
        Test if the model can be used for inference and outputs 3 values
        - logits, loss, and value states
        """
        EXPECTED_OUTPUT_SIZE = 3

        for model_name in self.all_model_names:
            model = AutoModelForCausalLMWithValueHead.from_pretrained(model_name)
            input_ids = torch.tensor([[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]])
            outputs = model(input_ids)

            # Check if the outputs are of the right size - here
            # we always output 3 values - logits, loss, and value states
            self.assertEqual(len(outputs), EXPECTED_OUTPUT_SIZE)

    def test_dropout_config(self):
        r"""
        Test if we instantiate a model by adding `summary_drop_prob` to the config
        it will be added to the vhead
        """
        for model_name in self.all_model_names:
            pretrained_model = AutoModelForCausalLM.from_pretrained(model_name)
            pretrained_model.config.summary_dropout_prob = 0.5
            model = AutoModelForCausalLMWithValueHead.from_pretrained(pretrained_model)

            # Check if v head of the model has the same dropout as the config
            self.assertEqual(model.v_head.dropout.p, pretrained_model.config.summary_dropout_prob)

    def test_dropout_kwargs(self):
        r"""
        Test if we instantiate a model by adding `summary_drop_prob` to the config
        it will be added to the vhead
        """
        for model_name in self.all_model_names:
            v_head_kwargs = {"summary_dropout_prob": 0.5}

            model = AutoModelForCausalLMWithValueHead.from_pretrained(model_name, **v_head_kwargs)

            # Check if v head of the model has the same dropout as the config
            self.assertEqual(model.v_head.dropout.p, 0.5)

            model = AutoModelForCausalLMWithValueHead.from_pretrained(model_name, summary_dropout_prob=0.5)

            # Check if v head of the model has the same dropout as the config
            self.assertEqual(model.v_head.dropout.p, 0.5)

    def test_generate(self):
        r"""
        Test if `generate` works for every model
        """
        for model_name in self.all_model_names:
            model = AutoModelForCausalLMWithValueHead.from_pretrained(model_name)
            input_ids = torch.tensor([[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]])

            # Just check if the generation works
            _ = model.generate(input_ids)

    def test_raise_error_not_causallm(self):
        # Test with a model without a LM head
        model_id = "hf-internal-testing/tiny-random-GPT2Model"
        # This should raise a ValueError
        with self.assertRaises(ValueError):
            pretrained_model = AutoModelForCausalLM.from_pretrained(model_id)
            _ = AutoModelForCausalLMWithValueHead.from_pretrained(pretrained_model.transformer)


class ReferenceModelTest(unittest.TestCase):
    def setUp(self):
        self.model = AutoModelForCausalLMWithValueHead.from_pretrained(
            "trl-internal-testing/tiny-random-GPT2LMHeadModel"
        )
        self.test_input = torch.tensor([[0, 1, 2, 3]])
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=1)
        self.layer_format = "pretrained_model.transformer.h.{layer}.attn.c_attn.weight"

    def test_independent_reference(self):
        layer_0 = self.layer_format.format(layer=0)
        layer_5 = self.layer_format.format(layer=4)

        ref_model = create_reference_model(self.model)

        first_layer_before = self.model.get_parameter(layer_0).data.clone()
        last_layer_before = self.model.get_parameter(layer_5).data.clone()

        first_ref_layer_before = ref_model.get_parameter(layer_0).data.clone()
        last_ref_layer_before = ref_model.get_parameter(layer_5).data.clone()

        output = self.model(input_ids=self.test_input, labels=self.test_input)
        output[1].backward()
        self.optimizer.step()

        first_layer_after = self.model.get_parameter(layer_0).data.clone()
        last_layer_after = self.model.get_parameter(layer_5).data.clone()

        first_ref_layer_after = ref_model.get_parameter(layer_0).data.clone()
        last_ref_layer_after = ref_model.get_parameter(layer_5).data.clone()

        # before optimization ref and model are identical
        self.assertTrue((first_layer_before == first_ref_layer_before).all())
        self.assertTrue((last_layer_before == last_ref_layer_before).all())
        # ref model stays identical after optimization
        self.assertTrue((first_ref_layer_before == first_ref_layer_after).all())
        self.assertTrue((last_ref_layer_before == last_ref_layer_after).all())
        # optimized model changes
        self.assertTrue(not (first_layer_before == first_layer_after).all())
        self.assertTrue(not (last_layer_before == last_layer_after).all())

    def test_shared_layers(self):
        layer_0 = self.layer_format.format(layer=0)
        layer_1 = self.layer_format.format(layer=1)

        ref_model = create_reference_model(self.model, num_shared_layers=1)

        first_layer_before = self.model.get_parameter(layer_0).data.clone()
        second_layer_before = self.model.get_parameter(layer_1).data.clone()

        first_ref_layer_before = ref_model.get_parameter(layer_0).data.clone()
        second_ref_layer_before = ref_model.get_parameter(layer_1).data.clone()

        output = self.model(input_ids=self.test_input, labels=self.test_input)
        output[1].backward()
        self.optimizer.step()

        first_layer_after = self.model.get_parameter(layer_0).data.clone()
        second_layer_after = self.model.get_parameter(layer_1).data.clone()

        first_ref_layer_after = ref_model.get_parameter(layer_0).data.clone()
        second_ref_layer_after = ref_model.get_parameter(layer_1).data.clone()

        # before optimization ref and model are identical
        self.assertTrue((first_layer_before == first_ref_layer_before).all())
        self.assertTrue((second_layer_before == second_ref_layer_before).all())
        # ref model stays identical after optimization
        self.assertTrue((first_ref_layer_before == first_ref_layer_after).all())
        self.assertTrue((second_ref_layer_before == second_ref_layer_after).all())
        # first layer of optimized model stays the same
        self.assertTrue((first_layer_before == first_layer_after).all())
        # other layers in optimized model change
        self.assertTrue(not (second_layer_before == second_layer_after).all())
