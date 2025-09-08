# Financial Transaction Risk Analyzer (AWS Serverless)

Real-time pipeline that ingests card transactions, scores risk with explainable rules, and alerts on suspicious activity. Raw events land in S3 for Glue/Athena analytics; flagged cases go to DynamoDB. CI/CD via GitHub Actions.

![Architecture – API Gateway → Lambda → S3/DynamoDB/SNS → Glue/Athena](diagram/architecture.png)

