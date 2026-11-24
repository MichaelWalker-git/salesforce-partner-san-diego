# Salesforce San Diego website

Static site served by GitHub Pages from the root of the `master` branch at https://www.salesforcepartnersandiego.com/.

## Contact form

`contact.js` posts JSON to the endpoint in `config.js`. The AWS SAM stack `salesforce-site-contact` in `us-east-1` validates submissions, saves inquiries in a dedicated encrypted DynamoDB table, and notifies `michael@horustech.dev` through SES. Reply-To is the visitor's email. Campaign UTM parameters from the current page are saved with the inquiry. The API allows the WWW and apex production origins, throttles requests, and validates a hidden honeypot field.

The form reports success only after the API returns a saved inquiry reference. Failed requests preserve entered fields. An email notification failure does not delete a saved inquiry, so check the table and Lambda logs if notifications stop. Inquiry records expire after 180 days through DynamoDB TTL; TTL deletion is asynchronous, and mailbox retention is separate.

No browser secrets or AWS credentials belong in this repository. The public API endpoint in `config.js` is not a secret.

## Verification

```sh
node --check contact.js
node --test tests/contact.test.cjs
python3 -m unittest discover -s backend -p 'test_*.py'
sam validate --template-file backend/template.yaml --lint --region us-east-1
```

Python tests require boto3. The Lambda runtime supplies boto3 in production. The tests cover invalid submissions, storage failure, notification failure, successful receipt, preservation of input after failure, campaign capture, and repeat clicks while sending.

## Deployment

Deploy the backend before publishing a frontend endpoint change:

```sh
sam deploy --template-file backend/template.yaml \
  --stack-name salesforce-site-contact \
  --s3-bucket ledgertransfer-sam-039885961427-us-east-1 \
  --s3-prefix salesforce-site-contact \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides SenderEmail=michael@horustech.dev AdminEmail=michael@horustech.dev \
  --region us-east-1 --profile michael-primary
```

The artifact bucket is shared with the existing migration site's deployment tooling, with Salesforce artifacts in a separate prefix. The runtime API, function, table, and role are separate resources.

Use the stack's `ContactEndpoint` output in `config.js`. Commit and push website changes to `master` to publish through GitHub Pages. Verify the deployed page, CORS preflight, a clearly labeled internal test inquiry, its DynamoDB record, and notification handling. Browser layout and interaction checks should be performed when browser access is available.
