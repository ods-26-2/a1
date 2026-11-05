"""Cliente Kafka para consumo de eventos no módulo A1, com commit após persistência."""

import json
import logging
import math
import threading
import time
from confluent_kafka import Consumer, KafkaError

from .config import KafkaSettings
from .contracts import ContractValidationError, validate_piece_analysis

# Configuração básica de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOGGER = logging.getLogger(__name__)


class A1KafkaConsumer:
    def __init__(self, ingestion_service, *, settings=None, consumer_factory=Consumer,
                 monotonic=time.monotonic):
        """
        Inicializa o consumidor Kafka injetando o IngestionService para processamento.
        """
        self.settings = settings or KafkaSettings.from_env()
        self.ingestion_service = ingestion_service
        self._monotonic = monotonic
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.running = False
        self._connected = False
        self._assigned = False
        self._retrying = False
        self._fatal = None
        self._detail = "Consumidor ainda não iniciado."
        self._next_probe = 0.0
        conf = {
            'bootstrap.servers': self.settings.broker_url,
            'group.id': self.settings.group_id,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False,
            'enable.auto.offset.store': False,
            'allow.auto.create.topics': False,
            'session.timeout.ms': 10000,
            'socket.timeout.ms': 5000,
            'max.poll.interval.ms': 300000,
            'error_cb': self._on_error,
        }
        self.consumer = consumer_factory(conf)

        # Roteamento Kafka; a validação do par schema/version fica no contrato.
        self.TOPICO_KAFKA = self.settings.topic

    def _on_error(self, error):
        with self._lock:
            self._connected = False
            self._detail = f"Erro Kafka: {error}"

    def _on_assign(self, consumer, partitions):
        # An empty assignment can be legitimate when a group has idle members.
        with self._lock:
            self._assigned = True

    def _on_revoke(self, consumer, partitions):
        with self._lock:
            self._assigned = False

    def assinar_topico(self):
        self.consumer.subscribe([self.TOPICO_KAFKA], on_assign=self._on_assign,
                                on_revoke=self._on_revoke, on_lost=self._on_revoke)
        LOGGER.info("Consumidor assinou o tópico Kafka: %s", self.TOPICO_KAFKA)

    def _validar_envelope(self, evento):
        # Validação de Negócio (Envelope B2)
        try:
            validate_piece_analysis(evento)
            return True, None
        except ContractValidationError as exc:
            return False, str(exc)

    def _probe_broker(self):
        try:
            metadata = self.consumer.list_topics(timeout=self.settings.health_timeout)
            topic = metadata.topics.get(self.TOPICO_KAFKA)
            if not metadata.brokers or topic is None or topic.error is not None:
                raise RuntimeError("Broker ou tópico configurado indisponível")
        except Exception as exc:
            self._on_error(exc)
        else:
            with self._lock:
                self._connected = True
                self._detail = f"Broker acessível; tópico {self.TOPICO_KAFKA}."
        self._next_probe = self._monotonic() + self.settings.health_interval

    def health_snapshot(self):
        with self._lock:
            up = (self.running and self._connected and self._assigned
                  and not self._retrying and not self._fatal and not self._stop.is_set())
            detail = self._fatal or self._detail
            if self._stop.is_set() and not self._fatal:
                detail = "Consumidor encerrando ou encerrado."
            elif self.running and not self._assigned and not self._retrying:
                detail = f"Aguardando atribuição do grupo {self.settings.group_id}. {detail}"
            return {"name": "i8-subscriber", "status": "UP" if up else "DOWN",
                    "detail": detail}

    def _retry(self, operation, label):
        delay = self.settings.retry_initial
        for attempt in range(self.settings.retry_attempts):
            try:
                result = operation()
            except Exception as exc:
                with self._lock:
                    self._retrying = True
                    self._detail = f"{label}: {type(exc).__name__}: {exc}"
                LOGGER.warning("%s; tentativa %s/%s", self._detail,
                               attempt + 1, self.settings.retry_attempts)
                if attempt + 1 == self.settings.retry_attempts:
                    with self._lock:
                        self._fatal = f"{label}: tentativas esgotadas; offset permanece sem confirmação."
                    self._stop.set()
                    return False, None
                if self._stop.wait(delay):
                    return False, None
                delay = min(delay * 2, self.settings.retry_max)
            else:
                with self._lock:
                    if self._retrying:
                        self._detail = f"{label}: recuperado; tópico {self.TOPICO_KAFKA}."
                    self._retrying = False
                return True, result
        return False, None

    @staticmethod
    def _invalid_number(value):
        raise ValueError(f"Número JSON inválido: {value}")

    @staticmethod
    def _finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"Número JSON fora do intervalo suportado: {value}")
        return parsed

    @staticmethod
    def _ensure_jsonb_safe(value):
        """Reject decoded values that PostgreSQL jsonb cannot represent."""
        pending = [(value, 0)]
        while pending:
            current, depth = pending.pop()
            if depth > 100:
                raise ValueError("JSON excede profundidade máxima de 100 níveis")
            if isinstance(current, str):
                if "\x00" in current:
                    raise ValueError("String JSON contém caractere nulo")
                try:
                    current.encode("utf-8", errors="strict")
                except UnicodeEncodeError as exc:
                    raise ValueError("String JSON contém Unicode inválido") from exc
            elif isinstance(current, float):
                if not math.isfinite(current):
                    raise ValueError("Número JSON deve ser finito")
            elif isinstance(current, dict):
                pending.extend((item, depth + 1) for item in current.keys())
                pending.extend((item, depth + 1) for item in current.values())
            elif isinstance(current, list):
                pending.extend((item, depth + 1) for item in current)

    def _process_message(self, msg):
        # Desserialização Defensiva
        try:
            raw = msg.value()
            if raw is None:
                raise ValueError("Valor Kafka nulo (tombstone)")
            evento = json.loads(
                raw.decode('utf-8'),
                parse_constant=self._invalid_number,
                parse_float=self._finite_float,
            )
            self._ensure_jsonb_safe(evento)
        except (ValueError, UnicodeDecodeError, AttributeError, RecursionError) as exc:
            reason = (f"JSON/encoding inválido: {exc}; topic={msg.topic()} "
                      f"partition={msg.partition()} offset={msg.offset()}")
            process = lambda: self.ingestion_service.reject_transport_message(reason)
        else:
            # Gravação e Deduplicação via IngestionService
            def process():
                # Chama o motor agnóstico do Samuel (ingestion.py)
                return self.ingestion_service.ingest(evento)

        def persist():
            resultado = process()
            # Garantir a extração do nome do Enum ou string dependendo da implementação
            status_nome = resultado.status.name if hasattr(resultado.status, 'name') else str(resultado.status)
            if status_nome not in {"ACCEPTED", "DUPLICATE", "REJECTED"}:
                raise RuntimeError(f"Resultado de ingestão desconhecido: {status_nome}")
            return resultado

        ok, resultado = self._retry(persist, "Falha ao persistir mensagem")
        if not ok:
            return False

        def commit():
            partitions = self.consumer.commit(message=msg, asynchronous=False)
            for partition in partitions or ():
                if partition.error is not None:
                    raise RuntimeError(str(partition.error))

        ok, _ = self._retry(commit, "Falha ao confirmar offset")
        if ok:
            LOGGER.info("Mensagem processada: %s; topic=%s partition=%s offset=%s",
                        resultado.status, msg.topic(), msg.partition(), msg.offset())
        return ok

    def comecar_a_consumir(self):
        """Laço principal de polling. Deve ser executado numa Thread separada."""
        try:
            # Preserve a stop requested before the worker was scheduled.
            if self._stop.is_set():
                return
            self.running = True
            self.assinar_topico()
            LOGGER.info("A iniciar o laço de consumo (Polling) do Kafka...")
            while not self._stop.is_set():
                if self._monotonic() >= self._next_probe:
                    self._probe_broker()
                msg = self.consumer.poll(self.settings.poll_timeout)
                if msg is None:
                    continue
                if self._stop.is_set():
                    break
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        self._on_error(msg.error())
                        LOGGER.warning("Erro no Kafka: %s", msg.error())
                    continue
                # No later record can bypass a failed persist/commit on any partition.
                if not self._process_message(msg):
                    break
        except Exception as exc:
            with self._lock:
                self._fatal = f"Erro fatal no laço de consumo: {type(exc).__name__}: {exc}"
            LOGGER.exception("Erro fatal no laço de consumo")
        finally:
            LOGGER.info("A fechar a ligação ao Kafka para libertar recursos...")
            try:
                self.consumer.close()
            finally:
                self.running = False
                with self._lock:
                    self._connected = False
            LOGGER.info("Consumidor encerrado de forma limpa.")

    def parar(self):
        """Método chamado pelo lifespan do FastAPI para desligar a thread suavemente."""
        LOGGER.info("Sinal de paragem recebido. A interromper o laço de consumo...")
        self._stop.set()
