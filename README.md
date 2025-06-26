# Zero-Touch Entitlements: SCIM + Lambda for Dynamic AWS Access

**Event-driven IAM automation that provisions AWS permissions in real-time from Okta group changes.**

![Architecture Flow](https://img.shields.io/badge/Okta-→-blue) ![CloudTrail](https://img.shields.io/badge/CloudTrail-→-orange) ![EventBridge](https://img.shields.io/badge/EventBridge-→-green) ![Lambda](https://img.shields.io/badge/Lambda-→-red) ![AWS Identity Center](https://img.shields.io/badge/AWS_Identity_Center-✓-yellow)

## 🚀 What It Does

Zero-Touch Entitlements eliminates manual AWS permission management by automatically syncing Okta groups to AWS Identity Center permission sets. When users are added or removed from Okta groups, AWS access is instantly provisioned or revoked without human intervention.

**Key Benefits:**
- **Zero manual provisioning** - Users get AWS access in seconds, not days
- **Automatic deprovisioning** - Access is revoked immediately when users leave groups
- **Audit compliance** - Full CloudTrail logging of all permission changes
- **Security by design** - Follows principle of least privilege with group-based access

## 🏗️ Architecture

```
Okta Group Change → CloudTrail → EventBridge → Lambda → AWS Identity Center
```

The system uses AWS event-driven architecture to process Okta SCIM events:

1. **Okta** - Identity source with SCIM provisioning enabled
2. **CloudTrail** - Captures CreateGroup/DeleteGroup API events
3. **EventBridge** - Routes events to Lambda functions
4. **Lambda** - Processes events and manages AWS permissions
5. **DynamoDB** - Tracks group-to-permission-set mappings
6. **AWS Identity Center** - Target for permission provisioning

## 📋 Prerequisites

- AWS Account with Identity Center enabled
- Okta org with SCIM provisioning configured
- Python 3.9+ runtime environment
- AWS CLI configured with appropriate permissions

**Required AWS Permissions:**
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sso-admin:*",
                "identitystore:*",
                "organizations:ListAccounts",
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```

## ⚙️ Setup & Deployment

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/zero-touch-entitlements
cd zero-touch-entitlements
```

### 2. Create DynamoDB Table
```bash
aws dynamodb create-table \
    --table-name entitlements \
    --attribute-definitions \
        AttributeName=groupid,AttributeType=S \
    --key-schema \
        AttributeName=groupid,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST
```

### 3. Deploy Lambda Function
```bash
# Package the function
zip -r entitlements-lambda.zip lambda_function.py

# Create Lambda function
aws lambda create-function \
    --function-name entitlements-processor \
    --runtime python3.9 \
    --role arn:aws:iam::YOUR-ACCOUNT:role/lambda-execution-role \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://entitlements-lambda.zip \
    --timeout 300
```

### 4. Configure EventBridge Rule
```bash
aws events put-rule \
    --name okta-group-events \
    --event-pattern '{
        "source": ["aws.sso"],
        "detail-type": ["AWS API Call via CloudTrail"],
        "detail": {
            "eventName": ["CreateGroup", "DeleteGroup"]
        }
    }'

aws events put-targets \
    --rule okta-group-events \
    --targets "Id"="1","Arn"="arn:aws:lambda:region:account:function:entitlements-processor"
```

## 🎯 Usage

### Naming Convention

The system follows a specific naming convention for automatic mapping:

- **Okta Groups**: `{account-name}-{role}`
  - Example: `aws-dev-sandbox-developer`
- **Permission Sets**: `{role}_DERIVED`
  - Example: `developer_DERIVED`
- **AWS Accounts**: `aws-{environment}-{type}-{counter}`
  - Example: `aws-dev-sandbox-01`

### Group Creation Flow

1. **Create Permission Set** in AWS Identity Center:
   ```
   Name: developer_DERIVED
   Description: Developer access permissions
   ```

2. **Create Okta Group**:
   ```
   Name: aws-dev-sandbox-developer
   Description: Developers for sandbox environment
   ```

3. **Automatic Provisioning**: The system automatically:
   - Detects the new group via CloudTrail
   - Maps it to the `developer_DERIVED` permission set
   - Provisions access to the target AWS account
   - Stores the mapping in DynamoDB

### Deprovisioning

When groups are deleted in Okta:
1. CloudTrail captures the DeleteGroup event
2. Lambda retrieves the permission set mapping from DynamoDB
3. Access is automatically revoked from the AWS account
4. Audit trail is maintained in CloudWatch Logs

## 🔧 Configuration

### Environment Variables

Set these in your Lambda function:

```bash
DYNAMODB_TABLE=entitlements
LOG_LEVEL=INFO
```

### Permission Set Templates

Create permission sets in AWS Identity Center following the naming pattern:
- `developer_DERIVED` - Development environment access
- `admin_DERIVED` - Administrative access
- `readonly_DERIVED` - Read-only access

## 📊 Monitoring & Troubleshooting

### CloudWatch Logs
Monitor Lambda execution:
```bash
aws logs tail /aws/lambda/entitlements-processor --follow
```

### Common Issues

**Permission Set Not Found**
```
ERROR: Permission Set - developer_DERIVED for the User group - aws-dev-sandbox-developer is NOT PRESENT
```
*Solution*: Create the permission set in AWS Identity Center with the correct naming convention.

**Group Sync Delay**
```
Group was not found in User groups (Perhaps it hasn't sync'd yet?)
```
*Solution*: SCIM sync can take 1-2 minutes. The system will retry automatically.

### Success Indicators
```
Success: Attached Permission Set - developer_DERIVED to AWS Account - 123456789012 for OKTA Group - aws-dev-sandbox-developer
```
### Demo
```
https://vimeo.com/manage/videos/1096741892/1df4ac1f6b
```
## 🛡️ Security Considerations

- **Least Privilege**: Lambda execution role has minimal required permissions
- **Audit Trail**: All actions logged via CloudTrail and CloudWatch
- **Automatic Cleanup**: Orphaned permissions are prevented through automatic deprovisioning
- **Group-Based Access**: Individual user permissions managed through group membership

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Related Documentation

- [AWS Identity Center API Reference](https://docs.aws.amazon.com/singlesignon/latest/APIReference/)
- [Okta SCIM Provisioning Guide](https://developer.okta.com/docs/concepts/scim/)
- [AWS EventBridge User Guide](https://docs.aws.amazon.com/eventbridge/latest/userguide/)

---

**Need Help?** Open an issue or contact the maintainers.

**⭐ Like this project?** Give it a star and share with your team!
