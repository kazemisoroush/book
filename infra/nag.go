package main

import (
	"github.com/aws/aws-cdk-go/awscdk/v2"
	"github.com/aws/constructs-go/constructs/v10"
	"github.com/aws/jsii-runtime-go"
	"github.com/cdklabs/cdk-nag-go/cdknag/v2"
)

// suppressNag records the cdk-nag rules the Book Studio accepts by design or defers.
func suppressNag(stack awscdk.Stack, healthRoute constructs.IConstruct) {
	cdknag.NagSuppressions_AddStackSuppressions(stack, &[]*cdknag.NagPackSuppression{
		{
			Id:     jsii.String("AwsSolutions-IAM4"),
			Reason: jsii.String("The Lambdas and the CDK-managed custom resources use the AWS managed basic execution role for CloudWatch Logs."),
		},
		{
			Id:     jsii.String("AwsSolutions-IAM5"),
			Reason: jsii.String("The only wildcards are the CDK grant helpers scoping bucket access to the single web and books buckets, and the CDK-managed BucketDeployment role."),
		},
		{
			Id:     jsii.String("AwsSolutions-S1"),
			Reason: jsii.String("S3 server access logging is deferred; the private web and books buckets serve a single-user studio."),
		},
		{
			Id:     jsii.String("AwsSolutions-APIG1"),
			Reason: jsii.String("HTTP API access logging is deferred; single-user studio behind the Cognito authorizer."),
		},
		{
			Id:     jsii.String("AwsSolutions-COG2"),
			Reason: jsii.String("Cognito MFA is deferred; single-user studio."),
		},
		{
			Id:     jsii.String("AwsSolutions-COG8"),
			Reason: jsii.String("Cognito advanced security requires the paid Plus tier and is deferred; single-user studio."),
		},
		{
			Id:     jsii.String("AwsSolutions-SMG4"),
			Reason: jsii.String("Automatic secret rotation is deferred; the provider tokens are rotated by hand through setup-token."),
		},
		{
			Id:     jsii.String("AwsSolutions-CFR1"),
			Reason: jsii.String("CloudFront geo restriction is not needed for a personal studio."),
		},
		{
			Id:     jsii.String("AwsSolutions-CFR2"),
			Reason: jsii.String("CloudFront WAF is deferred; the site is a static frontend and the API is behind Cognito."),
		},
		{
			Id:     jsii.String("AwsSolutions-CFR3"),
			Reason: jsii.String("CloudFront access logging is deferred for the personal studio."),
		},
		{
			Id:     jsii.String("AwsSolutions-CFR4"),
			Reason: jsii.String("The default CloudFront domain and certificate are used; a custom domain with a TLS minimum version lands later."),
		},
		{
			Id:     jsii.String("AwsSolutions-L1"),
			Reason: jsii.String("The S3 BucketDeployment and auto-delete custom resources use CDK-managed Lambdas whose runtime is pinned by the CDK version."),
		},
	}, jsii.Bool(true))

	cdknag.NagSuppressions_AddResourceSuppressions(healthRoute, &[]*cdknag.NagPackSuppression{
		{
			Id:     jsii.String("AwsSolutions-APIG4"),
			Reason: jsii.String("GET /health is an unauthenticated liveness probe that returns no data; every data route requires the Cognito JWT authorizer."),
		},
		{
			Id:     jsii.String("AwsSolutions-COG4"),
			Reason: jsii.String("GET /health is a liveness probe and needs no Cognito authorizer; the data routes use it."),
		},
	}, jsii.Bool(true))
}
