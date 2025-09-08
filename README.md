# Financial Transaction Risk Analyzer (AWS Serverless)

Real-time pipeline that ingests card transactions, scores risk with explainable rules, and alerts on suspicious activity. Raw events land in S3 for Glue/Athena analytics; flagged cases go to DynamoDB. CI/CD via GitHub Actions.

## Architecture
```mermaid
flowchart LR
  U[Client / Postman] -->|POST /ingest| APIG[API Gateway]
  APIG --> ING[Lambda: Ingest & Risk Score]

  ING -->|raw JSON dt-hour| S3[(S3 Data Lake)]
  ING -->|flag high-risk| DDB1[(DynamoDB: suspicious)]
  ING -->|user state| DDB2[(DynamoDB: userstate)]
  ING -->|alerts| SNS[(SNS Alerts)]
  ING -.-> LOG1[(CloudWatch Logs)]

  EVB[EventBridge hourly] --> AGG[Lambda: Aggregator]
  AGG -->|summaries| S3A[(S3 Aggregates)]
  AGG -.-> LOG2[(CloudWatch Logs)]

  S3 --> CRAWLER[Glue Crawler]
  CRAWLER --> CATALOG[Glue Data Catalog finance-risk_db]
  ATH[Athena SQL] --> CATALOG
  QS[QuickSight Dashboards] --> ATH
