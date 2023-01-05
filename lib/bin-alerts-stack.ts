import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import { LambdaFunction } from 'aws-cdk-lib/aws-events-targets';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as ssm from 'aws-cdk-lib/aws-ssm';

export class BinAlertsStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

  // ECR
  const ecrRepo = new ecr.Repository(this, "BinAlertsRepo", {
    repositoryName: 'binalerts'
  });
  ecrRepo.addLifecycleRule({ maxImageCount: 1 });

  // Docker Image Digest
  const shropshiredockerImageDigest = ssm.StringParameter.valueFromLookup(this, '/binalerts/shropshireDockerImage');

  // Lambda
  const binAlertsFunction = new lambda.DockerImageFunction(this, 'BinAlertsFunctions', {
    code: lambda.DockerImageCode.fromEcr(ecrRepo, { tagOrDigest: shropshiredockerImageDigest}),
    timeout: cdk.Duration.minutes(5),
    memorySize: 512,
    logRetention: logs.RetentionDays.ONE_WEEK,
    environment: {
      PROPERTY_ID: process.env.PROPERTY_ID!,
      BOT_TOKEN: process.env.BOT_TOKEN!,
      CHAT_ID: process.env.CHAT_ID!
    }
  });


  // CLOUDWATCH Events
  // Run every 1 days
  new events.Rule(this, 'EveryDaysAt2007Rule', {
    schedule: events.Schedule.expression('cron(7 19 ? * * *)'),
    targets: [
      new LambdaFunction(binAlertsFunction)
    ]
  }); 
  }
}
