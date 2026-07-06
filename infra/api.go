package main

// This file defines the API: an S3 books bucket, a provider secret, Cognito auth, the
// API and worker Lambdas from one image, and the HTTP API that fronts them.

import (
	"github.com/aws/aws-cdk-go/awscdk/v2"
	"github.com/aws/aws-cdk-go/awscdk/v2/awsapigatewayv2"
	"github.com/aws/aws-cdk-go/awscdk/v2/awsapigatewayv2authorizers"
	"github.com/aws/aws-cdk-go/awscdk/v2/awsapigatewayv2integrations"
	"github.com/aws/aws-cdk-go/awscdk/v2/awscognito"
	"github.com/aws/aws-cdk-go/awscdk/v2/awslambda"
	"github.com/aws/aws-cdk-go/awscdk/v2/awss3"
	"github.com/aws/aws-cdk-go/awscdk/v2/awssecretsmanager"
	"github.com/aws/constructs-go/constructs/v10"
	"github.com/aws/jsii-runtime-go"
)

// workerImageFile is the Dockerfile both Lambdas run, differing only by their handler.
const workerImageFile = "Dockerfile.worker"

// apiHandler is the API Lambda entrypoint.
const apiHandler = "src.api.lambda_handler.handler"

// workerHandler runs one workflow invocation.
const workerHandler = "src.api.run_worker.handler"

// Lambda environment keys and the S3 storage backend selector.
const (
	envStorage        = "BOOK_STORAGE"
	envBucket         = "BOOK_S3_BUCKET"
	envAllowedOrigins = "API_ALLOWED_ORIGINS"
	envWorkerName     = "WORKER_FUNCTION_NAME"
	envSecretArn      = "PROVIDER_SECRET_ARN"
	storageBackendS3  = "s3"
)

// api holds the values the stack wiring needs: the outputs for the frontend config, and the
// health route for the nag suppression.
type api struct {
	url         *string
	userPoolID  *string
	clientID    *string
	bucketName  *string
	healthRoute constructs.IConstruct
}

// newApi provisions the books bucket, the secret, Cognito, the two Lambdas, and the HTTP API.
func newApi(stack awscdk.Stack, allowedOrigins *[]*string) api {
	// The books bucket holds the generated audiobooks, the project's whole output, so it is
	// retained on stack delete rather than auto-deleted with the rebuildable web bucket.
	books := awss3.NewBucket(stack, jsii.String("Books"), &awss3.BucketProps{
		BlockPublicAccess: awss3.BlockPublicAccess_BLOCK_ALL(),
		Encryption:        awss3.BucketEncryption_S3_MANAGED,
		EnforceSSL:        jsii.Bool(true),
		Versioned:         jsii.Bool(true),
		RemovalPolicy:     awscdk.RemovalPolicy_RETAIN,
	})

	secret := awssecretsmanager.NewSecret(stack, jsii.String("ProviderSecrets"), &awssecretsmanager.SecretProps{
		Description:   jsii.String("Provider credentials: CLAUDE_CODE_OAUTH_TOKEN and ELEVENLABS_API_KEY."),
		RemovalPolicy: awscdk.RemovalPolicy_DESTROY,
	})

	pool := awscognito.NewUserPool(stack, jsii.String("Users"), &awscognito.UserPoolProps{
		SelfSignUpEnabled: jsii.Bool(false),
		SignInAliases:     &awscognito.SignInAliases{Email: jsii.Bool(true)},
		PasswordPolicy: &awscognito.PasswordPolicy{
			MinLength:        jsii.Number(12),
			RequireLowercase: jsii.Bool(true),
			RequireUppercase: jsii.Bool(true),
			RequireDigits:    jsii.Bool(true),
			RequireSymbols:   jsii.Bool(true),
		},
		AccountRecovery: awscognito.AccountRecovery_EMAIL_ONLY,
		RemovalPolicy:   awscdk.RemovalPolicy_DESTROY,
	})
	client := pool.AddClient(jsii.String("StudioClient"), &awscognito.UserPoolClientOptions{
		GenerateSecret:      jsii.Bool(false),
		AuthFlows:           &awscognito.AuthFlow{UserSrp: jsii.Bool(true)},
		AccessTokenValidity: awscdk.Duration_Hours(jsii.Number(1)),
		IdTokenValidity:     awscdk.Duration_Hours(jsii.Number(1)),
	})

	base := map[string]*string{
		envStorage: jsii.String(storageBackendS3),
		envBucket:  books.BucketName(),
	}

	// The worker carries the secret ARN so it can read the provider tokens at runtime (SOR-17).
	worker := awslambda.NewDockerImageFunction(stack, jsii.String("Worker"), &awslambda.DockerImageFunctionProps{
		Code:       imageCode(workerHandler),
		Timeout:    awscdk.Duration_Minutes(jsii.Number(15)),
		MemorySize: jsii.Number(2048),
		Environment: envWith(base, map[string]*string{
			envSecretArn: secret.SecretArn(),
		}),
	})

	apiFn := awslambda.NewDockerImageFunction(stack, jsii.String("Api"), &awslambda.DockerImageFunctionProps{
		Code:       imageCode(apiHandler),
		Timeout:    awscdk.Duration_Seconds(jsii.Number(30)),
		MemorySize: jsii.Number(512),
		Environment: envWith(base, map[string]*string{
			envAllowedOrigins: awscdk.Fn_Join(jsii.String(","), allowedOrigins),
			envWorkerName:     worker.FunctionName(),
		}),
	})

	books.GrantReadWrite(apiFn, nil)
	books.GrantReadWrite(worker, nil)
	secret.GrantRead(worker, nil)
	worker.GrantInvoke(apiFn)

	httpApi := awsapigatewayv2.NewHttpApi(stack, jsii.String("HttpApi"), &awsapigatewayv2.HttpApiProps{
		CorsPreflight: &awsapigatewayv2.CorsPreflightOptions{
			AllowOrigins: allowedOrigins,
			AllowMethods: &[]awsapigatewayv2.CorsHttpMethod{
				awsapigatewayv2.CorsHttpMethod_GET,
				awsapigatewayv2.CorsHttpMethod_POST,
				awsapigatewayv2.CorsHttpMethod_PATCH,
				awsapigatewayv2.CorsHttpMethod_DELETE,
			},
			AllowHeaders: jsii.Strings("Content-Type", "Authorization"),
		},
	})

	integration := awsapigatewayv2integrations.NewHttpLambdaIntegration(jsii.String("ApiIntegration"), apiFn, nil)
	authorizer := awsapigatewayv2authorizers.NewHttpUserPoolAuthorizer(jsii.String("JwtAuthorizer"), pool, &awsapigatewayv2authorizers.HttpUserPoolAuthorizerProps{
		UserPoolClients: &[]awscognito.IUserPoolClient{client},
	})

	// /health is public. The data routes list the real verbs, not ANY: ANY would also match
	// OPTIONS and send the CORS preflight through the authorizer (401), which the browser
	// preflight fails. Leaving OPTIONS unrouted lets the HTTP API answer preflight itself.
	healthRoutes := httpApi.AddRoutes(&awsapigatewayv2.AddRoutesOptions{
		Path:        jsii.String("/health"),
		Methods:     &[]awsapigatewayv2.HttpMethod{awsapigatewayv2.HttpMethod_GET},
		Integration: integration,
	})
	httpApi.AddRoutes(&awsapigatewayv2.AddRoutesOptions{
		Path: jsii.String("/{proxy+}"),
		Methods: &[]awsapigatewayv2.HttpMethod{
			awsapigatewayv2.HttpMethod_GET,
			awsapigatewayv2.HttpMethod_POST,
			awsapigatewayv2.HttpMethod_PATCH,
			awsapigatewayv2.HttpMethod_DELETE,
		},
		Integration: integration,
		Authorizer:  authorizer,
	})

	return api{
		url:         httpApi.Url(),
		userPoolID:  pool.UserPoolId(),
		clientID:    client.UserPoolClientId(),
		bucketName:  books.BucketName(),
		healthRoute: (*healthRoutes)[0],
	}
}

// imageCode builds the shared worker image and overrides its command to run *handler*.
func imageCode(handler string) awslambda.DockerImageCode {
	return awslambda.DockerImageCode_FromImageAsset(jsii.String(".."), &awslambda.AssetImageCodeProps{
		File: jsii.String(workerImageFile),
		Cmd:  &[]*string{jsii.String(handler)},
	})
}

// envWith merges the base environment with any extra keys.
func envWith(base, extra map[string]*string) *map[string]*string {
	merged := map[string]*string{}
	for key, value := range base {
		merged[key] = value
	}
	for key, value := range extra {
		merged[key] = value
	}
	return &merged
}
