import json
import logging
import paho.mqtt.client as mqtt
from typing import Any

logger = logging.getLogger(__name__)

class A1IngestionClient:
    def __init__(self, broker_url: str, ingestion_service: Any, broker_port: int = 1883):
        self.broker_url = broker_url
        self.broker_port = broker_port
        self.ingestion_service = ingestion_service
        self.topic = "ods/i8/piece_analysis"
        self.client_id = "a1_backend_i8_consumer"
        
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
            client_id=self.client_id, 
            clean_session=False
        )
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)
        
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Ligado ao broker MQTT em {self.broker_url}:{self.broker_port}.")
            self.client.subscribe(self.topic, qos=1)
        else:
            logger.error(f"Falha na ligação MQTT. Código de erro: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.warning(f"Desligado do broker MQTT (código {rc}). A tentar reconectar...")

    def _on_message(self, client, userdata, msg):
        try:
            self._process_message(msg.payload)
        except Exception as err:
            logger.error(f"Erro inesperado no processamento da mensagem MQTT: {err}", exc_info=True)

    def _process_message(self, raw_payload: bytes):
        #Descodificação primária da rede (bytes para dict)
        try:
            dados = json.loads(raw_payload.decode('utf-8'))
        except json.JSONDecodeError:
            logger.error("Mensagem MQTT ignorada: payload não é um JSON válido.")
            return

        #Entrega ao IngestionService (que trata validação, triagem e persistência)
        result = self.ingestion_service.ingest(dados)
        
        #Log do resultado com base na resposta do motor de ingestão
        if result.status.value == "ACCEPTED":
            logger.info(f"Ingestão aceite: {result.inspection_id}")
        elif result.status.value == "DUPLICATE":
            logger.info(f"Ingestão ignorada (duplicada): {result.inspection_id}")
        elif result.status.value == "REJECTED":
            logger.warning(f"Ingestão rejeitada: {result.reason}")

    def start(self):
        logger.info(f"A arrancar subscrição MQTT no tópico {self.topic}...")
        self.client.connect(self.broker_url, self.broker_port, keepalive=60)
        self.client.loop_start()
        
    def stop(self):
        logger.info("A encerrar cliente MQTT graciosamente...")
        self.client.loop_stop()
        self.client.disconnect()