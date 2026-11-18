"""Consulta TCP/metadados; não publica, consome, cria tópico ou confirma offsets."""
import json,socket
from datetime import datetime,timezone
from confluent_kafka.admin import AdminClient
host,port='200.17.66.56',9093
report={'recorded_at':datetime.now(timezone.utc).isoformat(),'endpoint':f'{host}:{port}',
        'internal_endpoint_informed':'172.18.4.56:9092','internal_endpoint_tested':False,
        'operation':'TCP and cluster metadata only','messages_produced':0,
        'messages_consumed':0,'topics_created':0,'offsets_committed':0,
        'security_protocol_planned':'PLAINTEXT, conforme clientes sem TLS/SASL do guia fornecido'}
try:
    with socket.create_connection((host,port),timeout=8): report['tcp']='PASS'
except OSError as exc:
    report.update(tcp='UNAVAILABLE',tcp_error=str(exc))
if report.get('tcp')=='PASS':
    try:
        client=AdminClient({'bootstrap.servers':f'{host}:{port}','socket.timeout.ms':5000,
                            'api.version.request.timeout.ms':5000,'client.id':'VER1-metadata-read-only'})
        metadata=client.list_topics(timeout=10)
        topic=metadata.topics.get('ods.industria.defeito_classificado')
        report.update(metadata='PASS',cluster_id=metadata.cluster_id,
                      advertised_brokers=[{'id':b.id,'host':b.host,'port':b.port} for b in metadata.brokers.values()],
                      industrial_topic_present=topic is not None,
                      industrial_topic_partitions=len(topic.partitions) if topic else None)
        if topic and topic.error: report['industrial_topic_error']=str(topic.error)
    except Exception as exc:
        report.update(metadata='UNAVAILABLE',metadata_error=str(exc))
else: report['metadata']='NOT_ATTEMPTED'
print(json.dumps(report,ensure_ascii=False,indent=2))
