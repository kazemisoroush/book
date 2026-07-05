package main

import (
	"testing"

	"github.com/aws/aws-cdk-go/awscdk/v2"
	"github.com/aws/aws-cdk-go/awscdk/v2/assertions"
	"github.com/aws/jsii-runtime-go"
)

// TestStackHostsTheSite checks the frontend hosting resources are present.
func TestStackHostsTheSite(t *testing.T) {
	defer jsii.Close()

	app := awscdk.NewApp(nil)
	stack := NewBookStudioStack(app, "TestStack", nil)
	template := assertions.Template_FromStack(stack, nil)

	template.ResourceCountIs(jsii.String("AWS::S3::Bucket"), jsii.Number(1))
	template.ResourceCountIs(jsii.String("AWS::CloudFront::Distribution"), jsii.Number(1))
}
