"""Final Kafka 2.0 contract examples; runs without ML or transport."""
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'shared/mocks/kafka-2.0'
if (ROOT / 'backend').is_dir():
    from backend.contracts import ContractValidationError as Error, validate_piece_analysis
    def validate(event):
        validate_piece_analysis(event, strict_publisher=True)
        return validate_piece_analysis(event)
else:
    from src.contracts import ContractError as Error, validate_piece_analysis
    class Taxonomy:
        version = 'defects-a1-1.0.0'
        def resolve(self, value, *, version):
            if value != 'AMASSADO' or version != self.version:
                raise ValueError('unknown class/version')
    def validate(event):
        return validate_piece_analysis(event, Taxonomy())

@pytest.mark.parametrize('path', sorted(EXAMPLES.glob('i8-piece-*.json')))
def test_final_valid_examples(path):
    event = json.loads(path.read_text())
    assert validate(event) == event

@pytest.mark.parametrize('path', sorted((EXAMPLES / 'invalid').glob('*.json')))
def test_final_invalid_examples(path):
    with pytest.raises(Error):
        validate(json.loads(path.read_text()))
