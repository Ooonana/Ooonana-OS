#!/usr/bin/env python3
"""Provider/credential boundaries and response failures; no network or real keys."""
import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ai', ROOT / 'packages/ooonana/usr/lib/ooonana/ai/ooonana_ai.py')
ai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)


class OpenAiProvider(unittest.TestCase):
    def setUp(self):
        self.config = {'OOONANA_AI_PROVIDER': 'openai', 'OPENAI_API_KEY': 'owned-fixture-token',
                       'NVIDIA_API_KEY': 'different-fixture-token'}
        self.args = argparse.Namespace(model='', provider='openai')

    def test_environment_and_provider_keys_stay_separate(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'owned-fixture-token',
                                    'OOONANA_OPENAI_MODEL_FAST': 'fixture-custom'}, clear=True):
            config = ai.load_config(Path('/missing-owned-fixture'))
        self.assertEqual(config['OPENAI_API_KEY'], 'owned-fixture-token')
        self.assertEqual(ai.resolve_model('fast', config, 'openai'), 'fixture-custom')
        self.assertEqual(ai.provider_api_key(self.config, 'nim'), 'different-fixture-token')
        self.assertEqual(ai.provider_api_key(self.config, 'openai'), 'owned-fixture-token')
        self.assertEqual(ai.selected_provider({'OOONANA_AI_PROVIDER': 'auto', 'OPENAI_API_KEY': 'fixture'}), 'openai')
        self.assertEqual(ai.selected_provider({**self.config, 'OOONANA_AI_PROVIDER': 'auto'}), 'nim')

    def test_request_uses_own_endpoint_and_supported_token_budget(self):
        payload = ai.request_payload(self.args, self.config, [{'role': 'user', 'content': 'fixture'}], True)
        self.assertEqual(payload['provider'], 'openai')
        self.assertEqual(payload['model'], 'gpt-6-luna')
        self.assertEqual(payload['reasoning_effort'], 'none')
        self.assertIn('max_completion_tokens', payload)
        self.assertNotIn('max_tokens', payload)
        self.assertNotIn('temperature', payload)
        self.assertEqual(ai.provider_base_url(self.config, 'openai'), 'https://api.openai.com/v1')
        self.assertEqual(ai.provider_base_url({**self.config, 'OOONANA_NIM_BASE_URL': 'http://fixture.invalid'}, 'openai'), 'https://api.openai.com/v1')

    def test_real_client_streaming_and_nonstreaming_contract(self):
        seen = []
        def response(request, **kwargs):
            seen.append(request)
            return io.BytesIO(json.dumps({'choices': [{'message': {'content': 'fixture reply'}}]}).encode())
        with patch.object(ai.urllib.request, 'urlopen', side_effect=response):
            self.assertEqual(ai.call_model(self.args, self.config, [], False), 'fixture reply')
        self.assertEqual(seen[0].get_header('Authorization'), 'Bearer owned-fixture-token')
        chunks = b'data: {"choices":[{"delta":{"content":"first "}}]}\n\ndata: {"choices":[{"delta":{"content":"second"}}]}\n\ndata: [DONE]\n\n'
        with patch.object(ai.urllib.request, 'urlopen', return_value=io.BytesIO(chunks)), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ai.call_model(self.args, self.config, [], True), 'first second')

    def test_quota_and_rate_limits_stay_distinct_and_redacted(self):
        for code, expected in [('credit_balance_exhausted', 'API credits exhausted'),
                               ('insufficient_quota', 'API credits exhausted'),
                               ('rate_limit_exceeded', 'Request rate limited')]:
            error = urllib.error.HTTPError('https://api.openai.com', 429, 'fixture', {},
                io.BytesIO(json.dumps({'error': {'code': code, 'message': 'owned-fixture-token'}}).encode()))
            with patch.object(ai.urllib.request, 'urlopen', side_effect=error):
                with self.assertRaises(ai.OoonanaError) as caught:
                    ai.call_model(self.args, self.config, [], False)
            self.assertIn(expected, str(caught.exception))
            self.assertNotIn('owned-fixture-token', str(caught.exception))

    def test_config_output_never_prints_key_prefix(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'ai.env'
            config.write_text('OPENAI_API_KEY=owned-fixture-token\n')
            output = io.StringIO()
            with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(output):
                ai.cmd_config(argparse.Namespace(config=str(config)))
            self.assertNotIn('owned-fi', output.getvalue())
            self.assertIn('...redacted', output.getvalue())

    def test_missing_key_or_empty_response_refused(self):
        with self.assertRaisesRegex(ai.OoonanaError, 'OPENAI_API_KEY'):
            ai.call_model(self.args, {'OOONANA_AI_PROVIDER': 'openai'}, [], False)
        with patch.object(ai.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"choices":[]}')):
            with self.assertRaisesRegex(ai.OoonanaError, 'chat content'):
                ai.call_model(self.args, self.config, [], False)
        with patch.object(ai.urllib.request, 'urlopen', return_value=io.BytesIO(b'not-json')):
            with self.assertRaisesRegex(ai.OoonanaError, 'invalid response'):
                ai.call_model(self.args, self.config, [], False)


if __name__ == '__main__':
    unittest.main()
