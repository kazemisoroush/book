package main

// This file defines the CI/CD trust that lets GitHub Actions deploy via OIDC.

import (
	"fmt"

	"github.com/aws/aws-cdk-go/awscdk/v2"
	"github.com/aws/aws-cdk-go/awscdk/v2/awsiam"
	"github.com/aws/constructs-go/constructs/v10"
	"github.com/aws/jsii-runtime-go"
	"github.com/cdklabs/cdk-nag-go/cdknag/v2"
)

// gitHubOIDCURL is the GitHub Actions OIDC issuer.
const gitHubOIDCURL = "https://token.actions.githubusercontent.com"

// gitHubAudience is the audience GitHub sets when requesting AWS credentials.
const gitHubAudience = "sts.amazonaws.com"

// deploySubject pins the trust to a push on the main branch of the book repo.
const deploySubject = "repo:kazemisoroush/book:ref:refs/heads/main"

// gitHubThumbprint is the GitHub Actions OIDC root CA thumbprint.
const gitHubThumbprint = "6938fd4d98bab03faadb97b34396831e3780aea1"

// deployRoleName is the IAM role GitHub Actions assumes to deploy.
const deployRoleName = "book-github-actions-deploy"

// cdkBootstrapQualifier is the name prefix of the CDK bootstrap roles in this account.
const cdkBootstrapQualifier = "cdk-hnb659fds"

// NewBookCICDStack defines the OIDC provider and the GitHub Actions deploy role.
func NewBookCICDStack(scope constructs.Construct, id string, props *awscdk.StackProps) awscdk.Stack {
	stack := awscdk.NewStack(scope, &id, props)

	provider := awsiam.NewCfnOIDCProvider(stack, jsii.String("GitHubOIDC"), &awsiam.CfnOIDCProviderProps{
		Url:            jsii.String(gitHubOIDCURL),
		ClientIdList:   jsii.Strings(gitHubAudience),
		ThumbprintList: jsii.Strings(gitHubThumbprint),
	})

	principal := awsiam.NewFederatedPrincipal(
		provider.AttrArn(),
		&map[string]any{
			"StringEquals": map[string]any{
				"token.actions.githubusercontent.com:aud": gitHubAudience,
				"token.actions.githubusercontent.com:sub": deploySubject,
			},
		},
		jsii.String("sts:AssumeRoleWithWebIdentity"),
	)

	role := awsiam.NewRole(stack, jsii.String("GithubActionsDeploy"), &awsiam.RoleProps{
		RoleName:    jsii.String(deployRoleName),
		AssumedBy:   principal,
		Description: jsii.String("GitHub Actions assumes this via OIDC to deploy the Book stacks."),
	})

	bootstrapRoles := fmt.Sprintf("arn:aws:iam::%s:role/%s-*", *stack.Account(), cdkBootstrapQualifier)
	role.AddToPolicy(awsiam.NewPolicyStatement(&awsiam.PolicyStatementProps{
		Actions:   jsii.Strings("sts:AssumeRole"),
		Resources: jsii.Strings(bootstrapRoles),
	}))

	cdknag.NagSuppressions_AddResourceSuppressions(role, &[]*cdknag.NagPackSuppression{
		{
			Id:     jsii.String("AwsSolutions-IAM5"),
			Reason: jsii.String(fmt.Sprintf("The deploy role may only assume the CDK bootstrap roles, which share the %s-* name prefix. The wildcard is scoped to those roles in this account.", cdkBootstrapQualifier)),
		},
	}, jsii.Bool(true))

	awscdk.NewCfnOutput(stack, jsii.String("DeployRoleArn"), &awscdk.CfnOutputProps{Value: role.RoleArn()})

	return stack
}
