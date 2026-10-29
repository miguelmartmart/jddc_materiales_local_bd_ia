"""Captura privada optativa, separada de RESULTADOS y sin credenciales de transporte."""
import json
from datetime import datetime, timezone


def append_turn(output, case, turn, question, answer, origin="web_real_no_erp_execution"):
    # Lista cerrada: nunca persistir el objeto HTTP ni approval/session/CSRF tokens.
    record = {'schema': 'devia-private-turn/1', 'at': datetime.now(timezone.utc).isoformat(),
              'case': case, 'turn': turn, 'question': question,
              'answer': answer.get('answer') if isinstance(answer.get('answer'), str) else '',
              'proposal_received': bool(answer.get('approval_token')),
              'erp_execution_requested': False, 'semantic_verified': False,
              'origin': origin}
    if len(record['answer']) > 16000:
        record['answer'] = record['answer'][:16000]
        record['answer_truncated'] = True
    with (output / 'CONVERSACION-PRIVADA.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')
