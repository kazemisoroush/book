# Infra

The cloud deployment, as AWS CDK in Go. For now it hosts the frontend static site; the API deploy and a custom domain land with M9.

## Stacks

- `BookStudioStack` puts the built frontend (`../frontend/out`) in a private S3 bucket behind a CloudFront distribution over HTTPS, with origin access control and a viewer-request function that rewrites directory and extensionless URLs to their `index.html`.
- `BookCICDStack` defines the `book-github-actions-deploy` role, trusted only by a push to `main` of this repo. The role may assume the CDK bootstrap roles, so CI deploys with no long-lived AWS keys. It imports the account's shared GitHub OIDC provider rather than creating one, since an account allows only one provider per issuer and the `vault` and `direct` repos share it.

## Files

- `main.go` the CDK app and the stacks.
- `frontend.go` the S3 and CloudFront static hosting.
- `cicd.go` the OIDC provider and the GitHub Actions deploy role.
- `nag.go` the cdk-nag suppressions, each with a reason.
- `main_test.go` and `cicd_test.go` synth tests for the two stacks.

## CI/CD

On a push to `main`, the `deploy` job assumes `book-github-actions-deploy` through OIDC and runs `cdk deploy BookStudioStack`, so a merge ships the site with no stored credentials.

One-time bootstrap (run once, with admin credentials):

1. `cdk bootstrap aws://<account>/<region>` creates the `cdk-hnb659fds-*` roles.
2. `cdk deploy BookCICDStack` creates the deploy role against the shared OIDC provider. Note its `DeployRoleArn` output.
3. Set the GitHub repo variables `AWS_DEPLOY_ROLE_ARN` (that ARN) and `AWS_REGION`.

The `deploy` job skips until `AWS_DEPLOY_ROLE_ARN` is set, so CI stays green before the bootstrap.

## Security gate

Every synth runs cdk-nag (`AwsSolutionsChecks`). Findings either fail the build or are suppressed with a stated reason in `nag.go`.

## Commands

`make infra-synth` from the repo root, or `cdk synth` here, synthesizes the stack and runs the gate. It needs `../frontend/out` to exist, so build the frontend first. `go test ./...` runs the synth test. Deploy happens in CI on push to main once the AWS role is configured.
