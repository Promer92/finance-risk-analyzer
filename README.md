# Financial Transaction Risk Analyzer (AWS Serverless)

Real-time pipeline that ingests card transactions, scores risk with explainable rules, and alerts on suspicious activity. Raw events land in S3 for Glue/Athena analytics; flagged cases go to DynamoDB. CI/CD via GitHub Actions.

![Architecture – API Gateway → Lambda → S3/DynamoDB/SNS → Glue/Athena](diagram/architecture.png)

🧪 Run it yourself (step-by-step)
1) Prerequisites
AWS account with permissions for Lambda, API Gateway, DynamoDB, S3, SNS, EventBridge, Glue, Athena
AWS CLI v2, SAM CLI, Python 3.11, Git
Set your default region (adjust if you prefer another):
aws configure set region ap-southeast-2
aws sts get-caller-identity   # should print your Account/Arn

2) Clone the repo
git clone https://github.com/<your-username>/finance-risk-analyzer.git
cd finance-risk-analyzer

3) Build & deploy (SAM)
sam build
sam deploy --guided \
  --stack-name finance-risk \
  --parameter-overrides \
    ProjectName=finance-risk \
    HomeCountry=AU \
    HighAmountThreshold=1000 \
    ForeignAmountThreshold=500 \
    HighRiskThreshold=0.85
# Choose "Save arguments to samconfig.toml" = Yes
After deploy, note the Outputs:
ApiUrl — POST endpoint (ends with /Prod/ingest)
AlertsTopicArn — SNS topic for email alerts
DataLakeBucketName — S3 bucket for raw/agg data
GlueDatabaseName — Glue/Athena DB (e.g., finance-risk_db)
(You can fetch them anytime with:)
STACK=finance-risk
API=$(aws cloudformation describe-stacks --stack-name $STACK --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
TOPIC=$(aws cloudformation describe-stacks --stack-name $STACK --query "Stacks[0].Outputs[?OutputKey=='AlertsTopicArn'].OutputValue" --output text)
BUCKET=$(aws cloudformation describe-stacks --stack-name $STACK --query "Stacks[0].Outputs[?OutputKey=='DataLakeBucketName'].OutputValue" --output text)
DB=$(aws cloudformation describe-stacks --stack-name $STACK --query "Stacks[0].Outputs[?OutputKey=='GlueDatabaseName'].OutputValue" --output text)
echo -e "API=$API\nTOPIC=$TOPIC\nBUCKET=$BUCKET\nDB=$DB"

4) Subscribe to alerts (confirm the email)
aws sns subscribe --topic-arn "$TOPIC" --protocol email --notification-endpoint you@example.com
# Open the confirmation email and click “Confirm subscription”.

5) Send test transactions
High-risk example (should trigger an alert):
curl -s -X POST "$API" -H 'Content-Type: application/json' -d '{
  "user_id":"U123",
  "amount":1200.00,
  "currency":"AUD",
  "merchant":"Electronics World",
  "mcc":"5732",
  "channel":"ecomm",
  "country":"US",
  "city":"San Francisco",
  "device_id":"dev-abc-123"
}' | jq
Low-risk example (no alert):
curl -s -X POST "$API" -H 'Content-Type: application/json' -d '{
  "user_id":"U1",
  "amount": 20,
  "currency": "AUD",
  "merchant": "Coffee Bar",
  "channel": "pos",
  "country": "AU",
  "city": "Melbourne",
  "device_id": "dev-1"
}' | jq

6) Check data landed
# S3 raw events (partitioned by dt/hour)
aws s3 ls "s3://$BUCKET/transactions/raw/" --recursive | head

# DynamoDB flags (high-risk only)
aws dynamodb scan --table-name finance-risk-suspicious --max-items 5

7) Analytics (Glue + Athena)
Start/refresh the crawler, then query in Athena:
aws glue start-crawler --name finance-risk-crawler
In Athena (same region):
MSCK REPAIR TABLE "finance-risk_db"."raw";

-- Count by partition
SELECT dt, hour, COUNT(*) AS n
FROM "finance-risk_db"."raw"
GROUP BY dt, hour
ORDER BY dt DESC, hour DESC
LIMIT 20;

-- Rules hit breakdown
SELECT r AS rule, COUNT(*) AS hits
FROM "finance-risk_db"."raw"
CROSS JOIN UNNEST(rules) AS t(r)
GROUP BY r
ORDER BY hits DESC;

8) Logs & troubleshooting
sam logs -n IngestFunction --stack-name finance-risk --tail
# Common quick fixes:
# - HandlerNotFound → ensure src/ingest/handler.py defines `lambda_handler`
# - AccessDenied → re-deploy; policies are in template.yaml

9) (Optional) Run locally (no AWS costs)
# Start a local API on http://127.0.0.1:3000
sam local start-api
# Then POST to: http://127.0.0.1:3000/ingest

10) Clean up (avoid charges)
# Empty the (versioned) bucket first
aws s3 rm "s3://$BUCKET" --recursive

# Delete the stack
sam delete --stack-name finance-risk

# Optional: remove Lambda log groups
aws logs delete-log-group --log-group-name /aws/lambda/finance-risk-ingest 2>/dev/null || true
aws logs delete-log-group --log-group-name /aws/lambda/finance-risk-aggregate 2>/dev/null || true
🔒 Notes
The /ingest endpoint is public for demo. For production, enable IAM auth or an API key and add a resource policy.
Thresholds are configurable via SAM parameters: HighAmountThreshold, ForeignAmountThreshold, HighRiskThreshold, HomeCountry.

