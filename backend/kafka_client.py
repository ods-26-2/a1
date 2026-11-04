"""Cliente Kafka para consumo de eventos (ods.industria.defeito_classificado) no módulo A1."""

import os
import json
import logging
from confluent_kafka import Consumer

# Configuração básica de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class A1KafkaConsumer:
    def __init__(self, ingestion_service):
        """
        Inicializa o consumidor Kafka injetando o IngestionService para processamento.
        """
        broker_url = os.getenv('KAFKA_BROKER_URL', '34.66.235.91:9093')
        group_id = 'VER-1-A1-Consumer'
        
        conf = {
            'bootstrap.servers': broker_url,
            'group.id': group_id,
            'auto.offset.reset': 'earliest',
            'session.timeout.ms': 10000 
        }
        
        logging.info(f"Inicializando o consumidor Kafka no broker: {broker_url}")
        self.consumer = Consumer(conf)
        self.ingestion_service = ingestion_service
        self.running = False
        
        # Regras do contrato B2
        self.CAMPOS_OBRIGATORIOS = [
            'message_id', 'message_type', 'schema', 'schema_version',
            'producer', 'occurred_at', 'payload'
        ]
        self.SCHEMA_ESPERADO = 'ods.industria.defeito_classificado'
        self.PRODUTOR_ESPERADO = 'I8'

    def assinar_topico(self):
        self.consumer.subscribe([self.SCHEMA_ESPERADO])
        logging.info(f"Consumidor assinou o tópico: {self.SCHEMA_ESPERADO}")

    def _validar_envelope(self, evento):
        for campo in self.CAMPOS_OBRIGATORIOS:
            if campo not in evento:
                return False, f"Campo ausente: {campo}"
        
        if evento.get('schema') != self.SCHEMA_ESPERADO:
            return False, f"Schema inesperado: {evento.get('schema')}"
            
        if str(evento.get('producer')).upper() != self.PRODUTOR_ESPERADO:
            return False, f"Produtor ignorado: {evento.get('producer')}"
            
        if not isinstance(evento.get('payload'), dict):
            return False, "Payload não é um dicionário JSON."
            
        return True, None

    def comecar_a_consumir(self):
        """Laço principal de polling. Deve ser executado numa Thread separada."""
        self.assinar_topico()
        self.running = True
        logging.info("A iniciar o laço de consumo (Polling) do Kafka...")

        try:
            while self.running:
                msg = self.consumer.poll(1.0)
                
                if msg is None:
                    continue
                if msg.error():
                    logging.warning(f"Erro no Kafka: {msg.error()}")
                    continue

                # Desserialização Defensiva
                try:
                    evento = json.loads(msg.value().decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    logging.warning("Mensagem descartada: JSON ou encoding inválido")
                    continue

                # Validação de Negócio (Envelope B2)
                valido, motivo = self._validar_envelope(evento)
                if not valido:
                    logging.warning(f"Mensagem descartada: {motivo}")
                    continue
                
                # Gravação e Deduplicação via IngestionService
                try:
                    # Chama o motor agnóstico do Samuel (ingestion.py)
                    resultado = self.ingestion_service.ingest(evento)
                    
                    # Garantir a extração do nome do Enum ou string dependendo da implementação
                    status_nome = resultado.status.name if hasattr(resultado.status, 'name') else str(resultado.status)
                    
                    if status_nome == "ACCEPTED":
                        logging.info(f"Inspeção {resultado.inspection_id} aceite e gravada no A1.")
                    elif status_nome == "DUPLICATE":
                        logging.info(f"Mensagem {evento['message_id']} ignorada: Já existe (Deduplicação).")
                    elif status_nome == "REJECTED":
                        logging.warning(f"Mensagem {evento['message_id']} rejeitada: {resultado.reason}")
                        
                except Exception as e:
                    logging.error(f"Erro interno e inesperado ao processar evento: {e}")

        except Exception as e:
            logging.error(f"Erro fatal no laço de consumo: {e}")
        finally:
            logging.info("A fechar a ligação ao Kafka para libertar recursos...")
            self.consumer.close()
            logging.info("Consumidor encerrado de forma limpa.")

    def parar(self):
        """Método chamado pelo lifespan do FastAPI para desligar a thread suavemente."""
        logging.info("Sinal de paragem recebido. A interromper o laço de consumo...")
        self.running = False