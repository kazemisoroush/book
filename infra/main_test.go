package main

import (
	"testing"

	"github.com/aws/aws-cdk-go/awscdk/v2"
	"github.com/aws/aws-cdk-go/awscdk/v2/assertions"
	"github.com/aws/jsii-runtime-go"
)

// TestStackStandsUpTheStudio checks the hosting, storage, auth, and API resources are present.
func TestStackStandsUpTheStudio(t *testing.T) {
	defer jsii.Close()

	app := awscdk.NewApp(nil)
	stack := NewBookStudioStack(app, "TestStack", nil)
	template := assertions.Template_FromStack(stack, nil)

	// The web bucket and the books bucket, one CloudFront distribution.
	template.ResourceCountIs(jsii.String("AWS::S3::Bucket"), jsii.Number(2))
	template.ResourceCountIs(jsii.String("AWS::CloudFront::Distribution"), jsii.Number(1))

	// Cognito auth, the HTTP API, and the provider secret.
	template.ResourceCountIs(jsii.String("AWS::Cognito::UserPool"), jsii.Number(1))
	template.ResourceCountIs(jsii.String("AWS::ApiGatewayV2::Api"), jsii.Number(1))
	template.ResourceCountIs(jsii.String("AWS::SecretsManager::Secret"), jsii.Number(1))

	// The API and worker Lambdas both run from a container image.
	template.HasResourceProperties(jsii.String("AWS::Lambda::Function"), map[string]any{
		"PackageType": "Image",
	})
}
