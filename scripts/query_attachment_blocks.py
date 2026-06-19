#!/usr/bin/env python3
"""Query content_blocks for attachment-category messages from the live DB."""
import csv
import json
import os

import psycopg2

from nacos_config import connect_database, load_nacos_config

SCRIPT_DIR = os.path.dirname(__file__)
JSON_PATH = os.path.join(SCRIPT_DIR, "first_qa_per_conversation_deduplicated.json")
CSV_PATH = os.path.join(SCRIPT_DIR, "qa_classification.csv")
OUTPUT_CSV = CSV_PATH

# 1. Load original JSON to get message IDs
with open(JSON_PATH) as f:
    data = json.load(f)

# 2. Load CSV to find attachment conversation IDs
with open(CSV_PATH, 'r', encoding='utf-8') as f:
    reader = list(csv.DictReader(f))

attachment_convs = {r['conversation_id'] for r in reader if r['category'] == 'attachment'}
print(f"Attachment conversations: {len(attachment_convs)}")

# 3. Build message ID maps
id_map = {}
for r in data:
    if r['conversation_id'] in attachment_convs:
        id_map[r['conversation_id']] = {
            'user_message_id': r['user_message_id'],
            'assistant_message_id': r['assistant_message_id'],
        }

all_user_ids = [v['user_message_id'] for v in id_map.values()]
all_asst_ids = [v['assistant_message_id'] for v in id_map.values()]
all_ids = all_user_ids + all_asst_ids

# 4. Query DB
config = load_nacos_config(prod=True)
conn = connect_database(config)
cur = conn.cursor()
cur.execute(
    'SELECT id, role, content_blocks FROM messages WHERE id = ANY(%s)',
    (all_ids,)
)

db_results = {}
for row in cur.fetchall():
    msg_id, role, cb_raw = row
    blocks = []
    if cb_raw:
        raw = cb_raw
        if isinstance(raw, str):
            raw = raw.replace('\\u0000', '')
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(parsed, list):
                blocks = parsed
        except Exception as e:
            blocks = [{'parse_error': str(e)}]
    db_results[msg_id] = {'role': role, 'blocks': blocks}

print(f"Found {len(db_results)} messages in DB")
conn.close()

# 5. Extract multimodal content_blocks for each attachment conversation
# Multimodal types: image, pdf, markdown, kb_context (not text/tool_use/tool_result/thinking)
MULTIMODAL_TYPES = {'image', 'pdf', 'markdown', 'kb_context'}

attachment_content = {}  # conversation_id -> JSON string of multimodal blocks

for conv_id, ids in id_map.items():
    user_blocks = db_results.get(ids['user_message_id'], {}).get('blocks', [])
    asst_blocks = db_results.get(ids['assistant_message_id'], {}).get('blocks', [])

    # Extract multimodal blocks from user message
    multimodal_blocks = []
    for b in user_blocks:
        if isinstance(b, dict) and b.get('type') in MULTIMODAL_TYPES:
            # Truncate large fields for CSV readability
            block_summary = {
                'type': b.get('type'),
                'source_type': b.get('source', {}).get('type', '') if isinstance(b.get('source'), dict) else '',
                'media_type': b.get('source', {}).get('media_type', '') if isinstance(b.get('source'), dict) else '',
            }
            # For text-based blocks (markdown, kb_context), include truncated text
            if 'text' in b:
                block_summary['text_preview'] = b['text'][:200] + ('...' if len(b.get('text', '')) > 200 else '')
            if 'url' in b:
                block_summary['url'] = b['url'][:100]
            multimodal_blocks.append(block_summary)

    # Also check assistant blocks for multimodal content
    for b in asst_blocks:
        if isinstance(b, dict) and b.get('type') in MULTIMODAL_TYPES:
            block_summary = {
                'type': b.get('type'),
                'source_type': b.get('source', {}).get('type', '') if isinstance(b.get('source'), dict) else '',
                'media_type': b.get('source', {}).get('media_type', '') if isinstance(b.get('source'), dict) else '',
            }
            if 'text' in b:
                block_summary['text_preview'] = b['text'][:200] + ('...' if len(b.get('text', '')) > 200 else '')
            multimodal_blocks.append(block_summary)

    attachment_content[conv_id] = json.dumps(multimodal_blocks, ensure_ascii=False) if multimodal_blocks else ''

# 6. Update CSV with new column
for row in reader:
    row['multimodal_content_blocks'] = attachment_content.get(row['conversation_id'], '')

fields = list(reader[0].keys())
with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(reader)

# 7. Print summary
print(f"\n=== multimodal content_blocks 详情 ===")
for row in reader:
    if row['category'] == 'attachment':
        cb = row['multimodal_content_blocks']
        parsed = json.loads(cb) if cb else []
        types = [b['type'] for b in parsed]
        print(f"  {row['conversation_id'][:8]} | {row['user_question'][:40]:40s} | blocks: {types}")

print(f"\nCSV 已更新: {OUTPUT_CSV}")
