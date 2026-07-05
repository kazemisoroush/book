package main

import (
	"github.com/aws/aws-cdk-go/awscdk/v2"
	"github.com/aws/jsii-runtime-go"
	"github.com/cdklabs/cdk-nag-go/cdknag/v2"
)

// suppressNag records the cdk-nag rules the Book Studio hosting accepts by design or defers.
func suppressNag(stack awscdk.Stack) {
	cdknag.NagSuppressions_AddStackSuppressions(stack, &[]*cdknag.NagPackSuppression{
		{
			Id:     jsii.String("AwsSolutions-S1"),
			Reason: jsii.String("S3 server access logging is deferred; the private web bucket holds only the static site, served through CloudFront."),
		},
		{
			Id:     jsii.String("AwsSolutions-CFR1"),
			Reason: jsii.String("CloudFront geo restriction is not needed for a personal studio."),
		},
		{
			Id:     jsii.String("AwsSolutions-CFR2"),
			Reason: jsii.String("CloudFront WAF is deferred; the site is a static frontend with no direct data access."),
		},
		{
			Id:     jsii.String("AwsSolutions-CFR3"),
			Reason: jsii.String("CloudFront access logging is deferred for the personal studio."),
		},
		{
			Id:     jsii.String("AwsSolutions-CFR4"),
			Reason: jsii.String("The default CloudFront domain and certificate are used; a custom domain with a TLS minimum version lands with the API deploy."),
		},
		{
			Id:     jsii.String("AwsSolutions-L1"),
			Reason: jsii.String("The S3 BucketDeployment and auto-delete custom resources use CDK-managed Lambdas whose runtime is pinned by the CDK version."),
		},
		{
			Id:     jsii.String("AwsSolutions-IAM5"),
			Reason: jsii.String("The CDK-managed BucketDeployment and auto-delete roles use wildcards scoped to the single web bucket by the CDK helpers."),
		},
		{
			Id:     jsii.String("AwsSolutions-IAM4"),
			Reason: jsii.String("The CDK-managed custom-resource Lambdas use the AWS managed basic execution role for CloudWatch Logs."),
		},
	}, jsii.Bool(true))
}
