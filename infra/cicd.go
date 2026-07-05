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

// gitHubOIDCHost is the GitHub Actions OIDC issuer host.
const gitHubOIDCHost = "token.actions.githubusercontent.com"

// gitHubAudience is the audience GitHub sets when requesting AWS credentials.
const gitHubAudience = "sts.amazonaws.com"

// deploySubject pins the trust to a push on the main branch of the book repo.
const deploySubject = "repo:kazemisoroush/book:ref:refs/heads/main"

// deployRoleName is the IAM role GitHub Actions assumes to deploy.
const deployRoleName = "book-github-actions-deploy"

// cdkBootstrapQualifier is the name prefix of the CDK bootstrap roles in this account.
const cdkBootstrapQualifier = "cdk-hnb659fds"

// NewBookCICDStack defines the deploy role, trusting the account's shared GitHub OIDC provider.
func NewBookCICDStack(scope constructs.Construct, id string, props *awscdk.StackProps) awscdk.Stack {
	stack := awscdk.NewStack(scope, &id, props)

	providerArn := fmt.Sprintf("arn:aws:iam::%s:oidc-provider/%s", *stack.Account(), gitHubOIDCHost)
	provider := awsiam.OpenIdConnectProvider_FromOpenIdConnectProviderArn(
		stack, jsii.String("GitHubOIDC"), jsii.String(providerArn),
	)

	principal := awsiam.NewFederatedPrincipal(
		provider.OpenIdConnectProviderArn(),
		&map[string]any{
			"StringEquals": map[string]any{
				gitHubOIDCHost + ":aud": gitHubAudience,
				gitHubOIDCHost + ":sub": deploySubject,
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
