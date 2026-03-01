# BinAlerts

Scrapes Shropshire Council bin collection dates and sends Telegram notifications the day before.

## Architecture

- **Lambda Function**: Runs daily at 19:07 using EventBridge
- **Docker Container**: Playwright + Chromium built-in (avoids bot detection, more reliable than layers)
- **SSM Parameter Store**: Configuration storage (free tier)
- **x86_64 Architecture**: Better compatibility with Docker images

## Project Structure

```
.
├── cdk/                    # CDK infrastructure code
│   ├── bin/               # CDK app entry point
│   ├── lib/               # Stack definitions
│   ├── test/              # Tests
│   └── package.json       # Node dependencies
├── lambda/                # Lambda function code
│   └── shropshire/
│       ├── main.py        # Scraper logic
│       ├── requirements.txt
│       └── Dockerfile     # Docker image with Playwright
└── .github/workflows/     # CI/CD
```

## Cost

Approximately **$0.10-0.20/month**:
- Lambda: ~$0.02/month (1024MB, x86_64, daily invocation)
- ECR Storage: ~$0.05/month (Docker image storage)
- SSM Parameter Store: Free tier (3 parameters)
- CloudWatch Logs: ~$0.03/month (3-day retention)

## Setup

### 1. Fork/Clone Repository

### 2. Configure GitHub Secrets

Go to Settings → Secrets and variables → Actions, add:

- `AWS_ACCOUNT_NUMBER`: Your AWS account ID
- `PROPERTY_ID`: Your Shropshire Council property ID (from URL: https://bins.shropshire.gov.uk/property/XXXXX)
- `BOT_TOKEN`: Your Telegram bot token (from @BotFather)
- `CHAT_ID`: Your Telegram chat ID

### 3. Deploy Infrastructure

Push to main branch - GitHub Actions will:
1. Bootstrap CDK (if needed)
2. Build and push Docker image to ECR
3. Deploy the stack
4. Create placeholder SSM parameters

### 4. Configure SSM Parameters

After first deploy, update the placeholder values in AWS Console:

```bash
aws ssm put-parameter --name "/binalerts/prod/property-id" --value "YOUR_PROPERTY_ID" --type SecureString --overwrite
aws ssm put-parameter --name "/binalerts/prod/bot-token" --value "YOUR_BOT_TOKEN" --type SecureString --overwrite
aws ssm put-parameter --name "/binalerts/prod/chat-id" --value "YOUR_CHAT_ID" --type SecureString --overwrite
```

Or use AWS Console → Systems Manager → Parameter Store.

### 5. Test

Manually invoke the Lambda function in AWS Console to verify it works.

## How It Works

1. **Daily Trigger**: EventBridge triggers Lambda at 19:07
2. **Scrape**: Playwright launches headless Chromium, visits council website
3. **Parse**: Extracts collection dates using CSS selectors (service IDs) or text matching
4. **Notify**: If a collection is within 24 hours, sends Telegram message
5. **Health Check**: On Sundays, notifies if no alerts were sent that week

## Supported Bin Types

- Garden Waste (green bin)
- Recycling (blue/purple bags)
- General Waste (grey bin)

## Development

### Local Testing

The Lambda uses a Docker image with Playwright/Chromium pre-installed:

```bash
cd lambda/shropshire

# Build Docker image locally
docker build -t binalerts-local .

# Or test Python directly (requires playwright install):
pip install playwright boto3 botocore
playwright install chromium
python main.py
```

### CDK Commands

```bash
cd cdk
npm install
npx cdk synth    # Synthesize CloudFormation template
npx cdk diff     # Show changes
npx cdk deploy   # Deploy stack (builds Docker image automatically)
```

## Troubleshooting

**No notifications?**
- Check CloudWatch Logs for errors
- Verify SSM parameters are set (not still "SET_MANUALLY_AFTER_DEPLOY")
- Test Telegram bot token: `curl "https://api.telegram.org/bot<TOKEN>/getMe"`

**Scraper not finding bins?**
- The council website structure may have changed
- Check CloudWatch logs for "Found X collections"
- Website may be down or blocking requests

**High costs?**
- Ensure log retention is 3 days (configured in stack)
- Check Lambda isn't being invoked excessively
- SSM is on free tier (up to 10,000 API calls/month)
- ECR: Image is small (~500MB), costs ~$0.05/month

**Docker build fails?**
- Ensure Docker is running locally
- Check GitHub Actions has Docker permissions (uses setup-buildx-action)

## License

MIT
