import json
import logging
import pytest
from unittest.mock import MagicMock

from backend.mqtt_client import A1IngestionClient
from backend.ingestion import IngestResult, IngestStatus

@pytest.fixture
def mock_ingestion_service():
    return MagicMock()

@pytest.fixture
def mqtt_client(mock_ingestion_service):
    return A1IngestionClient(
        broker_url="dummy-broker", 
        ingestion_service=mock_ingestion_service
    )

def test_process_message_valid_json_accepted(mqtt_client, mock_ingestion_service, caplog):
    """Garante que um JSON válido é descodificado e entregue ao serviço de ingestão."""
    caplog.set_level(logging.INFO, logger="backend.mqtt_client")
    # Configura o mock para simular uma ingestão com sucesso
    mock_ingestion_service.ingest.return_value = IngestResult(
        status=IngestStatus.ACCEPTED, 
        inspection_id="INSP-12345"
    )
    
    # Payload simulado
    dados = {"message_id": "msg-1", "schema": "ods.i8.piece_analysis"}
    payload_bytes = json.dumps(dados).encode("utf-8")
    
    # Executa o processamento interno do cliente
    mqtt_client._process_message(payload_bytes)
    
    # Verifica se o serviço de ingestão foi chamado corretamente com o dicionário
    mock_ingestion_service.ingest.assert_called_once_with(dados)
    assert "Ingestão aceite: INSP-12345" in caplog.text

def test_process_message_invalid_json_ignored(mqtt_client, mock_ingestion_service, caplog):
    """Garante que bytes que não formam um JSON válido são ignorados sem estoirar a aplicação."""
    payload_bytes = b"isto-nao-e-um-json-valido"
    
    mqtt_client._process_message(payload_bytes)
    
    # O serviço não deve ser chamado
    mock_ingestion_service.ingest.assert_not_called()
    assert "Mensagem MQTT ignorada: payload não é um JSON válido." in caplog.text

def test_process_message_duplicate_logged(mqtt_client, mock_ingestion_service, caplog):
    """Garante que mensagens duplicadas são tratadas e registadas corretamente."""
    caplog.set_level(logging.INFO, logger="backend.mqtt_client")
    mock_ingestion_service.ingest.return_value = IngestResult(
        status=IngestStatus.DUPLICATE, 
        inspection_id="INSP-99999"
    )
    
    dados = {"message_id": "msg-2"}
    mqtt_client._process_message(json.dumps(dados).encode("utf-8"))
    
    assert "Ingestão ignorada (duplicada): INSP-99999" in caplog.text