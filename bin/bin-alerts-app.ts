#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { BinAlertsStack } from '../lib/bin-alerts-stack';

const app = new cdk.App();
new BinAlertsStack(app, 'BinAlertsStack', {
  env: { account: process.env.AWS_ACCOUNT_NUMBER!, region: 'eu-west-1' },
});