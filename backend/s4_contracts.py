"""B1 S4 schemas with the 6c envelope and A1 snapshot invariants."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from .ingestion import diagnostic_event_for_jsonb

ROOT = Path(__file__).resolve().parents[1]/'shared/schemas/s4'
FILES = {'ods.s4.capture.command':'captureCommand', 'ods.s4.capture.reply':'captureReply', 'ods.s4.clip':'clipEvent'}


class S4ContractError(ValueError): pass


def timestamp(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z',value):
        raise S4ContractError('data deve ser UTC com milissegundos')
    return datetime.strptime(value,'%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)


def uuid4(value):
    if not isinstance(value,str) or UUID(value).version != 4:
        raise S4ContractError('identificador deve ser UUID v4')


def validate(message):
    try:
        if diagnostic_event_for_jsonb(message) is None:
            raise S4ContractError('mensagem não pode ser persistida como JSON')
        schema = message['schema']
        validator = Draft202012Validator(json.loads((ROOT/(FILES[schema]+'.schema.json')).read_text()),format_checker=FormatChecker())
        validator.validate(message)
        uuid4(message['message_id'])
        timestamp(message['published_at'])
        if message['schema_version'] != '1.0': raise S4ContractError('versão S4 não suportada')
        if schema == 'ods.s4.capture.command':
            if message['producer'] != 'A1' or message['target'] != 'S4': raise S4ContractError('comando deve sair de A1 para S4')
            timestamp(message['payload']['at'])
        else:
            if message['producer'] != 'S4': raise S4ContractError('produtor deve ser S4')
            if schema == 'ods.s4.capture.reply':
                uuid4(message['correlation_id'])
            else:
                uuid4(message['session_id'])
                timestamp(message['captured_at'])
                if type(message['sequence']) is not int or message['sequence'] < 0: raise S4ContractError('sequence inválida')
                if 'correlation_id' in message: uuid4(message['correlation_id'])
                payload = message['payload']
                for key in ('start_at','end_at','expires_at'): timestamp(payload[key])
                if not re.fullmatch('[0-9a-fA-F]{64}',payload['hash_sha256']): raise S4ContractError('SHA-256 inválido')
                uuid4(payload['clip_id'])
                if payload.get('event_id') is not None: uuid4(payload['event_id'])
        return message
    except (KeyError, ValueError, TypeError, AttributeError, OSError) as exc:
        raise S4ContractError(str(exc)) from exc
    except Exception as exc:
        # jsonschema.ValidationError is intentionally translated at the boundary.
        raise S4ContractError(str(exc)) from exc


def browser_url(uri):
    """Only browser HTTP(S) URLs. s4:// requires an external access gateway."""
    parsed = urlsplit(uri)
    if parsed.scheme in {'http','https'} and parsed.hostname and not parsed.username and not parsed.password and not any(ord(c)<33 for c in uri):
        return uri
    return None
