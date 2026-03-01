import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import { LambdaFunction } from 'aws-cdk-lib/aws-events-targets';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as path from 'path';

interface BinAlertsStackProps extends cdk.StackProps {
  readonly environment?: string;
}

export class BinAlertsStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: BinAlertsStackProps) {
    super(scope, id, props);

    const env = props?.environment || 'prod';

    // SSM Parameter Store (free tier) instead of Secrets Manager ($0.40/month)
    // Create placeholder parameters - set values manually after deployment
    const propertyIdParam = new ssm.StringParameter(this, 'PropertyIdParam', {
      parameterName: `/binalerts/${env}/property-id`,
      stringValue: 'SET_MANUALLY_AFTER_DEPLOY',
      description: 'Property ID for bin collection lookup'
    });

    const botTokenParam = new ssm.StringParameter(this, 'BotTokenParam', {
      parameterName: `/binalerts/${env}/bot-token`,
      stringValue: 'SET_MANUALLY_AFTER_DEPLOY',
      description: 'Telegram bot token',
      tier: ssm.ParameterTier.STANDARD
    });

    const chatIdParam = new ssm.StringParameter(this, 'ChatIdParam', {
      parameterName: `/binalerts/${env}/chat-id`,
      stringValue: 'SET_MANUALLY_AFTER_DEPLOY',
      description: 'Telegram chat ID for notifications'
    });

    // Lambda function - Docker-based with Playwright/Chromium built-in
    const binAlertsFunction = new lambda.DockerImageFunction(this, 'BinAlertsFunction', {
      functionName: `binalerts-${env}`,
      code: lambda.DockerImageCode.fromImageAsset(path.join(__dirname, '../../lambda/shropshire')),
      timeout: cdk.Duration.seconds(45),
      memorySize: 1024,  // Required for Chromium
      architecture: lambda.Architecture.X86_64,
      logRetention: logs.RetentionDays.THREE_DAYS,
      environment: {
        ENVIRONMENT: env,
        SSM_PREFIX: `/binalerts/${env}`,
        LOG_LEVEL: 'INFO'
      },
      retryAttempts: 1,
      deadLetterQueueEnabled: false
    });

    // Grant Lambda access to SSM parameters
    binAlertsFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['ssm:GetParameter'],
        resources: [
          propertyIdParam.parameterArn,
          botTokenParam.parameterArn,
          chatIdParam.parameterArn
        ]
      })
    );

    // EventBridge Rule
    new events.Rule(this, 'DailyBinCheck', {
      ruleName: `binalerts-${env}`,
      schedule: events.Schedule.cron({ minute: '7', hour: '19' }),
      targets: [new LambdaFunction(binAlertsFunction)]
    });

    // Outputs
    new cdk.CfnOutput(this, 'SSMParameters', {
      value: `/binalerts/${env}/`,
      description: 'Set these SSM parameters manually after deployment'
    });

    new cdk.CfnOutput(this, 'LambdaFunction', {
      value: binAlertsFunction.functionName,
      description: 'Lambda function name'
    });

    new cdk.CfnOutput(this, 'MonthlyCostEstimate', {
      value: '~$0.10-0.20',
      description: 'Estimated monthly cost (Docker Lambda + ECR storage)'
    });
  }
}
