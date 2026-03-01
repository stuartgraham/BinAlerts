import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import { LambdaFunction } from 'aws-cdk-lib/aws-events-targets';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as path from 'path';

export class BinAlertsStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Lambda with Chromium layer for headless browser
    // Uses sparticuz/chromium layer for Playwright support
    const binAlertsFunction = new lambda.Function(this, 'BinAlertsFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'main.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda/shropshire')),
      timeout: cdk.Duration.seconds(45),
      memorySize: 1024,  // Chromium needs ~512MB minimum, 1024MB for stability
      architecture: lambda.Architecture.ARM_64,  // 20% cheaper than x86
      logRetention: logs.RetentionDays.THREE_DAYS,
      environment: {
        PROPERTY_ID: process.env.PROPERTY_ID!,
        BOT_TOKEN: process.env.BOT_TOKEN!,
        CHAT_ID: process.env.CHAT_ID!,
        PLAYWRIGHT_BROWSERS_PATH: '0',  // Use bundled browser
        PYTHONPATH: '/opt/python'
      },
      layers: [
        // Sparticuz Chromium layer (ARM64, Python 3.12)
        // This layer includes Chromium binary + Playwright dependencies
        lambda.LayerVersion.fromLayerVersionArn(
          this,
          'ChromiumLayer',
          `arn:aws:lambda:${this.region}:764866452798:layer:chromium:132`  // ARM64 version
        ),
        // Playwright Python layer
        lambda.LayerVersion.fromLayerVersionArn(
          this,
          'PlaywrightLayer',
          `arn:aws:lambda:${this.region}:764866452798:layer:playwright:8`  // ARM64 Python 3.12
        )
      ]
    });

    // EventBridge Rule - run daily at 19:07
    new events.Rule(this, 'DailyBinCheck', {
      schedule: events.Schedule.cron({ minute: '7', hour: '19' }),
      targets: [new LambdaFunction(binAlertsFunction)]
    });
  }
}
