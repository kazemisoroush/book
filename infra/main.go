// CDK app that hosts the Book Studio frontend on S3 + CloudFront.
package main

import (
	"os"

	"github.com/aws/aws-cdk-go/awscdk/v2"
	"github.com/aws/constructs-go/constructs/v10"
	"github.com/aws/jsii-runtime-go"
	"github.com/cdklabs/cdk-nag-go/cdknag/v2"
)

// NewBookStudioStack defines the frontend hosting, the API, and the auth in front of it.
func NewBookStudioStack(scope constructs.Construct, id string, props *awscdk.StackProps) awscdk.Stack {
	stack := awscdk.NewStack(scope, &id, props)

	hosting := newFrontendHosting(stack)
	origins := jsii.Strings("http://localhost:3000", hosting.URL())
	built := newApi(stack, origins)
	hosting.deploy(stack, built.url, built.userPoolID, built.clientID)

	awscdk.NewCfnOutput(stack, jsii.String("FrontendUrl"), &awscdk.CfnOutputProps{Value: jsii.String(hosting.URL())})
	awscdk.NewCfnOutput(stack, jsii.String("ApiUrl"), &awscdk.CfnOutputProps{Value: built.url})
	awscdk.NewCfnOutput(stack, jsii.String("BooksBucket"), &awscdk.CfnOutputProps{Value: built.bucketName})
	awscdk.NewCfnOutput(stack, jsii.String("UserPoolId"), &awscdk.CfnOutputProps{Value: built.userPoolID})
	awscdk.NewCfnOutput(stack, jsii.String("UserPoolClientId"), &awscdk.CfnOutputProps{Value: built.clientID})

	suppressNag(stack, built.healthRoute)
	return stack
}

func main() {
	defer jsii.Close()

	app := awscdk.NewApp(nil)
	NewBookStudioStack(app, "BookStudioStack", &awscdk.StackProps{Env: stackEnv()})
	NewBookCICDStack(app, "BookCICDStack", &awscdk.StackProps{Env: stackEnv()})
	awscdk.Aspects_Of(app).Add(cdknag.NewAwsSolutionsChecks(&cdknag.NagPackProps{Verbose: jsii.Bool(true)}), nil)
	app.Synth(nil)
}

// stackEnv reads the deployment target from the standard CDK environment variables.
func stackEnv() *awscdk.Environment {
	return &awscdk.Environment{
		Account: jsii.String(os.Getenv("CDK_DEFAULT_ACCOUNT")),
		Region:  jsii.String(os.Getenv("CDK_DEFAULT_REGION")),
	}
}
