// CDK app that hosts the Book Studio frontend on S3 + CloudFront.
package main

import (
	"os"

	"github.com/aws/aws-cdk-go/awscdk/v2"
	"github.com/aws/constructs-go/constructs/v10"
	"github.com/aws/jsii-runtime-go"
	"github.com/cdklabs/cdk-nag-go/cdknag/v2"
)

// NewBookStudioStack defines the static-site hosting for the frontend.
func NewBookStudioStack(scope constructs.Construct, id string, props *awscdk.StackProps) awscdk.Stack {
	stack := awscdk.NewStack(scope, &id, props)

	hosting := newFrontendHosting(stack)
	hosting.deploy(stack)

	awscdk.NewCfnOutput(stack, jsii.String("FrontendUrl"), &awscdk.CfnOutputProps{Value: jsii.String(hosting.URL())})

	suppressNag(stack)
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
