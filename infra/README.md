# Infra

The cloud deployment, as AWS CDK in Go. For now it hosts the frontend static site; the API deploy and a custom domain land with M9.

## Stack

`BookStudioStack` puts the built frontend (`../frontend/out`) in a private S3 bucket behind a CloudFront distribution over HTTPS, with origin access control and a viewer-request function that rewrites directory and extensionless URLs to their `index.html`.

## Files

- `main.go` the CDK app and the stack.
- `frontend.go` the S3 and CloudFront static hosting.
- `nag.go` the cdk-nag suppressions, each with a reason.
- `main_test.go` a synth test that the hosting resources exist.

## Security gate

Every synth runs cdk-nag (`AwsSolutionsChecks`). Findings either fail the build or are suppressed with a stated reason in `nag.go`.

## Commands

`make infra-synth` from the repo root, or `cdk synth` here, synthesizes the stack and runs the gate. It needs `../frontend/out` to exist, so build the frontend first. `go test ./...` runs the synth test. Deploy happens in CI on push to main once the AWS role is configured.
