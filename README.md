# Financial Transaction Risk Analyzer (AWS Serverless)

Real-time pipeline that ingests card transactions, scores risk with explainable rules, and alerts on suspicious activity. Raw events land in S3 for Glue/Athena analytics; flagged cases go to DynamoDB. CI/CD via GitHub Actions.

![Architecture – API Gateway → Lambda → S3/DynamoDB/SNS → Glue/Athena](diagram/architecture.png)

## 🧪 Run it yourself (step-by-step)

### 0) Prerequisites
- AWS account with permissions for Lambda, API Gateway, DynamoDB, S3, SNS, EventBridge, Glue, Athena
- **AWS CLI v2**, **SAM CLI**, **Python 3.11**, **Git**
- Set region (adjust if needed):
```bash
aws configure set region ap-southeast-2
aws sts get-caller-identity


