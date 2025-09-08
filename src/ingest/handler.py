import os, json, uuid, time, datetime
import boto3
from decimal import Decimal

s3 = boto3.client('s3')
ddb = boto3.resource('dynamodb')
sns = boto3.client('sns')

BUCKET = os.environ['BUCKET_NAME']
SUSPICIOUS_TABLE = ddb.Table(os.environ['SUSPICIOUS_TABLE'])
USERSTATE_TABLE = ddb.Table(os.environ['USERSTATE_TABLE'])
ALERTS_TOPIC_ARN = os.environ['ALERTS_TOPIC_ARN']
HOME_COUNTRY = os.environ.get('HOME_COUNTRY', 'AU')
HIGH_AMOUNT = float(os.environ.get('HIGH_AMOUNT', '1000'))
FOREIGN_AMOUNT = float(os.environ.get('FOREIGN_AMOUNT', '500'))
HIGH_RISK_THRESHOLD = float(os.environ.get('HIGH_RISK_THRESHOLD', '0.85'))

RULE_WEIGHTS = {
    'HIGH_AMOUNT': 0.6,
    'FOREIGN_HIGH': 0.7,
    'RAPID_FIRE': 0.5,
}

def _utc_parts(ts_ms: int):
    dt = datetime.datetime.utcfromtimestamp(ts_ms/1000)
    return dt.strftime('%Y-%m-%d'), dt.strftime('%H')

def _get_userstate(user_id: str):
    resp = USERSTATE_TABLE.get_item(Key={'user_id': user_id})
    return resp.get('Item') or {}

def _put_userstate(user_id: str, last_ts_ms: int, last_country: str, rapid_count: int):
    USERSTATE_TABLE.put_item(Item={
        'user_id': user_id,
        'last_ts_ms': Decimal(str(last_ts_ms)),
        'last_country': last_country,
        'rapid_count': rapid_count,
        'updated_at': int(time.time())
    })

def _risk_score(rules_triggered):
    # Combine weights without exceeding 1.0: 1 - prod(1 - w)
    score = 0.0
    for r in rules_triggered:
        w = RULE_WEIGHTS.get(r, 0.4)
        score = 1 - (1 - score) * (1 - w)
    return round(min(score, 1.0), 3)

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body') or '{}')
    except json.JSONDecodeError:
        return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid JSON'})}

    required = ['user_id','amount','currency','merchant','country','city','device_id','channel']
    if any(k not in body for k in required):
        return {'statusCode': 400, 'body': json.dumps({'error': f'Missing fields. Required: {required}'})}

    txn = {
        'txn_id': body.get('txn_id') or str(uuid.uuid4()),
        'user_id': body['user_id'],
        'amount': float(body['amount']),
        'currency': body['currency'],
        'merchant': body['merchant'],
        'mcc': body.get('mcc'),
        'channel': body['channel'],
        'country': body['country'],
        'city': body['city'],
        'device_id': body['device_id'],
        'timestamp_utc': body.get('timestamp_utc') or datetime.datetime.utcnow().isoformat()+'Z',
    }

    ts_ms = int(body.get('timestamp_ms') or int(time.time()*1000))
    date_str, hour_str = _utc_parts(ts_ms)

    rules = []
    if txn['amount'] >= HIGH_AMOUNT:
        rules.append('HIGH_AMOUNT')
    if txn['country'] != HOME_COUNTRY and txn['amount'] >= FOREIGN_AMOUNT:
        rules.append('FOREIGN_HIGH')

    # Simple velocity: multiple >=200 within 60s
    userstate = _get_userstate(txn['user_id'])
    rapid_count = int(userstate.get('rapid_count', 0))
    last_ts_ms = int(userstate.get('last_ts_ms', 0))
    if last_ts_ms and (ts_ms - last_ts_ms) <= 60_000 and txn['amount'] >= 200:
        rapid_count += 1
        if rapid_count >= 3:
            rules.append('RAPID_FIRE')
    else:
        rapid_count = 1
    _put_userstate(txn['user_id'], ts_ms, txn['country'], rapid_count)

    risk = _risk_score(rules)
    explanation = {
        'rules': rules,
        'high_amount_threshold': HIGH_AMOUNT,
        'foreign_amount_threshold': FOREIGN_AMOUNT,
        'home_country': HOME_COUNTRY
    }

    key = f"transactions/raw/dt={date_str}/hour={hour_str}/txn-{txn['txn_id']}.json"
    s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps({**txn, 'risk': risk, 'rules': rules}))

    alert_sent = False
    if risk >= HIGH_RISK_THRESHOLD:
        SUSPICIOUS_TABLE.put_item(Item={
            'txn_id': txn['txn_id'],
            'user_id': txn['user_id'],
            'amount': Decimal(str(txn['amount'])),
            'currency': txn['currency'],
            'merchant': txn['merchant'],
            'country': txn['country'],
            'city': txn['city'],
            'device_id': txn['device_id'],
            'timestamp_ms': Decimal(str(ts_ms)),
            'risk_score': Decimal(str(risk)),
            'explanation': json.dumps(explanation),
            'created_at': int(time.time())
        })
        sns.publish(
            TopicArn=ALERTS_TOPIC_ARN,
            Subject=f"High-risk txn {txn['txn_id']} (score {risk})",
            Message=json.dumps({'transaction': txn, 'risk': risk, 'explanation': explanation})
        )
        alert_sent = True

    return {
        'statusCode': 201,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'txn_id': txn['txn_id'], 'risk': risk, 'rules': rules, 'alert_sent': alert_sent})
    }
