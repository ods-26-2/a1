"""Validate the local 1.1 candidate against the actual A1 and I8 adapters.

Usage: python scripts/validar_interoperabilidade_kafka_1_1.py --a1 /repo/a1 --i8 /repo/i8
Requires jsonschema. Does not import Torch, open a database or connect to Kafka.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

from jsonschema import Draft202012Validator, FormatChecker


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--a1', type=Path, required=True)
parser.add_argument('--i8', type=Path, required=True)
args = parser.parse_args()
A1, I8 = args.a1.resolve(), args.i8.resolve()
i8 = module('src.contracts', I8 / 'src/contracts/__init__.py')
a1 = module('a1_candidate_contracts', A1 / 'backend/contracts.py')
a1_taxonomy_module = module('a1_candidate_taxonomy', A1 / 'backend/taxonomy.py')
a1_taxonomy = a1_taxonomy_module.TaxonomyCatalog()
taxonomy_module = module('candidate_taxonomy', I8 / 'src/taxonomy/__init__.py')
artifact = A1 / 'shared/artifacts/defect-taxonomy/defects-a1-1.0.0'
taxonomy = taxonomy_module.load_taxonomy(
    artifact / 'content.json', artifact / 'descriptor.json',
    expected_version='defects-a1-1.0.0')



def read(path):
    return json.loads(path.read_text())


def fixture(name='conforming'):
    return read(A1 / f'shared/mocks/kafka-1.1-candidate/i8-piece-{name}.json')


def schema(path):
    value = read(path)
    Draft202012Validator.check_schema(value)
    return Draft202012Validator(value, format_checker=FormatChecker())


class CandidateContract(unittest.TestCase):
    def assert_both_reject(self, event):
        with self.assertRaises(i8.ContractError):
            i8.validate_piece_analysis(event, taxonomy)
        with self.assertRaises(a1.ContractValidationError):
            a1.validate_piece_analysis(event)
        with self.assertRaises(a1.ContractValidationError):
            a1.validate_piece_analysis(event, strict_publisher=True)

    def test_01_schema_bytes_are_identical_and_schemas_well_formed(self):
        self.assertEqual(
            (I8 / 'shared/schemas/6c/i8-piece-analysis.1.1.schema.json').read_bytes(),
            (A1 / 'shared/schemas/6c/i8-piece-analysis.publish.1.1.schema.json').read_bytes())
        for root in (A1, I8):
            for path in (root / 'shared/schemas/6c').glob('*.json'):
                with self.subTest(path=path):
                    Draft202012Validator.check_schema(read(path))

    def test_02_four_results_pass_all_real_contract_validators(self):
        strict = schema(I8 / 'shared/schemas/6c/i8-piece-analysis.1.1.schema.json')
        for result in ('conforming', 'non-conforming', 'anomaly', 'uncertain'):
            with self.subTest(result=result):
                event = fixture(result)
                self.assertEqual(event, read(I8 / f'shared/mocks/kafka-1.1-candidate/i8-piece-{result}.json'))
                strict.validate(event)
                self.assertEqual(i8.validate_piece_analysis(event, taxonomy), event)
                self.assertEqual(a1.validate_piece_analysis(event), event)
                self.assertEqual(a1.validate_piece_analysis(event, strict_publisher=True), event)

    def test_03_builder_requires_real_analysis_time_and_preserves_three_times(self):
        event = fixture()
        payload = event['payload']
        fields = {key: event[key] for key in (
            'source_id', 'session_id', 'sequence', 'captured_at', 'artifact_version',
            'message_id', 'published_at', 'occurred_at', 'schema_version')}
        fields.update({key: payload[key] for key in (
            'frame_index', 'detection_id', 'bbox', 'result', 'confidence', 'similarity')})
        self.assertEqual(i8.build_piece_analysis(taxonomy=taxonomy, **fields), event)
        fields.pop('occurred_at')
        with self.assertRaises(i8.ContractError):
            i8.build_piece_analysis(taxonomy=taxonomy, **fields)

    def test_04_each_required_field_missing_is_rejected(self):
        original = fixture('non-conforming')
        for key in original:
            with self.subTest(envelope_key=key):
                event = copy.deepcopy(original)
                del event[key]
                self.assert_both_reject(event)
        for key in original['payload']:
            with self.subTest(payload_key=key):
                event = copy.deepcopy(original)
                del event['payload'][key]
                self.assert_both_reject(event)

    def test_05_wrong_envelope_values_and_time_formats(self):
        changes = [
            ('schema_version', '2.0'), ('schema_version', '1.1.0'),
            ('schema', 'ods.industria.defeito_classificado'),
            ('schema', 'ods.ver1.i8_piece_analyzed'),
            ('message_type', 'command'), ('producer', 'A1'),
            ('message_id', 'not-a-uuid'), ('session_id', 'not-a-uuid'),
            ('sequence', -1), ('sequence', True), ('sequence', 0.5),
            ('source_id', ''), ('artifact_version', ''),
            ('occurred_at', '2026-02-30T12:00:00.000Z'),
            ('occurred_at', '2026-11-05T13:00:00Z'),
            ('occurred_at', '2026-11-05T13:00:00.080+00:00'),
            ('occurred_at', None), ('occurred_at', 123),
            ('captured_at', 'invalid'), ('published_at', 'invalid'),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                event = fixture()
                event[key] = value
                self.assert_both_reject(event)

    def test_06_invalid_payload_and_legacy_vocabulary(self):
        changes = [
            ('frame_index', -1), ('detection_id', True),
            ('bbox', [1, 0, 1, 10]), ('bbox', [0, 10, 10, 0]),
            ('bbox', [-1, 0, 10, 10]), ('bbox', [0, 0, 1]),
            ('confidence', True), ('confidence', -0.1),
            ('similarity', 1.01), ('similarity', float('inf')),
            ('similarity', float('nan')), ('confidence', float('nan')),
            ('result', 'APPROVED'), ('evidence', {'image_url': 'other.png'}),
            ('piece_id', 'P1'), ('classification', {'id': 'AMASSADO'}),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                event = fixture()
                event['payload'][key] = value
                self.assert_both_reject(event)

    def test_07_loaded_taxonomy_checks_beyond_json_schema(self):
        for key, value in [('defect_class', 'UNKNOWN'), ('taxonomy_version', 'missing-version')]:
            with self.subTest(key=key):
                event = fixture('non-conforming')
                event['payload'][key] = value
                # A1 contract validates structure; its domain taxonomy gate runs in triage.
                with self.assertRaises(i8.ContractError):
                    i8.validate_piece_analysis(event, taxonomy)
                with self.assertRaises(ValueError):
                    taxonomy.resolve(event['payload']['defect_class'],
                                     version=event['payload']['taxonomy_version'])
                with self.assertRaises(a1_taxonomy_module.TaxonomyError):
                    a1_taxonomy.resolve(event['payload']['taxonomy_version'],
                                        event['payload']['defect_class'])

    def test_08_known_class_only_for_non_conforming(self):
        for name in ('conforming', 'anomaly', 'uncertain'):
            with self.subTest(name=name):
                event = fixture(name)
                event['payload']['defect_class'] = 'AMASSADO'
                self.assert_both_reject(event)

    def test_09_legacy_1_0_remains_valid_without_occurred_at(self):
        for path in (A1 / 'shared/mocks/6c/valid').glob('i8-piece-*.json'):
            with self.subTest(path=path):
                event = read(path)
                self.assertNotIn('occurred_at', event)
                i8.validate_piece_analysis(event, taxonomy)
                a1.validate_piece_analysis(event)
                a1.validate_piece_analysis(event, strict_publisher=True)

    def test_10_additive_consumption_stays_separate_from_strict_publication(self):
        event = fixture()
        event['schema_version'] = '1.2'
        event['payload']['diagnostics'] = {'local_ms': 12}
        a1.validate_piece_analysis(event)
        with self.assertRaises(a1.ContractValidationError):
            a1.validate_piece_analysis(event, strict_publisher=True)
        with self.assertRaises(i8.ContractError):
            i8.validate_piece_analysis(event, taxonomy)

    def test_11_revalidation_does_not_mutate_event_identity_or_times(self):
        event = fixture()
        before = copy.deepcopy(event)
        for _ in range(2):
            i8.validate_piece_analysis(event, taxonomy)
            a1.validate_piece_analysis(event)
        self.assertEqual(event, before)

    def test_12_topic_and_schema_are_an_explicit_candidate_decision(self):
        self.assertEqual(fixture()['schema'], 'ods.i8.piece_analysis')
        self.assertNotIn('torch', sys.modules)

    def test_13_persisted_negative_examples_are_identical_and_rejected(self):
        for path in (A1 / 'shared/mocks/kafka-1.1-candidate/invalid').glob('*.json'):
            with self.subTest(path=path):
                event = read(path)
                self.assertEqual(event, read(I8 / 'shared/mocks/kafka-1.1-candidate/invalid' / path.name))
                self.assert_both_reject(event)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CandidateContract)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
